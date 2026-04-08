"""Event system for inter-agent communication."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """Represents a pipeline event."""
    name: str
    data: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# Type alias for event handlers
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """Async pub/sub event bus for agent coordination."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}
        self._history: list[Event] = []

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        """Register a handler for an event type."""
        if event_name not in self._handlers:
            self._handlers[event_name] = []
        self._handlers[event_name].append(handler)
        logger.debug(f"Handler subscribed to '{event_name}'")

    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        """Remove a handler for an event type."""
        if event_name in self._handlers:
            self._handlers[event_name].remove(handler)

    async def emit(self, event: Event) -> None:
        """Emit an event to all subscribed handlers."""
        self._history.append(event)
        handlers = self._handlers.get(event.name, [])
        if not handlers:
            logger.debug(f"No handlers for event '{event.name}'")
            return

        logger.info(f"Emitting '{event.name}' to {len(handlers)} handler(s)")
        tasks = [handler(event) for handler in handlers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    f"Handler {handlers[i].__name__} failed on '{event.name}': {result}"
                )

    def get_history(self, event_name: str | None = None) -> list[Event]:
        """Get event history, optionally filtered by name."""
        if event_name:
            return [e for e in self._history if e.name == event_name]
        return list(self._history)
