"""Idempotency claims: "have I already accepted this event id?"."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol

from redis.asyncio import Redis


class IdempotencyStore(Protocol):
    async def claim(self, key: str, ttl_seconds: int) -> bool:
        """Atomically reserve ``key``. True for the first caller, False for duplicates."""

    async def release(self, key: str) -> None:
        """Give the claim back (used when processing failed so the sender may retry)."""

    async def close(self) -> None: ...


class InMemoryIdempotencyStore:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._expires: dict[str, float] = {}

    async def claim(self, key: str, ttl_seconds: int) -> bool:
        now = self._clock()
        expiry = self._expires.get(key)
        if expiry is not None and expiry > now:
            return False
        self._expires[key] = now + ttl_seconds
        return True

    async def release(self, key: str) -> None:
        self._expires.pop(key, None)

    async def close(self) -> None:
        return None


class RedisIdempotencyStore:
    def __init__(self, url: str, *, client: Redis | None = None) -> None:
        self._redis: Redis = client or Redis.from_url(url, decode_responses=True)

    async def claim(self, key: str, ttl_seconds: int) -> bool:
        # SET NX EX is a single atomic command: no race between "check" and "set".
        return bool(await self._redis.set(f"idem:{key}", "1", nx=True, ex=ttl_seconds))

    async def release(self, key: str) -> None:
        await self._redis.delete(f"idem:{key}")

    async def close(self) -> None:
        await self._redis.aclose()
