"""Circuit breaker: stop hammering a failing dependency, probe it again after a cool-down."""

from __future__ import annotations

import time
from collections.abc import Callable
from enum import StrEnum


class BreakerState(StrEnum):
    CLOSED = "closed"  # healthy, calls flow
    OPEN = "open"  # failing, calls are short-circuited
    HALF_OPEN = "half_open"  # cool-down elapsed, exactly one probe is allowed


class CircuitBreaker:
    """Not thread-safe by design: the gateway runs on a single asyncio event loop and the
    state transitions below never ``await`` in the middle of a read-modify-write."""

    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        reset_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
        on_change: Callable[[BreakerState], None] | None = None,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        self._threshold = failure_threshold
        self._reset = reset_seconds
        self._clock = clock
        self._on_change = on_change
        self._state = BreakerState.CLOSED
        self._failures = 0
        self._opened_at = 0.0
        self._probe_in_flight = False

    @property
    def state(self) -> BreakerState:
        # Reading the state must reflect the cool-down even if nobody called allow() yet.
        if self._state is BreakerState.OPEN and self._clock() - self._opened_at >= self._reset:
            return BreakerState.HALF_OPEN
        return self._state

    def allow(self) -> bool:
        state = self.state
        if state is BreakerState.CLOSED:
            return True
        if state is BreakerState.HALF_OPEN:
            if self._probe_in_flight:
                return False
            self._set(BreakerState.HALF_OPEN)
            self._probe_in_flight = True
            return True
        return False

    def record_success(self) -> None:
        self._failures = 0
        self._probe_in_flight = False
        self._set(BreakerState.CLOSED)

    def record_failure(self) -> None:
        self._probe_in_flight = False
        if self._state is BreakerState.HALF_OPEN:
            self._trip()
            return
        self._failures += 1
        if self._failures >= self._threshold:
            self._trip()

    def _trip(self) -> None:
        self._opened_at = self._clock()
        self._set(BreakerState.OPEN)

    def _set(self, new: BreakerState) -> None:
        if new is not self._state:
            self._state = new
            if self._on_change:
                self._on_change(new)
