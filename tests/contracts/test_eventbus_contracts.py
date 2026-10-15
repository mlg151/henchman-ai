"""Contract tests for the EventBus pub/sub boundary.

The EventBus is the central inter-component communication channel, wired
through four subsystems: Orchestrator, AgentPool, REPL, and core_init.
These tests lock down the structural and behavioral contract before any
consumer commits to publish/subscribe expectations.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

import pytest

from henchman.core.eventbus import EventBus
from henchman.core.events import AgentEvent, EventType

# ===========================================================================
# Contract Definition: EventBusProtocol
# ===========================================================================


@runtime_checkable
class EventBusProtocol(Protocol):
    """Contract for the in-process pub/sub event bus.

    Invariants
    ----------
    1. **Subscription ordering**: Handlers are called in the order they
       were subscribed for a given event type.
    2. **Error isolation**: A handler that raises does NOT prevent
       subsequent handlers for the same event from executing.
    3. **Missing-event safety**: Publishing an event type with zero
       subscribers is a no-op (no error raised).
    4. **Idempotent subscribe**: Subscribing the same handler multiple
       times registers it multiple times (each subscription results in
       one invocation on publish).
    5. **Payload passthrough**: The exact AgentEvent object passed to
       ``publish()`` is forwarded to each handler (no copies or
       transformations).
    """

    async def subscribe(self, event_type: EventType, handler: Callable[[AgentEvent], Any]) -> str:
        """Register a handler for *event_type*.

        Handlers are called in subscription order when the event is
        published.
        """
        ...

    async def publish(self, event: AgentEvent) -> None:
        """Deliver *event* to every handler registered for its type.

        If no handlers are registered, this is a no-op.
        Handlers are called in subscription order.
        """
        ...


# ===========================================================================
# Structural Contract: EventBus satisfies EventBusProtocol
# ===========================================================================


@pytest.mark.anyio
class TestEventBusStructuralContract:
    """The concrete EventBus must satisfy the EventBusProtocol."""

    async def test_eventbus_is_runtime_checkable(self) -> None:
        """EventBus should pass isinstance check against EventBusProtocol."""
        bus = EventBus()
        assert isinstance(bus, EventBusProtocol), "EventBus must satisfy EventBusProtocol"

    async def test_eventbus_exposes_subscribe_method(self) -> None:
        """EventBus.subscribe must match the protocol signature."""
        bus = EventBus()
        assert callable(bus.subscribe)

    async def test_eventbus_exposes_publish_method(self) -> None:
        """EventBus.publish must match the protocol signature."""
        bus = EventBus()
        assert callable(bus.publish)


# ===========================================================================
# Behavioral Contract: Invariant 1 — Subscription Ordering
# ===========================================================================


@pytest.mark.anyio
class TestEventBusSubscriptionOrdering:
    """Handlers must be called in subscription order."""

    async def test_handlers_called_in_subscription_order(self) -> None:
        """First subscribed, first called."""
        bus = EventBus()
        calls: list[str] = []

        def handler_a(_event: AgentEvent) -> None:
            calls.append("a")

        def handler_b(_event: AgentEvent) -> None:
            calls.append("b")

        def handler_c(_event: AgentEvent) -> None:
            calls.append("c")

        await bus.subscribe(EventType.CONTENT, handler_a)
        await bus.subscribe(EventType.CONTENT, handler_b)
        await bus.subscribe(EventType.CONTENT, handler_c)

        await bus.publish(AgentEvent(type=EventType.CONTENT, data={"data": 1}))

        assert calls == ["a", "b", "c"], f"Expected ['a', 'b', 'c'], got {calls}"

    async def test_subscription_order_preserved_across_multiple_publishes(self) -> None:
        """Ordering must be stable across multiple publish calls."""
        bus = EventBus()
        calls: list[str] = []

        await bus.subscribe(EventType.CONTENT, lambda _: calls.append("x"))
        await bus.subscribe(EventType.CONTENT, lambda _: calls.append("y"))

        await bus.publish(AgentEvent(type=EventType.CONTENT, data={}))  # first publish
        await bus.publish(AgentEvent(type=EventType.CONTENT, data={}))  # second publish

        assert calls == ["x", "y", "x", "y"], f"Expected ['x', 'y', 'x', 'y'], got {calls}"


# ===========================================================================
# Behavioral Contract: Invariant 2 — Error Isolation
# ===========================================================================


@pytest.mark.anyio
class TestEventBusErrorIsolation:
    """A failing handler must not prevent subsequent handlers from running."""

    async def test_handler_exception_does_not_block_other_handlers(self) -> None:
        """Subsequent handlers still execute after a handler raises."""
        bus = EventBus()
        called: list[str] = []

        def failing_handler(_event: AgentEvent) -> None:
            called.append("fail")
            raise RuntimeError("boom")

        def ok_handler(_event: AgentEvent) -> None:
            called.append("ok")

        await bus.subscribe(EventType.CONTENT, failing_handler)
        await bus.subscribe(EventType.CONTENT, ok_handler)

        # publish must not raise, and both handlers must be called
        await bus.publish(AgentEvent(type=EventType.CONTENT, data={}))

        assert called == ["fail", "ok"], f"Expected ['fail', 'ok'], got {called}"

    async def test_multiple_failing_handlers_isolated(self) -> None:
        """Each handler's exception is isolated from others."""
        bus = EventBus()
        called: list[str] = []

        def fail_a(_event: AgentEvent) -> None:
            called.append("a")
            raise RuntimeError("a")

        def fail_b(_event: AgentEvent) -> None:
            called.append("b")
            raise ValueError("b")

        await bus.subscribe(EventType.CONTENT, fail_a)
        await bus.subscribe(EventType.CONTENT, fail_b)
        await bus.subscribe(EventType.CONTENT, lambda _: called.append("c"))

        await bus.publish(AgentEvent(type=EventType.CONTENT, data={}))
        assert called == ["a", "b", "c"], f"Expected ['a', 'b', 'c'], got {called}"


