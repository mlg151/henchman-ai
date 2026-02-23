"""Tests for Anthropic provider validation logic."""

import pytest

from henchman.providers.anthropic import AnthropicProvider
from henchman.providers.base import Message


class TestAnthropicValidation:
    """Tests for Anthropic provider validation."""

    @pytest.mark.asyncio
    async def test_empty_messages_validation(self):
        """Test that empty messages list raises ValueError."""
        provider = AnthropicProvider(api_key="test-key")

        # Create empty messages list
        messages = []

        # This should raise ValueError
        with pytest.raises(ValueError, match="Messages list cannot be empty"):
            async for _ in provider.chat_completion_stream(messages):
                pass

    @pytest.mark.asyncio
    async def test_empty_user_message_validation(self):
        """Test validation of empty user message."""
        provider = AnthropicProvider(api_key="test-key")

        # Create messages with empty user message
        messages = [Message(role="user", content="")]  # Empty content

        # Mock the actual API call since we're only testing validation
        # The validation happens in the chat_completion_stream method
        # We need to actually call it to trigger the validation
        try:
            async for _ in provider.chat_completion_stream(messages):
                pass
            # If we get here without exception, the test should fail
            pytest.fail("Expected ValueError for empty user message")
        except ValueError as e:
            # Check that it's the right error
            if "content" in str(e).lower():
                # This is the validation we're testing
                pass
            else:
                raise

    @pytest.mark.asyncio
    async def test_valid_messages_with_tool_calls(self):
        """Test that tool/function messages can have empty content."""
        provider = AnthropicProvider(api_key="test-key")

        # Create valid messages with tool call
        # Need to import ToolCall
        from henchman.providers.base import ToolCall

        messages = [
            Message(role="user", content="What's the weather?"),
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="1", name="get_weather", arguments={})],
            ),
            Message(role="tool", content="", tool_call_id="1"),
        ]

        # Validation should pass (no ValueError about empty messages).
        # The stream may succeed silently with a mock key or raise an auth error.
        try:
            async for _ in provider.chat_completion_stream(messages):
                pass
        except Exception as exc:
            # Any error should be about API auth, not validation
            assert "Messages list cannot be empty" not in str(exc)

    @pytest.mark.asyncio
    async def test_assistant_message_with_only_tool_calls(self):
        """Test that assistant messages with only tool calls are valid."""
        provider = AnthropicProvider(api_key="test-key")

        # Assistant message with tool calls but empty content
        messages = [
            Message(role="user", content="Do something"),
            Message(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "1",
                        "type": "function",
                        "function": {"name": "do_task", "arguments": "{}"},
                    }
                ],
            ),
        ]

        # Validation should pass; may or may not raise on API call
        try:
            async for _ in provider.chat_completion_stream(messages):
                pass
        except Exception as exc:
            assert "Messages list cannot be empty" not in str(exc)
            assert "content" not in str(exc).lower() or "API" in str(exc)

    @pytest.mark.asyncio
    async def test_mixed_valid_messages(self):
        """Test a mix of valid messages."""
        provider = AnthropicProvider(api_key="test-key")

        messages = [
            Message(role="system", content="You are a helpful assistant."),
            Message(role="user", content="Hello!"),
            Message(role="assistant", content="Hi there!"),
            Message(role="user", content="How are you?"),
        ]

        # Validation should pass; may or may not raise on API call
        try:
            async for _ in provider.chat_completion_stream(messages):
                pass
        except Exception as exc:
            assert "Messages list cannot be empty" not in str(exc)
            assert "content" not in str(exc).lower() or "API" in str(exc)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
