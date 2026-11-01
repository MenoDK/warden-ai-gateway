import pytest

from ai_core.gateway.circuit_breaker import BreakerState, CircuitBreaker
from tests.conftest import FakeClock


def make(threshold: int = 3, reset: float = 30.0) -> tuple[CircuitBreaker, FakeClock, list[BreakerState]]:
    clock = FakeClock()
    changes: list[BreakerState] = []
    return (
        CircuitBreaker(failure_threshold=threshold, reset_seconds=reset, clock=clock, on_change=changes.append),
        clock,
        changes,
    )


def test_opens_after_consecutive_failures() -> None:
    breaker, _, changes = make(threshold=3)
    for _ in range(2):
        assert breaker.allow()
        breaker.record_failure()
    assert breaker.state is BreakerState.CLOSED
    breaker.record_failure()
    assert breaker.state is BreakerState.OPEN
    assert not breaker.allow()
    assert changes == [BreakerState.OPEN]


def test_success_resets_the_failure_streak() -> None:
    breaker, _, _ = make(threshold=2)
    breaker.record_failure()
    breaker.record_success()
    breaker.record_failure()
    assert breaker.state is BreakerState.CLOSED  # streak was reset, so 1 < threshold


def test_half_open_allows_exactly_one_probe() -> None:
    breaker, clock, _ = make(threshold=1, reset=30)
    breaker.record_failure()
    assert not breaker.allow()
    clock.advance(31)
    assert breaker.state is BreakerState.HALF_OPEN
    assert breaker.allow()  # the probe
    assert not breaker.allow()  # nobody else while it is in flight


def test_probe_success_closes_and_probe_failure_reopens() -> None:
    breaker, clock, _ = make(threshold=1, reset=30)
    breaker.record_failure()
    clock.advance(31)
    assert breaker.allow()
    breaker.record_success()
    assert breaker.state is BreakerState.CLOSED

    breaker.record_failure()
    clock.advance(31)
    assert breaker.allow()
    breaker.record_failure()
    assert breaker.state is BreakerState.OPEN
    clock.advance(10)
    assert not breaker.allow()  # the cool-down restarted from the failed probe


def test_rejects_invalid_threshold() -> None:
    with pytest.raises(ValueError):
        CircuitBreaker(failure_threshold=0)
