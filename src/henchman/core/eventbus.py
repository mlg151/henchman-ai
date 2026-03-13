"""EventBus module for Henchman-AI.

This module provides a thread-safe, event-driven publish/subscribe system for agent communication.
The EventBus enables decoupled communication between different components of the multi-agent system,
allowing agents, tools, and UI components to communicate via events without direct dependencies.

Key Features:
- Thread-safe operations with anyio locks
- Event history tracking with configurable limits
- Type-safe event subscriptions with EventType filtering
- Support for both async and sync event handlers
- Unique subscription IDs for precise handler management

Usage Example:
    ```python
    from henchman.core.eventbus import EventBus
    from henchman.core.events import AgentEvent, EventType

    async def handle_content(event: AgentEvent) -> None:
        print(f"Content: {event.data}")

    bus = EventBus()
    sub_id = await bus.subscribe(EventType.CONTENT, handle_content)
    await bus.publish(AgentEvent(EventType.CONTENT, "Hello, world!"))
    ```
"""

import uuid
from collections import deque
from collections.abc import Callable
from typing import Any

import anyio

from henchman.core.events import AgentEvent, EventType


class EventBus:
    """A thread-safe, event-driven pub/sub system for agent communication."""

    def __init__(self, history_limit: int = 1000) -> None:
        """Initialize the EventBus.

        Args:
            history_limit: Maximum number of events to keep in history.
        """
        self._handlers: dict[str, tuple[EventType | None, Callable[[AgentEvent], Any]]] = {}
        self._history: deque[AgentEvent] = deque(maxlen=history_limit)
        self._lock = anyio.Lock()

    async def subscribe(self, event_type: EventType, handler: Callable[[AgentEvent], Any]) -> str:
        """Subscribe to a specific event type.

        Args:
            event_type: The type of event to subscribe to.
            handler: Async or sync function to call when event occurs.

        Returns:
            A unique subscription ID.
        """
        async with self._lock:
            sub_id = str(uuid.uuid4())
            self._handlers[sub_id] = (event_type, handler)
            return sub_id

    async def subscribe_all(self, handler: Callable[[AgentEvent], Any]) -> str:
        """Subscribe to all event types.

        Args:
            handler: Async or sync function to call for every event.

        Returns:
            A unique subscription ID.
        """
        async with self._lock:
            sub_id = str(uuid.uuid4())
            self._handlers[sub_id] = (None, handler)
            return sub_id

    async def unsubscribe(self, subscription_id: str) -> None:
        """Remove a subscription.

        Args:
            subscription_id: The ID returned from subscribe().

        Returns:
            None
        """
        async with self._lock:
            self._handlers.pop(subscription_id, None)

    async def publish(self, event: AgentEvent) -> None:
        """Publish an event to all matching subscribers.

        Args:
            event: The event to publish.

        Returns:
            None
        """
        async with self._lock:
            self._history.append(event)
            handlers_to_call = [
                handler
                for etype, handler in self._handlers.values()
                if etype is None or etype == event.type
            ]

        # Dispatch handlers outside the lock to avoid deadlocks and blocking
        for handler in handlers_to_call:
            try:
                import inspect  # noqa: PLC0415

                if inspect.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception:  # noqa: BLE001, PERF203
                # Error isolation: log but don't stop other handlers
                pass

    async def history(
        self,
        event_type: EventType | None = None,
        agent_id: str | None = None,
        limit: int = 100,
    ) -> list[AgentEvent]:
        """Query event history.

        Args:
            event_type: Filter by event type.
            agent_id: Filter by source agent ID.
            limit: Maximum number of events to return.

        Returns:
            List of matching events, newest first.
        """
        async with self._lock:
            results = []
            for event in reversed(self._history):
                if event_type and event.type != event_type:
                    continue
                if agent_id and event.source_agent != agent_id:
                    continue
                results.append(event)
                if len(results) >= limit:
                    break
            return results

    async def clear_history(self) -> None:
        """Clear the event history.

        Returns:
            None
        """
        async with self._lock:
            self._history.clear()
