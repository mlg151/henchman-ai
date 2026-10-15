"""Tests for BUG-023: EventBus has no unsubscribe mechanism.

Ensures EventBus.unsubscribe() properly removes handlers to prevent
permanent accumulation of subscribers.
"""

from __future__ import annotations

from henchman.core.eventbus import EventBus
from henchman.core.events import AgentEvent, EventType


class TestEventBusUnsubscribe:
    """Tests for EventBus.unsubscribe()."""

    async def test_unsubscribe_removes_handler(self) -> None:
        """After unsubscribe, the handler must not be called on publish."""
        bus = EventBus()
        calls: list[str] = []

        async def handler(_event: AgentEvent) -> None:
            calls.append("called")

        sub_id = await bus.subscribe(EventType.CONTENT, handler)
        await bus.unsubscribe(sub_id)
        await bus.publish(AgentEvent(EventType.CONTENT, "test"))

        assert calls == [], f"Handler should not have been called, got {calls}"

    async def test_unsubscribe_leaves_other_handlers(self) -> None:
        """Unsubscribing one handler must not affect other handlers for the same event."""
        bus = EventBus()
        calls: list[str] = []

        async def handler_a(_event: AgentEvent) -> None:
            calls.append("a")

        async def handler_b(_event: AgentEvent) -> None:
            calls.append("b")

        sub_a = await bus.subscribe(EventType.CONTENT, handler_a)
        await bus.subscribe(EventType.CONTENT, handler_b)
        await bus.unsubscribe(sub_a)
        await bus.publish(AgentEvent(EventType.CONTENT, "test"))

        assert calls == ["b"], f"Expected ['b'], got {calls}"

    async def test_unsubscribe_nonexistent_event_is_noop(self) -> None:
        """Unsubscribing with a nonexistent ID must not raise."""
        bus = EventBus()

        # Must not raise
        await bus.unsubscribe("nonexistent-id")

    async def test_unsubscribe_nonexistent_handler_is_noop(self) -> None:
        """Unsubscribing a handler that was never registered must not raise."""
        bus = EventBus()

        async def registered(event: AgentEvent) -> None:
            pass

        await bus.subscribe(EventType.CONTENT, registered)
        # Must not raise -- ID was never subscribed
        await bus.unsubscribe("never-registered-id")
        # Registered handler should still fire
        calls: list[str] = []
        await bus.subscribe(EventType.CONTENT, lambda _: calls.append("x"))
        await bus.publish(AgentEvent(EventType.CONTENT, "test"))
        assert len(calls) == 1

    async def test_unsubscribe_allows_resubscribe(self) -> None:
        """After unsubscribing, the handler can be re-subscribed."""
        bus = EventBus()
        calls: list[str] = []

        async def handler(_event: AgentEvent) -> None:
            calls.append("called")

        sub_id = await bus.subscribe(EventType.CONTENT, handler)
        await bus.unsubscribe(sub_id)
        await bus.subscribe(EventType.CONTENT, handler)  # Re-subscribe (new ID)
        await bus.publish(AgentEvent(EventType.CONTENT, "test"))

        assert calls == ["called"], "Handler should work after re-subscribe"

    async def test_publish_after_removing_all_handlers_is_noop(self) -> None:
        """After removing all handlers for an event, publish is a no-op."""
        bus = EventBus()

        async def handler(_event: AgentEvent) -> None:
            msg = "Should not be called"
            raise RuntimeError(msg)

        sub_id = await bus.subscribe(EventType.CONTENT, handler)
        await bus.unsubscribe(sub_id)
        # Must not raise
        await bus.publish(AgentEvent(EventType.CONTENT, "test"))
