# ADR 0004: Signed, timestamped, de-duplicated webhooks

Status: Accepted

## Context
`POST /v1/webhooks/{source}` accepts events from another system. Anyone who can reach the URL can send a request, so the
receiver must establish who sent it, that it was not edited, that it is not an old capture, and that a retry of an event
it already handled is not handled twice. It must do that without telling an attacker which check failed.

## Decision
- The signature is `HMAC-SHA256(secret, "<t>." + raw body)`, sent as `t=<unix seconds>,v1=<hex>[,v1=<hex>...]`. The
  timestamp is inside the MAC, so editing `t` breaks the signature.
- A tolerance window (default 300 s, both directions) bounds how long a captured request stays valid.
- The event id is claimed with an atomic `SET NX EX` (Redis) or its in-memory equivalent. That closes the gap *inside*
  the tolerance window, where the signature alone cannot help.
- Several `v1` values and several configured secrets are accepted, and every pair is compared without early exit, so a
  secret can be rotated without downtime.
- Every failure reason (`missing`, `malformed`, `expired`, `future`, `mismatch`) is counted separately in metrics but
  answered with one generic 401.
- The claim is released only on a **transient** failure. A deterministic rejection (an `AppError` from the handler)
  keeps it, because retrying the same event cannot succeed and the sender would retry forever.
- With no secret configured, verification fails closed.

## Rejected alternatives
- **A shared bearer token in a header.** Replayable and says nothing about the body.
- **Timestamp outside the MAC** (a separate header). An old capture could be refreshed by editing the header.
- **Check-then-set de-duplication.** Two concurrent deliveries both pass the check; the claim has to be one atomic command.
- **Distinct error messages per reason.** Useful to the sender while debugging, and equally useful to an attacker
  learning which check to defeat. The reasons live in metrics instead.
- **Release the claim on every error.** A malformed event would be redelivered forever.

## Consequences
- (+) Replay, tampering and double delivery each have a named defence and a test (`tests/test_webhooks.py`, and the
  Redis path in `tests/test_integration_stores.py`).
- (−) Sender and receiver clocks must agree within the tolerance window.
- (−) De-duplication state lives in Redis; a Redis outage with the Redis store configured fails the request rather than
  risking a double handle.
