"""Tests for provider base types and abstractions."""

import pytest

from henchman.providers.base import (
    FinishReason,
    Message,
    ModelProvider,
    StreamChunk,
    ToolCall,
    ToolDeclaration,
)


class TestMessage:
    """Tests for Message dataclass."""

    def test_user_message_creation(self) -> None:
        """Test creating a simple user message."""
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.tool_calls is None
        assert msg.tool_call_id is None

    def test_assistant_message_with_tool_calls(self) -> None:
        """Test assistant message with tool calls."""
        tool_call = ToolCall(id="call_1", name="read_file", arguments={"path": "test.py"})
        msg = Message(role="assistant", content=None, tool_calls=[tool_call])
        assert msg.role == "assistant"
        assert msg.content is None
        assert msg.tool_calls is not None
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].name == "read_file"

    def test_tool_result_message(self) -> None:
        """Test tool result message."""
        msg = Message(role="tool", content="file contents here", tool_call_id="call_1")
        assert msg.role == "tool"
        assert msg.content == "file contents here"
        assert msg.tool_call_id == "call_1"

    def test_system_message(self) -> None:
        """Test system message."""
        msg = Message(role="system", content="You are a helpful assistant")
        assert msg.role == "system"
        assert msg.content == "You are a helpful assistant"


class TestToolCall:
    """Tests for ToolCall dataclass."""

    def test_tool_call_creation(self) -> None:
        """Test creating a tool call."""
        tc = ToolCall(id="call_123", name="shell", arguments={"command": "ls -la"})
        assert tc.id == "call_123"
        assert tc.name == "shell"
        assert tc.arguments == {"command": "ls -la"}

    def test_tool_call_with_complex_arguments(self) -> None:
        """Test tool call with nested arguments."""
        tc = ToolCall(
            id="call_456",
            name="write_file",
            arguments={"path": "test.py", "content": "print('hello')", "overwrite": True},
        )
        assert tc.arguments["overwrite"] is True


class TestToolDeclaration:
    """Tests for ToolDeclaration dataclass."""

    def test_tool_declaration_creation(self) -> None:
        """Test creating a tool declaration."""
        decl = ToolDeclaration(
            name="read_file",
            description="Read contents of a file",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                },
                "required": ["path"],
            },
        )
        assert decl.name == "read_file"
        assert decl.description == "Read contents of a file"
        assert decl.parameters["type"] == "object"
        assert "path" in decl.parameters["properties"]


class TestStreamChunk:
    """Tests for StreamChunk dataclass."""

    def test_content_chunk(self) -> None:
        """Test chunk with content."""
        chunk = StreamChunk(content="Hello")
        assert chunk.content == "Hello"
        assert chunk.tool_calls is None
        assert chunk.finish_reason is None

    def test_tool_call_chunk(self) -> None:
        """Test chunk with tool calls."""
        tc = ToolCall(id="call_1", name="test", arguments={})
        chunk = StreamChunk(tool_calls=[tc])
        assert chunk.content is None
        assert chunk.tool_calls is not None

    def test_finish_chunk(self) -> None:
        """Test chunk with finish reason."""
        chunk = StreamChunk(finish_reason=FinishReason.STOP)
        assert chunk.finish_reason == FinishReason.STOP

    def test_thinking_chunk(self) -> None:
        """Test chunk with thinking content (reasoning models)."""
        chunk = StreamChunk(thinking="Let me think about this...")
        assert chunk.thinking == "Let me think about this..."


class TestFinishReason:
    """Tests for FinishReason enum."""

    def test_finish_reason_values(self) -> None:
        """Test that all expected finish reasons exist."""
        assert FinishReason.STOP.value == "stop"
        assert FinishReason.TOOL_CALLS.value == "tool_calls"
        assert FinishReason.LENGTH.value == "length"
        assert FinishReason.CONTENT_FILTER.value == "content_filter"


class TestModelProviderProtocol:
    """Tests for ModelProvider abstract base class."""

    def test_cannot_instantiate_directly(self) -> None:
        """Test that ModelProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            ModelProvider()  # type: ignore[abstract]

    def test_subclass_must_implement_name(self) -> None:
        """Test that subclasses must implement name property."""

        class IncompleteProvider(ModelProvider):
            async def chat_completion_stream(
                self, messages, tools=None, **kwargs  # noqa: ARG002
            ):
                yield StreamChunk()

        with pytest.raises(TypeError):
            IncompleteProvider()  # type: ignore[abstract]

    def test_subclass_must_implement_chat_completion_stream(self) -> None:
        """Test that subclasses must implement chat_completion_stream."""

        class IncompleteProvider(ModelProvider):
            @property
            def name(self) -> str:
                return "incomplete"

        with pytest.raises(TypeError):
            IncompleteProvider()  # type: ignore[abstract]
