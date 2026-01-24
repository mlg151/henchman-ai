"""Tests for Anthropic provider."""

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.providers.anthropic import AnthropicProvider
from henchman.providers.base import FinishReason, Message, ModelProvider, ToolCall, ToolDeclaration


class TestAnthropicProvider:
    """Tests for AnthropicProvider."""

    def test_instantiation_with_explicit_key(self) -> None:
        """Test creating provider with explicit API key."""
        provider = AnthropicProvider(api_key="test-anthropic-key")
        assert provider.api_key == "test-anthropic-key"
        assert provider.default_model == "claude-sonnet-4-20250514"

    def test_instantiation_with_env_var(self) -> None:
        """Test creating provider with environment variable."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-key"}):
            provider = AnthropicProvider()
            assert provider.api_key == "env-key"

    def test_instantiation_without_key(self) -> None:
        """Test creating provider without API key (empty string)."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            provider = AnthropicProvider()
            assert provider.api_key == ""

    def test_custom_model(self) -> None:
        """Test creating provider with custom model."""
        provider = AnthropicProvider(api_key="test-key", model="claude-3-opus-20240229")
        assert provider.default_model == "claude-3-opus-20240229"

    def test_name_property(self) -> None:
        """Test that name property returns 'anthropic'."""
        provider = AnthropicProvider(api_key="test-key")
        assert provider.name == "anthropic"

    def test_list_models(self) -> None:
        """Test listing available models."""
        provider = AnthropicProvider(api_key="test-key")
        models = provider.list_models()
        assert "claude-sonnet-4-20250514" in models
        assert "claude-3-5-sonnet-20241022" in models

    def test_is_model_provider(self) -> None:
        """Test that AnthropicProvider implements ModelProvider."""
        provider = AnthropicProvider(api_key="test-key")
        assert isinstance(provider, ModelProvider)

    def test_max_tokens_default(self) -> None:
        """Test default max_tokens."""
        provider = AnthropicProvider(api_key="test-key")
        assert provider.max_tokens == 8192

    def test_custom_max_tokens(self) -> None:
        """Test custom max_tokens."""
        provider = AnthropicProvider(api_key="test-key", max_tokens=4096)
        assert provider.max_tokens == 4096


class TestAnthropicFormatting:
    """Tests for Anthropic message/tool formatting."""

    def test_format_tool(self) -> None:
        """Test tool formatting for Anthropic API."""
        provider = AnthropicProvider(api_key="test-key")
        tool = ToolDeclaration(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object", "properties": {}},
        )
        formatted = provider._format_tool(tool)
        assert formatted["name"] == "test_tool"
        assert formatted["description"] == "A test tool"
        assert formatted["input_schema"] == {"type": "object", "properties": {}}

    def test_format_messages_basic(self) -> None:
        """Test basic message formatting."""
        provider = AnthropicProvider(api_key="test-key")
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there"),
        ]
        system, formatted = provider._format_messages(messages)
        assert system is None
        assert len(formatted) == 2
        assert formatted[0]["role"] == "user"
        assert formatted[0]["content"] == "Hello"

    def test_format_messages_with_system(self) -> None:
        """Test message formatting with system message."""
        provider = AnthropicProvider(api_key="test-key")
        messages = [
            Message(role="system", content="You are helpful"),
            Message(role="user", content="Hello"),
        ]
        system, formatted = provider._format_messages(messages)
        assert system == "You are helpful"
        assert len(formatted) == 1
        assert formatted[0]["role"] == "user"

    def test_format_messages_tool_result(self) -> None:
        """Test tool result message formatting."""
        provider = AnthropicProvider(api_key="test-key")
        messages = [
            Message(role="tool", content="result data", tool_call_id="tc_123"),
        ]
        system, formatted = provider._format_messages(messages)
        assert len(formatted) == 1
        assert formatted[0]["role"] == "user"
        assert formatted[0]["content"][0]["type"] == "tool_result"
        assert formatted[0]["content"][0]["tool_use_id"] == "tc_123"

    def test_format_messages_assistant_with_tool_calls(self) -> None:
        """Test assistant message with tool calls."""
        provider = AnthropicProvider(api_key="test-key")
        messages = [
            Message(
                role="assistant",
                content="Let me check",
                tool_calls=[ToolCall(id="tc_1", name="search", arguments={"q": "test"})],
            ),
        ]
        system, formatted = provider._format_messages(messages)
        assert len(formatted) == 1
        content = formatted[0]["content"]
        assert isinstance(content, list)
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "tool_use"
        assert content[1]["id"] == "tc_1"

    def test_format_messages_assistant_tool_calls_no_content(self) -> None:
        """Test assistant message with tool calls but no text content."""
        provider = AnthropicProvider(api_key="test-key")
        messages = [
            Message(
                role="assistant",
                content=None,
                tool_calls=[ToolCall(id="tc_1", name="search", arguments={})],
            ),
        ]
        system, formatted = provider._format_messages(messages)
        content = formatted[0]["content"]
        assert len(content) == 1
        assert content[0]["type"] == "tool_use"


