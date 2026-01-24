"""Tests for the core Agent class."""

from unittest.mock import MagicMock

import pytest

from henchman.core.agent import Agent
from henchman.core.events import EventType
from henchman.providers.base import (
    FinishReason,
    Message,
    ModelProvider,
    StreamChunk,
    ToolCall,
    ToolDeclaration,
)


class TestAgentInitialization:
    """Tests for Agent initialization."""

    def test_agent_creation_minimal(self) -> None:
        """Test creating an agent with minimal arguments."""
        provider = MagicMock(spec=ModelProvider)
        agent = Agent(provider=provider)
        assert agent.provider is provider
        assert agent.history == []
        assert agent.system_prompt == ""

    def test_agent_creation_with_system_prompt(self) -> None:
        """Test creating an agent with a system prompt."""
        provider = MagicMock(spec=ModelProvider)
        agent = Agent(provider=provider, system_prompt="You are helpful.")
        assert agent.system_prompt == "You are helpful."

    def test_agent_creation_with_tools(self) -> None:
        """Test creating an agent with tool declarations."""
        provider = MagicMock(spec=ModelProvider)
        tools = [
            ToolDeclaration(
                name="read_file",
                description="Read a file",
                parameters={"type": "object", "properties": {}},
            )
        ]
        agent = Agent(provider=provider, tools=tools)
        assert len(agent.tools) == 1
        assert agent.tools[0].name == "read_file"


class TestAgentHistory:
    """Tests for Agent conversation history management."""

    def test_history_starts_empty(self) -> None:
        """Test that history starts empty."""
        provider = MagicMock(spec=ModelProvider)
        agent = Agent(provider=provider)
        assert agent.history == []

    def test_clear_history(self) -> None:
        """Test clearing conversation history."""
        provider = MagicMock(spec=ModelProvider)
        agent = Agent(provider=provider)
        agent.history.append(Message(role="user", content="Hello"))
        agent.clear_history()
        assert agent.history == []

    def test_history_preserves_system_prompt(self) -> None:
        """Test that system prompt is included in messages."""
        provider = MagicMock(spec=ModelProvider)
        agent = Agent(provider=provider, system_prompt="Be helpful.")
        messages = agent.get_messages_for_api()
        assert len(messages) == 1
        assert messages[0].role == "system"
        assert messages[0].content == "Be helpful."


class TestAgentRun:
    """Tests for Agent.run() method."""

    @pytest.mark.asyncio
    async def test_run_streams_content(self) -> None:
        """Test that run() yields content events from model response."""
        provider = MagicMock(spec=ModelProvider)

        async def mock_stream(messages, tools=None, **kwargs):  # noqa: ARG001
            yield StreamChunk(content="Hello")
            yield StreamChunk(content=" World")
            yield StreamChunk(finish_reason=FinishReason.STOP)

        provider.chat_completion_stream = mock_stream

        agent = Agent(provider=provider)
        events = []
        async for event in agent.run("Hi"):
            events.append(event)

        # Should have content events and a finished event
        content_events = [e for e in events if e.type == EventType.CONTENT]
        assert len(content_events) == 2
        assert content_events[0].data == "Hello"
        assert content_events[1].data == " World"

        finished_events = [e for e in events if e.type == EventType.FINISHED]
        assert len(finished_events) == 1

    @pytest.mark.asyncio
    async def test_run_adds_user_message_to_history(self) -> None:
        """Test that run() adds the user message to history."""
        provider = MagicMock(spec=ModelProvider)

        async def mock_stream(messages, tools=None, **kwargs):  # noqa: ARG001
            yield StreamChunk(finish_reason=FinishReason.STOP)

        provider.chat_completion_stream = mock_stream

        agent = Agent(provider=provider)
        async for _ in agent.run("Hello"):
            pass

        assert len(agent.history) >= 1
        user_msgs = [m for m in agent.history if m.role == "user"]
        assert len(user_msgs) == 1
        assert user_msgs[0].content == "Hello"

    @pytest.mark.asyncio
    async def test_run_adds_assistant_response_to_history(self) -> None:
        """Test that run() adds the assistant response to history."""
        provider = MagicMock(spec=ModelProvider)

        async def mock_stream(messages, tools=None, **kwargs):  # noqa: ARG001
            yield StreamChunk(content="Hi there!")
            yield StreamChunk(finish_reason=FinishReason.STOP)

        provider.chat_completion_stream = mock_stream

        agent = Agent(provider=provider)
        async for _ in agent.run("Hello"):
            pass

        assistant_msgs = [m for m in agent.history if m.role == "assistant"]
        assert len(assistant_msgs) == 1
        assert assistant_msgs[0].content == "Hi there!"

    @pytest.mark.asyncio
    async def test_run_streams_thinking_content(self) -> None:
        """Test that run() yields thought events for reasoning models."""
        provider = MagicMock(spec=ModelProvider)

        async def mock_stream(messages, tools=None, **kwargs):  # noqa: ARG001
            yield StreamChunk(thinking="Let me consider...")
            yield StreamChunk(content="The answer is 42.")
            yield StreamChunk(finish_reason=FinishReason.STOP)

        provider.chat_completion_stream = mock_stream

        agent = Agent(provider=provider)
        events = []
        async for event in agent.run("What is the meaning of life?"):
            events.append(event)

        thought_events = [e for e in events if e.type == EventType.THOUGHT]
        assert len(thought_events) == 1
        assert thought_events[0].data == "Let me consider..."

    @pytest.mark.asyncio
    async def test_run_with_system_prompt(self) -> None:
        """Test that system prompt is passed to provider."""
        provider = MagicMock(spec=ModelProvider)
        captured_messages = []

        async def mock_stream(messages, tools=None, **kwargs):  # noqa: ARG001
            captured_messages.extend(messages)
            yield StreamChunk(finish_reason=FinishReason.STOP)

        provider.chat_completion_stream = mock_stream

        agent = Agent(provider=provider, system_prompt="Be concise.")
        async for _ in agent.run("Hello"):
            pass

        assert len(captured_messages) >= 2
        assert captured_messages[0].role == "system"
        assert captured_messages[0].content == "Be concise."


