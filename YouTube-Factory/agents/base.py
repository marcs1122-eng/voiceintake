"""Base agent class that all YouTube Factory agents inherit from."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

from core.events import EventBus, Event
from core.state import VideoProject


class BaseAgent(ABC):
    """Abstract base for all pipeline agents.

    Subclasses must implement `process()`. The base class provides:
    - Logging scoped to the agent name
    - Event bus integration
    - Channel config access
    - Retry logic with exponential backoff
    - Standard error handling
    """

    name: str = "base_agent"

    def __init__(self, config: dict[str, Any], event_bus: EventBus) -> None:
        self.config = config
        self.event_bus = event_bus
        self.logger = logging.getLogger(f"agent.{self.name}")

    @abstractmethod
    async def process(self, project: VideoProject, context: dict[str, Any]) -> dict[str, Any]:
        """Execute this agent's work on a video project.

        Args:
            project: The current video project state.
            context: Shared context dict (API clients, channel config, etc.)

        Returns:
            Dict of results to merge into the project or pass downstream.
        """
        ...

    async def emit(self, event_name: str, data: dict[str, Any] | None = None) -> None:
        """Emit an event from this agent."""
        await self.event_bus.emit(Event(
            name=event_name,
            source=self.name,
            data=data or {},
        ))

    def get_channel_config(self, project: VideoProject) -> dict[str, Any]:
        """Get the channel-specific config for a project."""
        channels = self.config.get("channels", {})
        return channels.get(project.channel_id, {})

    async def retry(
        self,
        coro_factory,
        max_attempts: int = 3,
        base_delay: float = 2.0,
    ) -> Any:
        """Retry an async operation with exponential backoff.

        Args:
            coro_factory: Callable that returns a new coroutine each call.
            max_attempts: Maximum number of attempts.
            base_delay: Base delay in seconds (doubles each retry).

        Returns:
            The result of the successful coroutine call.
        """
        last_error = None
        for attempt in range(max_attempts):
            try:
                return await coro_factory()
            except Exception as e:
                last_error = e
                if attempt < max_attempts - 1:
                    delay = base_delay * (2 ** attempt)
                    self.logger.warning(
                        f"[{self.name}] Attempt {attempt + 1}/{max_attempts} failed: {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
        raise last_error  # type: ignore[misc]

    def validate_project(self, project: VideoProject, required_fields: list[str]) -> bool:
        """Check that required project fields are populated."""
        for field_name in required_fields:
            value = getattr(project, field_name, None)
            if not value:
                self.logger.error(f"[{self.name}] Missing required field: {field_name}")
                return False
        return True