class TestAnthropicFinishReasons:
    """Tests for finish reason parsing."""

    def test_parse_finish_reason_end_turn(self) -> None:
        """Test end_turn maps to STOP."""
        provider = AnthropicProvider(api_key="test-key")
        assert provider._parse_finish_reason("end_turn") == FinishReason.STOP

    def test_parse_finish_reason_stop_sequence(self) -> None:
        """Test stop_sequence maps to STOP."""
        provider = AnthropicProvider(api_key="test-key")
        assert provider._parse_finish_reason("stop_sequence") == FinishReason.STOP

    def test_parse_finish_reason_tool_use(self) -> None:
        """Test tool_use maps to TOOL_CALLS."""
        provider = AnthropicProvider(api_key="test-key")
        assert provider._parse_finish_reason("tool_use") == FinishReason.TOOL_CALLS

    def test_parse_finish_reason_max_tokens(self) -> None:
        """Test max_tokens maps to LENGTH."""
        provider = AnthropicProvider(api_key="test-key")
        assert provider._parse_finish_reason("max_tokens") == FinishReason.LENGTH

    def test_parse_finish_reason_none(self) -> None:
        """Test None returns None."""
        provider = AnthropicProvider(api_key="test-key")
        assert provider._parse_finish_reason(None) is None

    def test_parse_finish_reason_unknown(self) -> None:
        """Test unknown reason defaults to STOP."""
        provider = AnthropicProvider(api_key="test-key")
        assert provider._parse_finish_reason("unknown") == FinishReason.STOP


