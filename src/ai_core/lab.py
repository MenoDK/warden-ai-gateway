"""Laboratory mode: makes the gateway's failure behaviour observable. Development and demos only.

* ``SwitchableProvider`` wraps a real provider with an outage switch.
* ``DemoCloudProvider`` is a deterministic stand-in for a third-party API. It *records every prompt it
  receives*, so the lab can show exactly what crossed the trust boundary (placeholders, never the raw data).
* The HTTP side lives in ``ai_core.api.lab``; it is only mounted when ``LAB_MODE`` is on, and the settings
  validator refuses that flag in production.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from ai_core.gateway.provider import CompletionRequest, LLMProvider, Locality, ProviderError

_INBOX_LIMIT = 20


class SwitchableProvider:
    """Delegates to ``inner`` unless an operator has switched it off."""

    def __init__(self, inner: LLMProvider) -> None:
        self._inner = inner
        self.name = inner.name
        self.locality = inner.locality
        self.down = False

    async def complete(self, request: CompletionRequest) -> str:
        if self.down:
            raise ProviderError("simulated outage")
        return await self._inner.complete(request)

    async def aclose(self) -> None:
        close = getattr(self._inner, "aclose", None)
        if close:
            await close()


class DemoCloudProvider:
    """An external provider that is not a model: it echoes the prompt and remembers what it was sent."""

    name = "demo-cloud"
    locality = Locality.EXTERNAL

    def __init__(self) -> None:
        self.received: deque[str] = deque(maxlen=_INBOX_LIMIT)

    async def complete(self, request: CompletionRequest) -> str:
        self.received.append(request.prompt)
        return f"(demo cloud model) I was asked: {request.prompt[:240]}"


@dataclass
class LabControl:
    switches: dict[str, SwitchableProvider]
    cloud: DemoCloudProvider | None

    def reset(self) -> None:
        """Every provider up and the cloud inbox empty. Breakers and stored knowledge are reset by the caller."""
        for provider in self.switches.values():
            provider.down = False
        if self.cloud is not None:
            self.cloud.received.clear()


def wrap_for_lab(providers: list[LLMProvider]) -> tuple[list[LLMProvider], LabControl]:
    cloud: DemoCloudProvider | None = None
    if not any(p.locality is Locality.EXTERNAL for p in providers):
        cloud = DemoCloudProvider()
        providers = [*providers, cloud]
    wrapped = [SwitchableProvider(p) for p in providers]
    return list(wrapped), LabControl({p.name: p for p in wrapped}, cloud)
