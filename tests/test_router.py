import asyncio

import pytest

from ai_core.gateway.circuit_breaker import BreakerState
from ai_core.gateway.provider import CompletionRequest, Locality, Sensitivity
from ai_core.gateway.router import AllProvidersFailed, NoEligibleProvider, SensitivityRouter
from ai_core.privacy.masker import PIIMasker
from tests.conftest import FakeClock, FakeProvider

PII_PROMPT = "Summarise the complaint from ana@example.com"


def router(*providers: FakeProvider, **kwargs: object) -> SensitivityRouter:
    return SensitivityRouter(list(providers), PIIMasker(), **kwargs)  # type: ignore[arg-type]


async def test_sensitive_content_never_reaches_external() -> None:
    local = FakeProvider("local", Locality.LOCAL, "local answer")
    external = FakeProvider("cloud", Locality.EXTERNAL, "cloud answer")
    result = await router(external, local).complete(CompletionRequest(PII_PROMPT), Sensitivity.AUTO)
    assert result.provider == "local"
    assert result.sensitivity is Sensitivity.SENSITIVE
    assert external.requests == []  # not even attempted
    assert [a.outcome for a in result.attempts] == ["skipped_sensitive", "ok"]


async def test_sensitive_with_no_local_provider_fails_closed() -> None:
    external = FakeProvider("cloud", Locality.EXTERNAL)
    with pytest.raises(NoEligibleProvider) as exc:
        await router(external).complete(CompletionRequest("anything"), Sensitivity.SENSITIVE)
    assert external.requests == []
    assert exc.value.attempts[0].outcome == "skipped_sensitive"


async def test_sensitive_local_failure_does_not_fall_back_to_cloud() -> None:
    local = FakeProvider("local", Locality.LOCAL, fail=True)
    external = FakeProvider("cloud", Locality.EXTERNAL)
    with pytest.raises(AllProvidersFailed):
        await router(local, external).complete(CompletionRequest("x"), Sensitivity.SENSITIVE)
    assert external.requests == []


async def test_internal_content_is_pseudonymised_for_external_and_restored() -> None:
    echo = FakeProvider("cloud", Locality.EXTERNAL, lambda r: f"Reply to {r.prompt.split()[-1]}")
    result = await router(echo).complete(CompletionRequest(PII_PROMPT), Sensitivity.INTERNAL)
    sent = echo.requests[0].prompt
    assert "ana@example.com" not in sent and "<EMAIL_1>" in sent
    assert result.pseudonymised
    assert result.text == "Reply to ana@example.com"  # re-hydrated locally


async def test_public_content_is_sent_as_is() -> None:
    external = FakeProvider("cloud", Locality.EXTERNAL)
    await router(external).complete(CompletionRequest(PII_PROMPT), Sensitivity.PUBLIC)
    assert external.requests[0].prompt == PII_PROMPT


async def test_local_provider_receives_unmasked_text() -> None:
    local = FakeProvider("local", Locality.LOCAL)
    await router(local).complete(CompletionRequest(PII_PROMPT), Sensitivity.INTERNAL)
    assert local.requests[0].prompt == PII_PROMPT


async def test_auto_without_pii_is_internal() -> None:
    r = router(FakeProvider("local", Locality.LOCAL))
    assert r.classify(CompletionRequest("what is a mutex?"), Sensitivity.AUTO) is Sensitivity.INTERNAL


async def test_falls_back_to_next_provider_and_records_the_trace() -> None:
    first = FakeProvider("first", Locality.EXTERNAL, fail=True)
    second = FakeProvider("second", Locality.EXTERNAL, "fine")
    result = await router(first, second).complete(CompletionRequest("hi"), Sensitivity.PUBLIC)
    assert result.provider == "second"
    assert [(a.provider, a.outcome) for a in result.attempts] == [("first", "error"), ("second", "ok")]


async def test_breaker_opens_and_short_circuits_without_calling_the_provider() -> None:
    clock = FakeClock()
    flaky = FakeProvider("flaky", Locality.EXTERNAL, fail=True)
    backup = FakeProvider("backup", Locality.EXTERNAL, "backup")
    r = router(flaky, backup, failure_threshold=2, reset_seconds=30, clock=clock)

    for _ in range(2):
        await r.complete(CompletionRequest("x"), Sensitivity.PUBLIC)
    assert len(flaky.requests) == 2
    assert r.breaker_states()["flaky"] is BreakerState.OPEN

    result = await r.complete(CompletionRequest("x"), Sensitivity.PUBLIC)
    assert len(flaky.requests) == 2, "an open breaker must not call the provider"
    assert result.attempts[0].outcome == "circuit_open"

    clock.advance(31)
    flaky.fail = False
    flaky.reply = "recovered"
    result = await r.complete(CompletionRequest("x"), Sensitivity.PUBLIC)
    assert result.provider == "flaky"  # the half-open probe succeeded
    assert r.breaker_states()["flaky"] is BreakerState.CLOSED


async def test_timeout_counts_as_a_failure() -> None:
    class Slow(FakeProvider):
        async def complete(self, request: CompletionRequest) -> str:
            await asyncio.sleep(1)
            return "late"

    slow = Slow("slow", Locality.LOCAL)
    with pytest.raises(AllProvidersFailed) as exc:
        await router(slow, timeout_seconds=0.01).complete(CompletionRequest("x"), Sensitivity.PUBLIC)
    assert exc.value.attempts[0].outcome == "timeout"
