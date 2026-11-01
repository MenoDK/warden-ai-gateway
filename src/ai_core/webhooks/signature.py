"""HMAC-SHA256 webhook signatures with timestamp tolerance (anti-replay).

Header format (``X-Signature``): ``t=<unix seconds>,v1=<hex>[,v1=<hex>...]``

The signed payload is ``"<t>." + raw_body``. Binding the timestamp into the MAC means an
attacker cannot refresh an old capture by editing ``t``; the tolerance window bounds how long
a captured request stays valid, and event-id de-duplication (see ``idempotency``) closes the
gap *inside* the window. Multiple ``v1`` values allow secret rotation without downtime.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from collections.abc import Sequence
from typing import Literal

Reason = Literal["missing", "malformed", "expired", "future", "mismatch"]


class SignatureError(Exception):
    def __init__(self, reason: Reason) -> None:
        super().__init__(reason)
        self.reason = reason


def _mac(secret: str, timestamp: int, body: bytes) -> str:
    return hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()


def build_signature_header(secret: str, body: bytes, *, timestamp: int | None = None) -> str:
    ts = int(time.time()) if timestamp is None else timestamp
    return f"t={ts},v1={_mac(secret, ts, body)}"


def verify_signature(
    header: str | None,
    body: bytes,
    secrets: Sequence[str],
    *,
    tolerance_seconds: int = 300,
    now: float | None = None,
) -> int:
    """Return the verified timestamp, or raise ``SignatureError``."""
    if not header:
        raise SignatureError("missing")
    if not secrets:
        raise SignatureError("mismatch")  # fail closed when nothing is configured

    timestamp: int | None = None
    candidates: list[str] = []
    for part in header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t":
            try:
                timestamp = int(value)
            except ValueError:
                raise SignatureError("malformed") from None
        elif key == "v1" and value:
            candidates.append(value)
    if timestamp is None or not candidates:
        raise SignatureError("malformed")

    current = time.time() if now is None else now
    if current - timestamp > tolerance_seconds:
        raise SignatureError("expired")
    if timestamp - current > tolerance_seconds:
        raise SignatureError("future")

    # Compare against every (secret, candidate) pair without early exit.
    matched = False
    for secret in secrets:
        expected = _mac(secret, timestamp, body)
        for candidate in candidates:
            matched |= hmac.compare_digest(expected, candidate)
    if not matched:
        raise SignatureError("mismatch")
    return timestamp
