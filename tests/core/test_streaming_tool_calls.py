"""Test for streaming tool call accumulation before finish_reason."""

import pytest

from henchman.core.agent import Agent
from henchman.core.events import EventType
from henchman.providers.base import FinishReason, StreamChunk, ToolCall
from henchman.tools.registry import ToolRegistry


class MockStreamingProvider:
    """Mock provider that streams tool calls before sending finish_reason."""

    def __init__(self, chunks: list[StreamChunk]):
        self.chunks = chunks
        self.call_count = 0

    async def chat_completion_stream(self, messages, tools=None):
        self.call_count += 1
        for chunk in self.chunks:
            yield chunk


class TestStreamingToolCallAccumulation:
    """Tests for proper tool call accumulation during streaming."""

    @pytest.mark.anyio
    async def test_tool_calls_accumulated_before_finish_reason(self):
        """Test that tool calls are accumulated and only yielded on finish_reason."""
        # Simulate provider streaming tool calls in separate chunks
        chunks = [
            # First chunk has a tool call but no finish reason
            StreamChunk(
                content=None,
                tool_calls=[ToolCall(id="call_1", name="tool_a", arguments={"x": 1})],
                finish_reason=None,
            ),
            # Second chunk has another tool call and still no finish reason
            StreamChunk(
                content=None,
                tool_calls=[ToolCall(id="call_2", name="tool_b", arguments={"y": 2})],
                finish_reason=None,
            ),
            # Final chunk has finish reason but no tool calls
            StreamChunk(
                content=None,
                tool_calls=None,
                finish_reason=FinishReason.TOOL_CALLS,
            ),
        ]

        provider = MockStreamingProvider(chunks)
        registry = ToolRegistry()
        agent = Agent(provider=provider, tool_registry=registry)

        # Collect events
        events = []
        async for event in agent.run("Test"):
            events.append(event)

        # Should have 2 TOOL_CALL_REQUEST events (accumulated from all chunks)
        tool_call_events = [e for e in events if e.type == EventType.TOOL_CALL_REQUEST]
        assert len(tool_call_events) == 2, f"Expected 2 tool calls, got {len(tool_call_events)}"

        # The tool calls should have the correct IDs
        tool_call_ids = [e.data.id for e in tool_call_events]
        assert "call_1" in tool_call_ids
        assert "call_2" in tool_call_ids

        # Agent messages should include the assistant message with both tool calls
        assistant_messages = [m for m in agent.messages if m.role == "assistant"]
        assert len(assistant_messages) == 1
        assert len(assistant_messages[0].tool_calls) == 2

    @pytest.mark.anyio
    async def test_content_streamed_as_it_comes(self):
        """Test that content is still streamed incrementally."""
        chunks = [
            StreamChunk(content="Hello ", finish_reason=None),
            StreamChunk(content="world", finish_reason=None),
            StreamChunk(content="!", finish_reason=FinishReason.STOP),
        ]

        provider = MockStreamingProvider(chunks)
        agent = Agent(provider=provider)

        events = []
        async for event in agent.run("Test"):
            events.append(event)

        # Should have content events for each streamed chunk
        content_events = [e for e in events if e.type == EventType.CONTENT]
        # The streaming chunks yield individual content events
        # Plus potentially one final one with accumulated content
        assert len(content_events) >= 2, (
            f"Expected at least 2 content events, got {len(content_events)}"
        )

    @pytest.mark.anyio
    async def test_tool_results_match_after_streaming(self):
        """Test that tool results can be properly submitted after streaming tool calls."""
        chunks = [
            StreamChunk(
                content=None,
                tool_calls=[ToolCall(id="stream_call", name="test_tool", arguments={})],
                finish_reason=None,
            ),
            StreamChunk(
                content=None,
                tool_calls=None,
                finish_reason=FinishReason.TOOL_CALLS,
            ),
        ]

        provider = MockStreamingProvider(chunks)
        agent = Agent(provider=provider)

        # Run agent to get tool call
        async for _ in agent.run("Test"):
            pass

        # Submit tool result with matching ID
        agent.submit_tool_result("stream_call", "result")

        # Verify the message sequence is valid
        from henchman.utils.validation import validate_message_sequence

        # This should not raise
        validate_message_sequence(agent.messages)

        # Verify structure
        assert agent.messages[-1].role == "tool"
        assert agent.messages[-1].tool_call_id == "stream_call"
        assert agent.messages[-2].role == "assistant"
        assert agent.messages[-2].tool_calls[0].id == "stream_call"
