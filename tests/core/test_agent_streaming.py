"""Tests for the agent_streaming module."""

import pytest

from henchman.core.agent_streaming import (
    StreamContext,
    StreamState,
    generate_stream_events,
)
from henchman.core.events import EventType
from henchman.providers.base import FinishReason, ModelProvider, StreamChunk, ToolCall


class MockProvider(ModelProvider):
    """A provider that yields pre-defined chunks."""

    def __init__(self, chunks: list[StreamChunk]):
        self.chunks = chunks
        self._name = "mock"

    @property
    def name(self) -> str:
        return self._name

    async def chat_completion_stream(self, messages, tools=None, **kwargs):
        for chunk in self.chunks:
            yield chunk


@pytest.mark.asyncio
async def test_generate_stream_events_accumulates_content():
    """Test that content is correctly accumulated in StreamState."""
    chunks = [
        StreamChunk(content="Hello"),
        StreamChunk(content=" "),
        StreamChunk(content="World"),
        StreamChunk(finish_reason=FinishReason.STOP),
    ]
    provider = MockProvider(chunks)
    context = StreamContext(
        provider=provider,
        api_messages=[],
        history=[],
        tool_declarations=[],
    )
    state = StreamState()

    events = []
    async for event in generate_stream_events(context, state, compacted=False):
        events.append(event)

    assert state.content == "Hello World"
    assert state.finish_reason == FinishReason.STOP

    # Check events
    content_events = [e for e in events if e.type == EventType.CONTENT]
    assert len(content_events) == 3
    assert content_events[0].data == "Hello"
    assert content_events[1].data == " "
    assert content_events[2].data == "World"

    finished_event = events[-1]
    assert finished_event.type == EventType.FINISHED
    assert finished_event.data == "stop"

    # Check history update
    assert len(context.history) == 1
    assert context.history[0].role == "assistant"
    assert context.history[0].content == "Hello World"


@pytest.mark.asyncio
async def test_generate_stream_events_handles_thinking():
    """Test that 'thinking' content is correctly handled."""
    chunks = [
        StreamChunk(thinking="I am thinking..."),
        StreamChunk(thinking="\nStill thinking."),
        StreamChunk(content="Finally, an answer."),
        StreamChunk(finish_reason=FinishReason.STOP),
    ]
    provider = MockProvider(chunks)
    context = StreamContext(
        provider=provider,
        api_messages=[],
        history=[],
        tool_declarations=[],
    )
    state = StreamState()

    events = []
    async for event in generate_stream_events(context, state, compacted=False):
        events.append(event)

    assert state.thinking == "I am thinking...\nStill thinking."
    assert state.content == "Finally, an answer."

    thought_events = [e for e in events if e.type == EventType.THOUGHT]
    assert len(thought_events) == 2

    # Check history update - reasoning_content should be set
    assert len(context.history) == 1
    assert context.history[0].reasoning_content == "I am thinking...\nStill thinking."
    assert context.history[0].content == "Finally, an answer."


@pytest.mark.asyncio
async def test_generate_stream_events_handles_tool_calls():
    """Test that tool calls are correctly accumulated and emitted."""
    tc1 = ToolCall(id="call_1", name="get_weather", arguments={"city": "London"})
    tc2 = ToolCall(id="call_2", name="get_time", arguments={"city": "Paris"})

    chunks = [
        StreamChunk(tool_calls=[tc1]),
        StreamChunk(tool_calls=[tc2]),
        StreamChunk(finish_reason=FinishReason.TOOL_CALLS),
    ]
    provider = MockProvider(chunks)
    context = StreamContext(
        provider=provider,
        api_messages=[],
        history=[],
        tool_declarations=[],
    )
    state = StreamState()

    events = []
    async for event in generate_stream_events(context, state, compacted=False):
        events.append(event)

    assert state.tool_calls == [tc1, tc2]
    assert state.finish_reason == FinishReason.TOOL_CALLS

    tc_events = [e for e in events if e.type == EventType.TOOL_CALL_REQUEST]
    assert len(tc_events) == 2
    assert tc_events[0].data.id == tc1.id
    assert tc_events[1].data.id == tc2.id

    # Check history update - tool_calls should be set
    assert len(context.history) == 1
    assert context.history[0].tool_calls == [tc1, tc2]


@pytest.mark.asyncio
async def test_generate_stream_events_handles_usage_and_finish_reason():
    """Test that usage and finish_reason are correctly captured."""
    usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    chunks = [
        StreamChunk(content="The end."),
        StreamChunk(finish_reason=FinishReason.STOP, usage=usage),
    ]
    provider = MockProvider(chunks)
    context = StreamContext(
        provider=provider,
        api_messages=[],
        history=[],
        tool_declarations=[],
    )
    state = StreamState()

    events = []
    async for event in generate_stream_events(context, state, compacted=False):
        events.append(event)

    assert state.finish_reason == FinishReason.STOP
    assert state.usage == usage

    finished_event = events[-1]
    assert finished_event.type == EventType.FINISHED
    assert isinstance(finished_event.data, dict)
    assert finished_event.data["finish_reason"] == "stop"
    assert finished_event.data["usage"] == usage


@pytest.mark.asyncio
async def test_generate_stream_events_handles_mixed_content_and_tools():
    """Test that a single chunk can contain both content and tools."""
    tc = ToolCall(id="call_1", name="get_weather", arguments={"city": "London"})
    chunks = [
        StreamChunk(content="Thinking about the weather...", tool_calls=[tc]),
        StreamChunk(finish_reason=FinishReason.TOOL_CALLS),
    ]
    provider = MockProvider(chunks)
    context = StreamContext(
        provider=provider,
        api_messages=[],
        history=[],
        tool_declarations=[],
    )
    state = StreamState()

    events = []
    async for event in generate_stream_events(context, state, compacted=False):
        events.append(event)

    assert state.content == "Thinking about the weather..."
    assert state.tool_calls == [tc]

    content_events = [e for e in events if e.type == EventType.CONTENT]
    tc_events = [e for e in events if e.type == EventType.TOOL_CALL_REQUEST]

    assert len(content_events) == 1
    assert len(tc_events) == 1