# ===========================================================================
# Behavioral Contract: Invariant 3 — Missing-Event Safety
# ===========================================================================


@pytest.mark.anyio
class TestEventBusMissingEventSafety:
    """Publishing with no subscribers must be a no-op."""

    async def test_publish_with_no_subscribers_is_noop(self) -> None:
        """No error, no side effects."""
        bus = EventBus()
        # Must not raise — publish an event type with no subscribers
        await bus.publish(AgentEvent(type=EventType.ERROR, data={"data": 42}))

    async def test_publish_after_event_name_has_no_subscribers(self) -> None:
        """Event types are independent — subscribing to A doesn't affect B."""
        bus = EventBus()
        events_received: list[str] = []

        await bus.subscribe(EventType.AGENT_STARTED, lambda _: events_received.append("a"))
        # Different event type, no subscribers
        await bus.publish(AgentEvent(type=EventType.CONTENT, data={"data": 1}))

        assert events_received == [], (
            f"Handler for AGENT_STARTED should not be called, got {events_received}"
        )


# ===========================================================================
# Behavioral Contract: Invariant 4 — Idempotent Subscribe
# ===========================================================================


@pytest.mark.anyio
class TestEventBusIdempotentSubscribe:
    """Subscribing the same handler multiple times registers multiple invocations."""

    async def test_duplicate_subscription_calls_handler_twice(self) -> None:
        """Each subscribe call results in one invocation on publish."""
        bus = EventBus()
        count = [0]

        def counter(_event: AgentEvent) -> None:
            count[0] += 1

        await bus.subscribe(EventType.CONTENT, counter)
        await bus.subscribe(EventType.CONTENT, counter)  # same handler, second subscription
        await bus.publish(AgentEvent(type=EventType.CONTENT, data={}))

        assert count[0] == 2, f"Expected handler called 2 times, got {count[0]}"

    async def test_different_handlers_same_event_isolated(self) -> None:
        """Multiple distinct handlers each receive the event."""
        bus = EventBus()
        results: set[str] = set()

        await bus.subscribe(EventType.CONTENT, lambda _: results.add("h1"))
        await bus.subscribe(EventType.CONTENT, lambda _: results.add("h2"))
        await bus.subscribe(EventType.CONTENT, lambda _: results.add("h3"))

        await bus.publish(AgentEvent(type=EventType.CONTENT, data={}))
        assert results == {"h1", "h2", "h3"}, f"Expected {{'h1', 'h2', 'h3'}}, got {results}"


# ===========================================================================
# Behavioral Contract: Invariant 5 — Payload Passthrough
# ===========================================================================


@pytest.mark.anyio
class TestEventBusPayloadPassthrough:
    """The exact event object is forwarded to each handler."""

    async def test_payload_is_passed_by_reference(self) -> None:
        """The same object reference is delivered to all handlers."""
        bus = EventBus()
        received: list[AgentEvent] = []

        await bus.subscribe(EventType.CONTENT, lambda e: received.append(e))
        await bus.subscribe(EventType.CONTENT, lambda e: received.append(e))

        event = AgentEvent(type=EventType.CONTENT, data={"key": "value"})
        await bus.publish(event)

        assert len(received) == 2
        assert received[0] is received[1] is event, (
            "Event must be passed by reference (same object)"
        )

    async def test_payload_content_is_preserved(self) -> None:
        """The payload content is not modified during delivery."""
        bus = EventBus()
        received: list[AgentEvent] = []

        await bus.subscribe(EventType.CONTENT, lambda e: received.append(e))

        event = AgentEvent(type=EventType.CONTENT, data={"nested": {"deep": [1, 2, 3]}, "flag": True, "text": "hello"})
        await bus.publish(event)

        assert received[0] == event
        assert received[0] is event


# ===========================================================================
# Behavioral Contract: Event Type Independence
# ===========================================================================


@pytest.mark.anyio
class TestEventBusEventNameIndependence:
    """Event types are namespaced — handlers for one type are not called for another."""

    async def test_handlers_only_receive_matching_events(self) -> None:
        """Handler for AGENT_STARTED is not called when CONTENT is published."""
        calls: dict[str, int] = {}

        bus = EventBus()
        await bus.subscribe(EventType.AGENT_STARTED, lambda _: calls.__setitem__("a", calls.get("a", 0) + 1))
        await bus.subscribe(EventType.CONTENT, lambda _: calls.__setitem__("b", calls.get("b", 0) + 1))
        await bus.publish(AgentEvent(type=EventType.AGENT_STARTED, data={}))

        assert calls.get("a") == 1, (
            f"Handler for AGENT_STARTED should be called once, got {calls.get('a')}"
        )
        assert calls.get("b") is None, (
            f"Handler for CONTENT should NOT be called, got {calls.get('b')}"
        )
