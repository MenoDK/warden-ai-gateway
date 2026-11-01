"""Sensitivity-aware routing with per-provider circuit breakers and explicit failure.

Rules (in order of precedence):

1. ``SENSITIVE`` content is only ever offered to ``LOCAL`` providers. If none is healthy the
   call *fails* -- there is deliberately no "fall back to the cloud" path.
2. ``INTERNAL`` content may reach ``EXTERNAL`` providers only after pseudonymisation; the
   answer is re-hydrated locally.
3. ``AUTO`` classifies the request: personal data / secrets found -> ``SENSITIVE``,
   otherwise ``INTERNAL`` (the safe default for anything not explicitly public).
4. Providers are tried in configured order; an open breaker is skipped, not waited on.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Literal

from ai_core.gateway.circuit_breaker import BreakerState, CircuitBreaker
from ai_core.gateway.provider import (
    CompletionRequest,
    LLMProvider,
    Locality,
    ProviderError,
    ProviderTimeout,
    Sensitivity,
)
from ai_core.privacy.masker import PIIMasker

Outcome = Literal["ok", "error", "timeout", "circuit_open", "skipped_sensitive"]


@dataclass(frozen=True)
class Attempt:
    provider: str
    locality: Locality
    outcome: Outcome
    detail: str = ""


@dataclass(frozen=True)
class RouteResult:
    text: str
    provider: str
    locality: Locality
    sensitivity: Sensitivity  # the *effective* sensitivity after classification
    pseudonymised: bool
    attempts: tuple[Attempt, ...]


class GatewayError(Exception):
    def __init__(self, message: str, attempts: Sequence[Attempt]) -> None:
        super().__init__(message)
        self.attempts = tuple(attempts)


class NoEligibleProvider(GatewayError):
    """Policy forbids every configured provider for this content."""


class AllProvidersFailed(GatewayError):
    """Eligible providers exist, but none produced an answer."""


class SensitivityRouter:
    def __init__(
        self,
        providers: Sequence[LLMProvider],
        masker: PIIMasker,
        *,
        timeout_seconds: float = 30.0,
        failure_threshold: int = 3,
        reset_seconds: float = 30.0,
        clock: Callable[[], float] | None = None,
        on_attempt: Callable[[Attempt], None] | None = None,
        on_breaker_change: Callable[[str, BreakerState], None] | None = None,
    ) -> None:
        self._providers = list(providers)
        self._masker = masker
        self._timeout = timeout_seconds
        self._on_attempt = on_attempt

        breaker_kwargs: dict[str, object] = {}
        if clock is not None:
            breaker_kwargs["clock"] = clock
        self._breakers: dict[str, CircuitBreaker] = {}
        for p in self._providers:
            callback = (lambda state, name=p.name: on_breaker_change(name, state)) if on_breaker_change else None
            self._breakers[p.name] = CircuitBreaker(
                failure_threshold=failure_threshold,
                reset_seconds=reset_seconds,
                on_change=callback,
                **breaker_kwargs,  # type: ignore[arg-type]
            )

    @property
    def provider_names(self) -> list[str]:
        return [p.name for p in self._providers]

    def reset_breakers(self) -> None:
        for breaker in self._breakers.values():
            breaker.reset()

    def breaker_states(self) -> dict[str, BreakerState]:
        return {name: b.state for name, b in self._breakers.items()}

    def classify(self, request: CompletionRequest, requested: Sensitivity) -> Sensitivity:
        if requested is not Sensitivity.AUTO:
            return requested
        if self._masker.detect(f"{request.system}\n{request.prompt}"):
            return Sensitivity.SENSITIVE
        return Sensitivity.INTERNAL

    async def complete(self, request: CompletionRequest, sensitivity: Sensitivity = Sensitivity.AUTO) -> RouteResult:
        effective = self.classify(request, sensitivity)
        attempts: list[Attempt] = []

        eligible: list[LLMProvider] = []
        for p in self._providers:
            if effective is Sensitivity.SENSITIVE and p.locality is not Locality.LOCAL:
                self._record(attempts, Attempt(p.name, p.locality, "skipped_sensitive"))
            else:
                eligible.append(p)

        if not eligible:
            raise NoEligibleProvider("no provider is allowed to process content of this sensitivity", attempts)

        for provider in eligible:
            breaker = self._breakers[provider.name]
            if not breaker.allow():
                self._record(attempts, Attempt(provider.name, provider.locality, "circuit_open"))
                continue

            outbound, mapping = self._prepare(request, provider, effective)
            try:
                text = await asyncio.wait_for(provider.complete(outbound), self._timeout)
            except TimeoutError:
                breaker.record_failure()
                self._record(
                    attempts,
                    Attempt(provider.name, provider.locality, "timeout", f">{self._timeout}s"),
                )
                continue
            except ProviderError as exc:
                breaker.record_failure()
                self._record(
                    attempts,
                    Attempt(
                        provider.name,
                        provider.locality,
                        "timeout" if isinstance(exc, ProviderTimeout) else "error",
                        type(exc).__name__,
                    ),
                )
                continue

            breaker.record_success()
            self._record(attempts, Attempt(provider.name, provider.locality, "ok"))
            return RouteResult(
                text=PIIMasker.unmask(text, mapping) if mapping else text,
                provider=provider.name,
                locality=provider.locality,
                sensitivity=effective,
                pseudonymised=bool(mapping),
                attempts=tuple(attempts),
            )

        raise AllProvidersFailed("every eligible provider failed or is unavailable", attempts)

    def _prepare(
        self, request: CompletionRequest, provider: LLMProvider, effective: Sensitivity
    ) -> tuple[CompletionRequest, dict[str, str]]:
        """Pseudonymise whatever is about to cross the trust boundary."""
        if provider.locality is Locality.LOCAL or effective is Sensitivity.PUBLIC:
            return request, {}
        masked_prompt = self._masker.mask(request.prompt)
        masked_system = self._masker.mask(request.system)
        mapping = {**masked_system.mapping, **masked_prompt.mapping}
        return replace(request, prompt=masked_prompt.text, system=masked_system.text), mapping

    def _record(self, attempts: list[Attempt], attempt: Attempt) -> None:
        attempts.append(attempt)
        if self._on_attempt:
            self._on_attempt(attempt)
