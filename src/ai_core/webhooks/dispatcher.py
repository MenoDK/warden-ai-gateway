from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

Handler = Callable[[dict[str, Any]], Awaitable[None]]


class EventDispatcher:
    """Routes verified webhook events to registered handlers by ``type``."""

    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}

    def register(self, event_type: str, handler: Handler) -> None:
        self._handlers[event_type] = handler

    def handles(self, event_type: str) -> bool:
        return event_type in self._handlers

    async def dispatch(self, event_type: str, payload: dict[str, Any]) -> bool:
        handler = self._handlers.get(event_type)
        if handler is None:
            return False
        await handler(payload)
        return True
