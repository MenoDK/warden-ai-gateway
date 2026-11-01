from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from ai_core.config import Settings
from ai_core.container import Container, build_container
from ai_core.gateway.provider import CompletionRequest, Locality, ProviderError
from ai_core.main import create_app

API_KEY = "test-api-key"
WEBHOOK_SECRET = "whsec_current_for_tests"
OLD_WEBHOOK_SECRET = "whsec_previous_for_tests"
AUTH = {"x-api-key": API_KEY}

CORPUS = (
    "Rotating credentials every 90 days limits the blast radius of a leaked key. "
    "Short-lived tokens are preferred over long-lived passwords. "
    "Audit logs should be append-only and hash chained so tampering is detectable."
)


class FakeProvider:
    """Scriptable provider: records every request it receives."""

    def __init__(
        self,
        name: str,
        locality: Locality,
        reply: str | Callable[[CompletionRequest], str] = "ok [1]",
        *,
        fail: bool = False,
    ) -> None:
        self.name = name
        self.locality = locality
        self.reply = reply
        self.fail = fail
        self.requests: list[CompletionRequest] = []

    async def complete(self, request: CompletionRequest) -> str:
        self.requests.append(request)
        if self.fail:
            raise ProviderError("boom")
        return self.reply(request) if callable(self.reply) else self.reply


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        api_key=SecretStr(API_KEY),
        webhook_secrets=SecretStr(f"{WEBHOOK_SECRET},{OLD_WEBHOOK_SECRET}"),
        # Pinned so that REDIS_URL / DATABASE_URL in the environment (CI sets them for the
        # integration tests) can never leak into unit tests.
        database_url="",
        redis_url="",
        allowed_sources="docs/*,kb/*",
        rag_min_score=0.2,
    )


@pytest.fixture
def container(settings: Settings) -> Container:
    return build_container(settings)  # default wiring: demo local provider, in-memory stores


@pytest.fixture
def client(settings: Settings, container: Container) -> Iterator[TestClient]:
    with TestClient(create_app(settings, container=container)) as c:
        yield c
