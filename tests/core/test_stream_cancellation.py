"""Interrupted streams release resources and never announce successful completion."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from henchman.core.agent import Agent
from henchman.core.agent_streaming import StreamContext, StreamState, generate_stream_events
from henchman.core.events import EventType
from henchman.providers.base import (
    FinishReason,
    Message,
    ModelProvider,
    StreamChunk,
    ToolDeclaration,
)


class InterruptibleProvider(ModelProvider):
    """Expose resource lifetime and a deterministic cancellation point."""

    name = "interruptible"

    def __init__(self) -> None:
        self.waiting = asyncio.Event()
        self.closed = False

    async def chat_completion_stream(
        self, messages: list[Message], tools: list[ToolDeclaration] | None = None, **kwargs: object,
    ) -> AsyncIterator[StreamChunk]:
        try:
            yield StreamChunk(content="Partial answer")
            self.waiting.set()
            await asyncio.Event().wait()
        finally:
            self.closed = True


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["events", "run", "continue"])
async def test_closing_partial_stream_releases_provider(surface: str) -> None:
    provider = InterruptibleProvider()
    agent = Agent(provider=provider)
    if surface == "events":
        stream = generate_stream_events(
            StreamContext(provider, [], agent.messages, []), StreamState(), compacted=False,
        )
    elif surface == "run":
        stream = agent.run("Start")
    else:
        stream = agent.continue_with_tool_results()

    first = await anext(stream)
    assert first.type == EventType.CONTENT
    await stream.aclose()

    assert provider.closed, "Provider resources must close before the consumer returns"
    assert agent.messages[-1].content == "Partial answer\n\n[Response interrupted.]"
    assert agent.messages[-1].tool_calls is None


@pytest.mark.asyncio
async def test_continuation_reports_final_response_completion() -> None:
    """A tool-driven response must expose completion and usage to its consumer."""
    class CompletedProvider(ModelProvider):
        name = "completed"

        async def chat_completion_stream(self, messages, tools=None, **kwargs):
            yield StreamChunk(
                content="Tests pass.", finish_reason=FinishReason.STOP,
                usage={"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
            )

    agent = Agent(provider=CompletedProvider())
    events = [event async for event in agent.continue_with_tool_results()]

    assert [event.type for event in events] == [EventType.CONTENT, EventType.FINISHED]
    assert events[-1].data == {
        "finish_reason": "stop",
        "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
    }


@pytest.mark.asyncio
async def test_failed_continuation_does_not_reuse_previous_response_usage(monkeypatch) -> None:
    agent = Agent(provider=InterruptibleProvider())
    agent._last_stream_state = StreamState(
        finish_reason=FinishReason.STOP,
        usage={"total_tokens": 123},
    )

    def fail_preparation():
        raise ValueError("Unable to prepare context")

    monkeypatch.setattr(agent, "get_messages_for_api", fail_preparation)
    events = [event async for event in agent.continue_with_tool_results()]

    assert [event.type for event in events] == [EventType.ERROR, EventType.FINISHED]
    assert not isinstance(events[-1].data, dict) or "usage" not in events[-1].data


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["events", "run", "continue"])
async def test_task_cancellation_propagates_without_finished_event(surface: str) -> None:
    provider = InterruptibleProvider()
    agent = Agent(provider=provider)
    if surface == "events":
        stream = generate_stream_events(
            StreamContext(provider, [], agent.messages, []), StreamState(), compacted=False,
        )
    elif surface == "run":
        stream = agent.run("Start")
    else:
        stream = agent.continue_with_tool_results()
    events = []

    async def consume() -> None:
        async for event in stream:
            events.append(event)

    task = asyncio.create_task(consume())
    await asyncio.wait_for(provider.waiting.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert provider.closed
    assert [event.type for event in events] == [EventType.CONTENT]
    assert agent.messages[-1].content == "Partial answer\n\n[Response interrupted.]"
    assert agent.messages[-1].tool_calls is None


@pytest.mark.asyncio
async def test_close_after_thought_preserves_reasoning_without_executable_calls() -> None:
    class ThinkingProvider(ModelProvider):
        name = "thinking"

        async def chat_completion_stream(self, messages, tools=None, **kwargs):
            yield StreamChunk(thinking="Partial reasoning")
            await asyncio.Event().wait()

    agent = Agent(provider=ThinkingProvider())
    stream = agent.run("Work")
    assert (await anext(stream)).type == EventType.THOUGHT
    await stream.aclose()

    assert agent.messages[-1].content == "[Response interrupted.]"
    assert agent.messages[-1].reasoning_content == "Partial reasoning"
    assert agent.messages[-1].tool_calls is None


@pytest.mark.asyncio
@pytest.mark.parametrize("interrupt", ["cancel", "close"])
async def test_cleanup_failure_does_not_replace_interruption(interrupt: str, caplog) -> None:
    class FailingCleanupIterator:
        def __init__(self):
            self.started = False
            self.waiting = asyncio.Event()

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self.started:
                self.started = True
                return StreamChunk(content="Partial answer")
            self.waiting.set()
            await asyncio.Event().wait()

        async def aclose(self):
            raise RuntimeError("Transport cleanup failed")

    class ResourceProvider(ModelProvider):
        name = "resource"

        def chat_completion_stream(self, messages, tools=None, **kwargs):
            return resource

    resource = FailingCleanupIterator()
    stream = Agent(provider=ResourceProvider()).run("Start")
    assert (await anext(stream)).type == EventType.CONTENT
    if interrupt == "close":
        await stream.aclose()
    else:
        task = asyncio.create_task(anext(stream))
        await asyncio.wait_for(resource.waiting.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert "Transport cleanup failed" in caplog.text


@pytest.mark.asyncio
async def test_provider_iterator_without_close_remains_supported() -> None:
    class PlainIterator:
        def __init__(self):
            self.finished = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.finished:
                raise StopAsyncIteration
            self.finished = True
            return StreamChunk(content="Complete", finish_reason=FinishReason.STOP)

    class IteratorProvider(ModelProvider):
        name = "iterator"

        def chat_completion_stream(self, messages, tools=None, **kwargs):
            return PlainIterator()

    agent = Agent(provider=IteratorProvider())
    events = [event async for event in agent.run("Start")]
    assert [event.type for event in events] == [EventType.CONTENT, EventType.FINISHED]
    assert agent.messages[-1].content == "Complete"
