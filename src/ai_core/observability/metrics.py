"""Prometheus metrics. One registry per app instance keeps tests isolated."""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

from ai_core.gateway.circuit_breaker import BreakerState
from ai_core.gateway.router import Attempt

_STATE_VALUE = {BreakerState.CLOSED: 0, BreakerState.HALF_OPEN: 1, BreakerState.OPEN: 2}


class Metrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self.http_requests = Counter(
            "http_requests_total", "HTTP requests", ["method", "route", "status"], registry=self.registry
        )
        self.http_latency = Histogram(
            "http_request_duration_seconds",
            "HTTP latency",
            ["method", "route"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
            registry=self.registry,
        )
        self.provider_attempts = Counter(
            "llm_provider_attempts_total",
            "LLM provider attempts by outcome",
            ["provider", "locality", "outcome"],
            registry=self.registry,
        )
        self.breaker_state = Gauge(
            "llm_circuit_breaker_state",
            "0=closed 1=half_open 2=open",
            ["provider"],
            registry=self.registry,
        )
        self.webhooks = Counter(
            "webhook_events_total", "Webhook deliveries by outcome", ["outcome"], registry=self.registry
        )

    def on_attempt(self, attempt: Attempt) -> None:
        self.provider_attempts.labels(attempt.provider, attempt.locality.value, attempt.outcome).inc()

    def on_breaker_change(self, provider: str, state: BreakerState) -> None:
        self.breaker_state.labels(provider).set(_STATE_VALUE[state])

    def render(self) -> bytes:
        return generate_latest(self.registry)