class TestAgentToolCalls:
    """Tests for Agent tool call handling."""

    @pytest.mark.asyncio
    async def test_run_detects_tool_calls(self) -> None:
        """Test that run() yields tool call request events."""
        provider = MagicMock(spec=ModelProvider)

        tool_call = ToolCall(
            id="call_123",
            name="read_file",
            arguments={"path": "test.py"},
        )

        async def mock_stream(messages, tools=None, **kwargs):  # noqa: ARG001
            yield StreamChunk(tool_calls=[tool_call], finish_reason=FinishReason.TOOL_CALLS)

        provider.chat_completion_stream = mock_stream

        tools = [
            ToolDeclaration(
                name="read_file",
                description="Read a file",
                parameters={"type": "object", "properties": {"path": {"type": "string"}}},
            )
        ]
        agent = Agent(provider=provider, tools=tools)
        events = []
        async for event in agent.run("Read test.py"):
            events.append(event)

        tool_events = [e for e in events if e.type == EventType.TOOL_CALL_REQUEST]
        assert len(tool_events) == 1
        assert tool_events[0].data.name == "read_file"
        assert tool_events[0].data.arguments == {"path": "test.py"}

    @pytest.mark.asyncio
    async def test_run_passes_tools_to_provider(self) -> None:
        """Test that tools are passed to the provider."""
        provider = MagicMock(spec=ModelProvider)
        captured_tools = []

        async def mock_stream(messages, tools=None, **kwargs):  # noqa: ARG001
            if tools:
                captured_tools.extend(tools)
            yield StreamChunk(finish_reason=FinishReason.STOP)

        provider.chat_completion_stream = mock_stream

        tools = [
            ToolDeclaration(
                name="shell",
                description="Run a command",
                parameters={"type": "object", "properties": {}},
            )
        ]
        agent = Agent(provider=provider, tools=tools)
        async for _ in agent.run("List files"):
            pass

        assert len(captured_tools) == 1
        assert captured_tools[0].name == "shell"

    @pytest.mark.asyncio
    async def test_submit_tool_result(self) -> None:
        """Test submitting a tool result and continuing the conversation."""
        provider = MagicMock(spec=ModelProvider)
        call_count = 0

        async def mock_stream(messages, tools=None, **kwargs):  # noqa: ARG001
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: model requests tool
                yield StreamChunk(
                    tool_calls=[ToolCall(id="call_1", name="read_file", arguments={"path": "x"})],
                    finish_reason=FinishReason.TOOL_CALLS,
                )
            else:
                # Second call: model responds after tool result
                yield StreamChunk(content="The file contains: hello")
                yield StreamChunk(finish_reason=FinishReason.STOP)

        provider.chat_completion_stream = mock_stream

        agent = Agent(provider=provider)

        # First run - get tool call
        events1 = []
        async for event in agent.run("Read the file"):
            events1.append(event)

        # Submit tool result
        agent.submit_tool_result(tool_call_id="call_1", result="hello")

        # Continue - should get response
        events2 = []
        async for event in agent.continue_with_tool_results():
            events2.append(event)

        content_events = [e for e in events2 if e.type == EventType.CONTENT]
        assert len(content_events) == 1
        assert "hello" in content_events[0].data


class TestAgentErrorHandling:
    """Tests for Agent error handling."""

    @pytest.mark.asyncio
    async def test_run_yields_error_on_exception(self) -> None:
        """Test that run() yields an error event when provider fails."""
        provider = MagicMock(spec=ModelProvider)

        async def mock_stream(messages, tools=None, **kwargs):  # noqa: ARG001
            raise RuntimeError("API Error")
            yield  # Make it a generator  # noqa: B901

        provider.chat_completion_stream = mock_stream

        agent = Agent(provider=provider)
        events = []
        async for event in agent.run("Hello"):
            events.append(event)

        error_events = [e for e in events if e.type == EventType.ERROR]
        assert len(error_events) == 1
        assert "API Error" in str(error_events[0].data)
