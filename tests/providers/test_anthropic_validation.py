"""Tests for Anthropic provider validation logic."""

import pytest

from henchman.providers.anthropic import AnthropicProvider
from henchman.providers.base import Message, ToolCall
from henchman.providers.utils import validate_messages


class TestAnthropicValidation:
    """Tests for Anthropic provider validation."""

    @pytest.mark.asyncio
    async def test_empty_messages_validation(self) -> None:
        """Test that empty messages list raises ValueError."""
        provider = AnthropicProvider(api_key="test-key")

        # Create empty messages list
        messages: list[Message] = []

        # This should raise ValueError
        with pytest.raises(ValueError, match="Messages list cannot be empty"):
            async for _ in provider.chat_completion_stream(messages):
                pass

    @pytest.mark.asyncio
    async def test_empty_user_message_validation(self) -> None:
        """Test validation of empty user message."""
        provider = AnthropicProvider(api_key="test-key")

        # Create messages with empty user message
        messages = [Message(role="user", content="")]  # Empty content

        with pytest.raises(ValueError, match="cannot have empty content"):
            async for _ in provider.chat_completion_stream(messages):
                pass

    def test_valid_messages_with_tool_calls(self) -> None:
        """Test that tool/function messages can have empty content."""

        messages = [
            Message(role="user", content="What's the weather?"),
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="1", name="get_weather", arguments={})],
            ),
            Message(role="tool", content="", tool_call_id="1"),
        ]

        validate_messages(messages)

    def test_assistant_message_with_only_tool_calls(self) -> None:
        """Test that assistant messages with only tool calls are valid."""

        # Assistant message with tool calls but empty content
        messages = [
            Message(role="user", content="Do something"),
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="1", name="do_task", arguments={})],
            ),
        ]

        validate_messages(messages)

    def test_mixed_valid_messages(self) -> None:
        """Test a mix of valid messages."""

        messages = [
            Message(role="system", content="You are a helpful assistant."),
            Message(role="user", content="Hello!"),
            Message(role="assistant", content="Hi there!"),
            Message(role="user", content="How are you?"),
        ]

        validate_messages(messages)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