class TestAnthropicStreaming:
    """Tests for streaming chat completion."""

    @pytest.mark.anyio
    async def test_chat_completion_stream_text(self) -> None:
        """Test streaming text content."""
        provider = AnthropicProvider(api_key="test-key")

        # Create mock events
        mock_text_event = MagicMock()
        mock_text_event.type = "content_block_delta"
        mock_text_event.delta.type = "text_delta"
        mock_text_event.delta.text = "Hello"

        mock_finish_event = MagicMock()
        mock_finish_event.type = "message_delta"
        mock_finish_event.delta.stop_reason = "end_turn"

        events = [mock_text_event, mock_finish_event]

        mock_stream = MagicMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        async def async_iter() -> Any:
            for event in events:
                yield event

        mock_stream.__aiter__ = lambda _: async_iter()

        with patch.object(provider._client.messages, "stream", return_value=mock_stream):
            chunks = []
            async for chunk in provider.chat_completion_stream(
                [Message(role="user", content="Hi")]
            ):
                chunks.append(chunk)

        assert len(chunks) == 2
        assert chunks[0].content == "Hello"
        assert chunks[1].finish_reason == FinishReason.STOP

    @pytest.mark.anyio
    async def test_chat_completion_stream_with_tools(self) -> None:
        """Test streaming with tool calls."""
        provider = AnthropicProvider(api_key="test-key")

        # Mock tool use events
        mock_block_start = MagicMock()
        mock_block_start.type = "content_block_start"
        mock_block_start.content_block.type = "tool_use"
        mock_block_start.content_block.id = "tc_123"
        mock_block_start.content_block.name = "search"

        mock_input_delta = MagicMock()
        mock_input_delta.type = "content_block_delta"
        mock_input_delta.delta.type = "input_json_delta"
        mock_input_delta.delta.partial_json = '{"query": "test"}'

        mock_block_stop = MagicMock()
        mock_block_stop.type = "content_block_stop"

        mock_finish = MagicMock()
        mock_finish.type = "message_delta"
        mock_finish.delta.stop_reason = "tool_use"

        events = [mock_block_start, mock_input_delta, mock_block_stop, mock_finish]

        mock_stream = MagicMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        async def async_iter() -> Any:
            for event in events:
                yield event

        mock_stream.__aiter__ = lambda _: async_iter()

        tool = ToolDeclaration(
            name="search",
            description="Search",
            parameters={"type": "object", "properties": {}},
        )

        with patch.object(provider._client.messages, "stream", return_value=mock_stream):
            chunks = []
            async for chunk in provider.chat_completion_stream(
                [Message(role="user", content="Search")],
                tools=[tool],
            ):
                chunks.append(chunk)

        # Should have finish chunk with tool calls
        finish_chunks = [c for c in chunks if c.finish_reason == FinishReason.TOOL_CALLS]
        assert len(finish_chunks) == 1
        assert finish_chunks[0].tool_calls is not None
        assert finish_chunks[0].tool_calls[0].name == "search"

    @pytest.mark.anyio
    async def test_chat_completion_stream_thinking(self) -> None:
        """Test streaming thinking content."""
        provider = AnthropicProvider(api_key="test-key")

        mock_thinking_event = MagicMock()
        mock_thinking_event.type = "content_block_delta"
        mock_thinking_event.delta.type = "thinking_delta"
        mock_thinking_event.delta.thinking = "Let me think..."

        mock_finish = MagicMock()
        mock_finish.type = "message_delta"
        mock_finish.delta.stop_reason = "end_turn"

        events = [mock_thinking_event, mock_finish]

        mock_stream = MagicMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        async def async_iter() -> Any:
            for event in events:
                yield event

        mock_stream.__aiter__ = lambda _: async_iter()

        with patch.object(provider._client.messages, "stream", return_value=mock_stream):
            chunks = []
            async for chunk in provider.chat_completion_stream(
                [Message(role="user", content="Think")]
            ):
                chunks.append(chunk)

        thinking_chunks = [c for c in chunks if c.thinking]
        assert len(thinking_chunks) == 1
        assert thinking_chunks[0].thinking == "Let me think..."

    @pytest.mark.anyio
    async def test_chat_completion_handles_invalid_json(self) -> None:
        """Test handling of invalid JSON in tool arguments."""
        provider = AnthropicProvider(api_key="test-key")

        mock_block_start = MagicMock()
        mock_block_start.type = "content_block_start"
        mock_block_start.content_block.type = "tool_use"
        mock_block_start.content_block.id = "tc_bad"
        mock_block_start.content_block.name = "broken"

        mock_input_delta = MagicMock()
        mock_input_delta.type = "content_block_delta"
        mock_input_delta.delta.type = "input_json_delta"
        mock_input_delta.delta.partial_json = "not valid json{"

        mock_block_stop = MagicMock()
        mock_block_stop.type = "content_block_stop"

        mock_finish = MagicMock()
        mock_finish.type = "message_delta"
        mock_finish.delta.stop_reason = "tool_use"

        events = [mock_block_start, mock_input_delta, mock_block_stop, mock_finish]

        mock_stream = MagicMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        async def async_iter() -> Any:
            for event in events:
                yield event

        mock_stream.__aiter__ = lambda _: async_iter()

        with patch.object(provider._client.messages, "stream", return_value=mock_stream):
            chunks = []
            async for chunk in provider.chat_completion_stream(
                [Message(role="user", content="Call broken tool")]
            ):
                chunks.append(chunk)

        # Should still work, with empty arguments
        finish_chunks = [c for c in chunks if c.tool_calls]
        assert len(finish_chunks) == 1
        assert finish_chunks[0].tool_calls[0].arguments == {}

    @pytest.mark.anyio
    async def test_chat_completion_with_system_message(self) -> None:
        """Test streaming with system message."""
        provider = AnthropicProvider(api_key="test-key")

        mock_text_event = MagicMock()
        mock_text_event.type = "content_block_delta"
        mock_text_event.delta.type = "text_delta"
        mock_text_event.delta.text = "I am helpful"

        mock_finish = MagicMock()
        mock_finish.type = "message_delta"
        mock_finish.delta.stop_reason = "end_turn"

        events = [mock_text_event, mock_finish]

        mock_stream = MagicMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        async def async_iter() -> Any:
            for event in events:
                yield event

        mock_stream.__aiter__ = lambda _: async_iter()

        with patch.object(provider._client.messages, "stream", return_value=mock_stream):
            chunks = []
            async for chunk in provider.chat_completion_stream(
                [
                    Message(role="system", content="You are helpful"),
                    Message(role="user", content="Hi"),
                ]
            ):
                chunks.append(chunk)

        assert len(chunks) == 2
        assert chunks[0].content == "I am helpful"

    @pytest.mark.anyio
    async def test_chat_completion_text_block_start(self) -> None:
        """Test handling text content_block_start (not tool_use)."""
        provider = AnthropicProvider(api_key="test-key")

        # Text block start - not a tool_use
        mock_block_start = MagicMock()
        mock_block_start.type = "content_block_start"
        mock_block_start.content_block.type = "text"

        mock_text = MagicMock()
        mock_text.type = "content_block_delta"
        mock_text.delta.type = "text_delta"
        mock_text.delta.text = "Hello"

        mock_finish = MagicMock()
        mock_finish.type = "message_delta"
        mock_finish.delta.stop_reason = "end_turn"

        events = [mock_block_start, mock_text, mock_finish]

        mock_stream = MagicMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        async def async_iter() -> Any:
            for event in events:
                yield event

        mock_stream.__aiter__ = lambda _: async_iter()

        with patch.object(provider._client.messages, "stream", return_value=mock_stream):
            chunks = []
            async for chunk in provider.chat_completion_stream(
                [Message(role="user", content="Hi")]
            ):
                chunks.append(chunk)

        # Should still get text content and finish
        text_chunks = [c for c in chunks if c.content]
        assert len(text_chunks) == 1
        assert text_chunks[0].content == "Hello"

    @pytest.mark.anyio
    async def test_chat_completion_input_json_without_tool_id(self) -> None:
        """Test input_json_delta when current_tool_id is None."""
        provider = AnthropicProvider(api_key="test-key")

        # Input JSON without a preceding tool_use block
        mock_input = MagicMock()
        mock_input.type = "content_block_delta"
        mock_input.delta.type = "input_json_delta"
        mock_input.delta.partial_json = '{"ignored": true}'

        mock_finish = MagicMock()
        mock_finish.type = "message_delta"
        mock_finish.delta.stop_reason = "end_turn"

        events = [mock_input, mock_finish]

        mock_stream = MagicMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        async def async_iter() -> Any:
            for event in events:
                yield event

        mock_stream.__aiter__ = lambda _: async_iter()

        with patch.object(provider._client.messages, "stream", return_value=mock_stream):
            chunks = []
            async for chunk in provider.chat_completion_stream(
                [Message(role="user", content="Hi")]
            ):
                chunks.append(chunk)

        # Should just get finish, no tool calls
        assert len(chunks) == 1
        assert chunks[0].finish_reason == FinishReason.STOP
        assert chunks[0].tool_calls is None

    @pytest.mark.anyio
    async def test_chat_completion_unknown_event_type(self) -> None:
        """Test handling of unknown event types."""
        provider = AnthropicProvider(api_key="test-key")

        # Unknown event type
        mock_unknown = MagicMock()
        mock_unknown.type = "unknown_event"

        mock_finish = MagicMock()
        mock_finish.type = "message_delta"
        mock_finish.delta.stop_reason = "end_turn"

        events = [mock_unknown, mock_finish]

        mock_stream = MagicMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        async def async_iter() -> Any:
            for event in events:
                yield event

        mock_stream.__aiter__ = lambda _: async_iter()

        with patch.object(provider._client.messages, "stream", return_value=mock_stream):
            chunks = []
            async for chunk in provider.chat_completion_stream(
                [Message(role="user", content="Hi")]
            ):
                chunks.append(chunk)

        # Should just get finish
        assert len(chunks) == 1
        assert chunks[0].finish_reason == FinishReason.STOP
