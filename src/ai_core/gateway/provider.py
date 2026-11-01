"""Provider port: the only thing the rest of the system knows about a model backend."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable


class Locality(StrEnum):
    LOCAL = "local"  # runs inside our trust boundary (e.g. Ollama on a private network)
    EXTERNAL = "external"  # third-party API


class Sensitivity(StrEnum):
    AUTO = "auto"  # let the gateway classify the content
    PUBLIC = "public"  # may go anywhere, sent as-is
    INTERNAL = "internal"  # may go to external models, but only pseudonymised
    SENSITIVE = "sensitive"  # never leaves local providers


@dataclass(frozen=True)
class CompletionRequest:
    prompt: str
    system: str = ""
    max_tokens: int = 512
    temperature: float = 0.0
    json_mode: bool = False


class ProviderError(Exception):
    """Any failure to obtain a completion from a provider."""


class ProviderTimeout(ProviderError):
    pass


class ProviderRateLimited(ProviderError):
    pass


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    locality: Locality

    async def complete(self, request: CompletionRequest) -> str: ...
