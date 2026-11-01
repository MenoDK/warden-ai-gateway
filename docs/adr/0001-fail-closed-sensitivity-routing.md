# ADR-0001: Fail-closed, sensitivity-aware model routing

**Status:** accepted

## Context
The service can talk to local models (inside the trust boundary) and external APIs. Requests may contain personal
data or credentials. A router that "tries the next provider" on failure is convenient — and, for sensitive content,
is precisely how data ends up at a third party during an outage.

## Decision
Every request has an *effective* sensitivity (`public`, `internal`, `sensitive`; `auto` classifies from the content).

- `sensitive` → only `LOCAL` providers are eligible. If none is healthy the call **fails** with a typed error.
- `internal` → external providers allowed, but only after reversible pseudonymisation; the answer is re-hydrated locally.
- `public` → sent as-is.
- Each provider has its own circuit breaker; an open breaker is skipped instead of waited on.
- Every attempt is recorded (`ok`, `error`, `timeout`, `circuit_open`, `skipped_sensitive`) and returned/metered.

## Consequences
- (+) A provider outage can degrade availability but not confidentiality.
- (+) The failure mode is explicit and testable (`NoEligibleProvider` vs `AllProvidersFailed`).
- (−) Sensitive workloads need a local model to be available at all. The RAG layer mitigates this with an extractive
  fallback that never leaves the process.
- (−) `auto` classification is only as good as the detectors; callers that *know* the data class should say so.
