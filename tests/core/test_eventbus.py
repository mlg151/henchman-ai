import pytest

from henchman.core.eventbus import EventBus
from henchman.core.events import AgentEvent, EventType


@pytest.mark.asyncio
async def test_eventbus_subscribe_publish():
    bus = EventBus()
    received = []

    async def handler(event):
        received.append(event)

    await bus.subscribe(EventType.CONTENT, handler)

    event = AgentEvent(type=EventType.CONTENT, data="test")
    await bus.publish(event)

    assert len(received) == 1
    assert received[0] == event


@pytest.mark.asyncio
async def test_eventbus_subscribe_all():
    bus = EventBus()
    received = []

    async def handler(event):
        received.append(event)

    await bus.subscribe_all(handler)

    event1 = AgentEvent(type=EventType.CONTENT, data="test1")
    event2 = AgentEvent(type=EventType.ERROR, data="test2")

    await bus.publish(event1)
    await bus.publish(event2)

    assert len(received) == 2
    assert received[0] == event1
    assert received[1] == event2


@pytest.mark.asyncio
async def test_eventbus_unsubscribe():
    bus = EventBus()
    received = []

    async def handler(event):
        received.append(event)

    sub_id = await bus.subscribe(EventType.CONTENT, handler)
    await bus.unsubscribe(sub_id)

    event = AgentEvent(type=EventType.CONTENT, data="test")
    await bus.publish(event)

    assert len(received) == 0


@pytest.mark.asyncio
async def test_eventbus_history():
    bus = EventBus()

    event1 = AgentEvent(type=EventType.CONTENT, data="test1", source_agent="agent1")
    event2 = AgentEvent(type=EventType.ERROR, data="test2", source_agent="agent2")

    await bus.publish(event1)
    await bus.publish(event2)

    history = await bus.history()
    assert len(history) == 2
    assert history[0] == event2  # Newest first
    assert history[1] == event1

    # Filter by type
    history_content = await bus.history(event_type=EventType.CONTENT)
    assert len(history_content) == 1
    assert history_content[0] == event1

    # Filter by agent
    history_agent2 = await bus.history(agent_id="agent2")
    assert len(history_agent2) == 1
    assert history_agent2[0] == event2


@pytest.mark.asyncio
async def test_eventbus_error_isolation():
    bus = EventBus()
    received = []

    async def failing_handler(_event):  # noqa: ARG001
        raise RuntimeError("Fail")

    async def successful_handler(event):
        received.append(event)

    await bus.subscribe_all(failing_handler)
    await bus.subscribe_all(successful_handler)

    event = AgentEvent(type=EventType.CONTENT, data="test")
    await bus.publish(event)

    assert len(received) == 1
    assert received[0] == event


@pytest.mark.asyncio
async def test_eventbus_sync_handler():
    bus = EventBus()
    received = []

    def sync_handler(event):
        received.append(event)

    await bus.subscribe_all(sync_handler)

    event = AgentEvent(type=EventType.CONTENT, data="test")
    await bus.publish(event)

    assert len(received) == 1
    assert received[0] == event
