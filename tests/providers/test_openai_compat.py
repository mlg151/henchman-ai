"""Tests for OpenAI-compatible provider base class."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.providers.base import FinishReason, Message, ToolCall, ToolDeclaration
from henchman.providers.openai_compat import OpenAICompatibleProvider


class TestOpenAICompatibleProvider:
    """Tests for OpenAICompatibleProvider."""

    def test_instantiation_with_api_key(self) -> None:
        """Test creating provider with explicit API key."""
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://api.example.com",
            default_model="test-model",
        )
        assert provider.api_key == "test-key"
        assert provider.base_url == "https://api.example.com"
        assert provider.default_model == "test-model"

    def test_name_property(self) -> None:
        """Test that name property returns correct value."""
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://api.example.com",
            default_model="test-model",
        )
        assert provider.name == "openai-compatible"

    def test_format_tool_declaration(self) -> None:
        """Test that tool declarations are formatted for OpenAI API."""
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://api.example.com",
            default_model="test-model",
        )
        decl = ToolDeclaration(
            name="read_file",
            description="Read a file",
            parameters={"type": "object", "properties": {"path": {"type": "string"}}},
        )
        formatted = provider._format_tool(decl)
        assert formatted["type"] == "function"
        assert formatted["function"]["name"] == "read_file"
        assert formatted["function"]["description"] == "Read a file"
        assert formatted["function"]["parameters"] == decl.parameters

    def test_format_message_user(self) -> None:
        """Test formatting user message for API."""
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://api.example.com",
            default_model="test-model",
        )
        msg = Message(role="user", content="Hello")
        formatted = provider._format_message(msg)
        assert formatted["role"] == "user"
        assert formatted["content"] == "Hello"

    def test_format_message_assistant_with_tool_calls(self) -> None:
        """Test formatting assistant message with tool calls."""
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://api.example.com",
            default_model="test-model",
        )
        tc = ToolCall(id="call_1", name="test_tool", arguments={"arg": "value"})
        msg = Message(role="assistant", content=None, tool_calls=[tc])
        formatted = provider._format_message(msg)
        assert formatted["role"] == "assistant"
        assert formatted["content"] is None
        assert len(formatted["tool_calls"]) == 1
        assert formatted["tool_calls"][0]["id"] == "call_1"
        assert formatted["tool_calls"][0]["type"] == "function"
        assert formatted["tool_calls"][0]["function"]["name"] == "test_tool"

    def test_format_message_tool_result(self) -> None:
        """Test formatting tool result message."""
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://api.example.com",
            default_model="test-model",
        )
        msg = Message(role="tool", content="result data", tool_call_id="call_1")
        formatted = provider._format_message(msg)
        assert formatted["role"] == "tool"
        assert formatted["content"] == "result data"
        assert formatted["tool_call_id"] == "call_1"

    def test_parse_finish_reason_mapping(self) -> None:
        """Test parsing all finish reason values."""
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://api.example.com",
            default_model="test-model",
        )
        assert provider._parse_finish_reason(None) is None
        assert provider._parse_finish_reason("stop") == FinishReason.STOP
        assert provider._parse_finish_reason("tool_calls") == FinishReason.TOOL_CALLS
        assert provider._parse_finish_reason("length") == FinishReason.LENGTH
        assert provider._parse_finish_reason("content_filter") == FinishReason.CONTENT_FILTER
        # Unknown reason defaults to STOP
        assert provider._parse_finish_reason("unknown") == FinishReason.STOP

    def test_parse_tool_calls_empty(self) -> None:
        """Test parsing empty tool calls."""
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://api.example.com",
            default_model="test-model",
        )
        assert provider._parse_tool_calls(None) is None
        assert provider._parse_tool_calls([]) is None

    def test_parse_tool_calls_valid(self) -> None:
        """Test parsing valid tool calls."""
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://api.example.com",
            default_model="test-model",
        )
        mock_tc = MagicMock()
        mock_tc.id = "call_123"
        mock_tc.function.name = "read_file"
        mock_tc.function.arguments = '{"path": "test.py"}'

        result = provider._parse_tool_calls([mock_tc])
        assert result is not None
        assert len(result) == 1
        assert result[0].id == "call_123"
        assert result[0].name == "read_file"
        assert result[0].arguments == {"path": "test.py"}

    def test_parse_tool_calls_invalid_json(self) -> None:
        """Test parsing tool calls with invalid JSON arguments."""
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://api.example.com",
            default_model="test-model",
        )
        mock_tc = MagicMock()
        mock_tc.id = "call_123"
        mock_tc.function.name = "read_file"
        mock_tc.function.arguments = "not valid json"

        result = provider._parse_tool_calls([mock_tc])
        assert result is not None
        assert len(result) == 1
        assert result[0].arguments == {}  # Defaults to empty dict

    @pytest.mark.asyncio
    async def test_chat_completion_stream_content(self) -> None:
        """Test streaming chat completion with content chunks."""
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://api.example.com",
            default_model="test-model",
        )

        # Mock the OpenAI client response
        mock_chunk1 = MagicMock()
        mock_chunk1.choices = [MagicMock()]
        mock_chunk1.choices[0].delta.content = "Hello"
        mock_chunk1.choices[0].delta.tool_calls = None
        mock_chunk1.choices[0].finish_reason = None

        mock_chunk2 = MagicMock()
        mock_chunk2.choices = [MagicMock()]
        mock_chunk2.choices[0].delta.content = " World"
        mock_chunk2.choices[0].delta.tool_calls = None
        mock_chunk2.choices[0].finish_reason = None

        mock_chunk3 = MagicMock()
        mock_chunk3.choices = [MagicMock()]
        mock_chunk3.choices[0].delta.content = None
        mock_chunk3.choices[0].delta.tool_calls = None
        mock_chunk3.choices[0].finish_reason = "stop"

        async def mock_stream():
            for chunk in [mock_chunk1, mock_chunk2, mock_chunk3]:
                yield chunk

        async def mock_create(**kwargs):  # noqa: ARG001
            return mock_stream()

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)

            messages = [Message(role="user", content="Hi")]
            chunks = []
            async for chunk in provider.chat_completion_stream(messages):
                chunks.append(chunk)

            assert len(chunks) == 3
            assert chunks[0].content == "Hello"
            assert chunks[1].content == " World"
            assert chunks[2].finish_reason == FinishReason.STOP

    @pytest.mark.asyncio
    async def test_chat_completion_stream_with_tools(self) -> None:
        """Test streaming with tool declarations."""
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://api.example.com",
            default_model="test-model",
        )

        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta.content = "I'll help you"
        mock_chunk.choices[0].delta.tool_calls = None
        mock_chunk.choices[0].finish_reason = "stop"

        async def mock_stream():
            yield mock_chunk

        captured_kwargs = {}

        async def mock_create(**kwargs):
            captured_kwargs.update(kwargs)
            return mock_stream()

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)

            messages = [Message(role="user", content="Read test.py")]
            tools = [
                ToolDeclaration(
                    name="read_file",
                    description="Read a file",
                    parameters={"type": "object", "properties": {}},
                )
            ]

            chunks = []
            async for chunk in provider.chat_completion_stream(messages, tools=tools):
                chunks.append(chunk)

            assert "tools" in captured_kwargs
            assert len(captured_kwargs["tools"]) == 1
            assert captured_kwargs["tools"][0]["function"]["name"] == "read_file"

    @pytest.mark.asyncio
    async def test_chat_completion_stream_empty_choices(self) -> None:
        """Test streaming handles chunks with empty choices."""
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://api.example.com",
            default_model="test-model",
        )

        mock_chunk1 = MagicMock()
        mock_chunk1.choices = []  # Empty choices

        mock_chunk2 = MagicMock()
        mock_chunk2.choices = [MagicMock()]
        mock_chunk2.choices[0].delta.content = "Hello"
        mock_chunk2.choices[0].delta.tool_calls = None
        mock_chunk2.choices[0].finish_reason = "stop"

        async def mock_stream():
            yield mock_chunk1
            yield mock_chunk2

        async def mock_create(**kwargs):  # noqa: ARG001
            return mock_stream()

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)

            messages = [Message(role="user", content="Hi")]
            chunks = []
            async for chunk in provider.chat_completion_stream(messages):
                chunks.append(chunk)

            # Should only get one chunk (empty choices skipped)
            assert len(chunks) == 1
            assert chunks[0].content == "Hello"

    @pytest.mark.asyncio
    async def test_chat_completion_stream_with_tool_calls(self) -> None:
        """Test streaming with incremental tool call chunks."""
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://api.example.com",
            default_model="test-model",
        )

        # First chunk starts the tool call
        mock_tc_delta1 = MagicMock()
        mock_tc_delta1.index = 0
        mock_tc_delta1.id = "call_123"
        mock_tc_delta1.function = MagicMock()
        mock_tc_delta1.function.name = "read_file"
        mock_tc_delta1.function.arguments = '{"path":'

        mock_chunk1 = MagicMock()
        mock_chunk1.choices = [MagicMock()]
        mock_chunk1.choices[0].delta.content = None
        mock_chunk1.choices[0].delta.tool_calls = [mock_tc_delta1]
        mock_chunk1.choices[0].finish_reason = None

        # Second chunk continues the arguments
        mock_tc_delta2 = MagicMock()
        mock_tc_delta2.index = 0
        mock_tc_delta2.id = None
        mock_tc_delta2.function = MagicMock()
        mock_tc_delta2.function.name = None
        mock_tc_delta2.function.arguments = ' "test.py"}'

        mock_chunk2 = MagicMock()
        mock_chunk2.choices = [MagicMock()]
        mock_chunk2.choices[0].delta.content = None
        mock_chunk2.choices[0].delta.tool_calls = [mock_tc_delta2]
        mock_chunk2.choices[0].finish_reason = None

        # Third chunk finishes with tool_calls reason
        mock_chunk3 = MagicMock()
        mock_chunk3.choices = [MagicMock()]
        mock_chunk3.choices[0].delta.content = None
        mock_chunk3.choices[0].delta.tool_calls = None
        mock_chunk3.choices[0].finish_reason = "tool_calls"

        async def mock_stream():
            yield mock_chunk1
            yield mock_chunk2
            yield mock_chunk3

        async def mock_create(**kwargs):  # noqa: ARG001
            return mock_stream()

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)

            messages = [Message(role="user", content="Read test.py")]
            chunks = []
            async for chunk in provider.chat_completion_stream(messages):
                chunks.append(chunk)

            assert len(chunks) == 3
            # The final chunk should have the complete tool call
            assert chunks[2].finish_reason == FinishReason.TOOL_CALLS
            assert chunks[2].tool_calls is not None
            assert len(chunks[2].tool_calls) == 1
            assert chunks[2].tool_calls[0].id == "call_123"
            assert chunks[2].tool_calls[0].name == "read_file"
            assert chunks[2].tool_calls[0].arguments == {"path": "test.py"}

    @pytest.mark.asyncio
    async def test_chat_completion_stream_with_thinking(self) -> None:
        """Test streaming with reasoning content (thinking)."""
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://api.example.com",
            default_model="test-model",
        )

        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta.content = None
        mock_chunk.choices[0].delta.reasoning_content = "Let me think..."
        mock_chunk.choices[0].delta.tool_calls = None
        mock_chunk.choices[0].finish_reason = None

        async def mock_stream():
            yield mock_chunk

        async def mock_create(**kwargs):  # noqa: ARG001
            return mock_stream()

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)

            messages = [Message(role="user", content="Think about this")]
            chunks = []
            async for chunk in provider.chat_completion_stream(messages):
                chunks.append(chunk)

            assert len(chunks) == 1
            assert chunks[0].thinking == "Let me think..."

    @pytest.mark.asyncio
    async def test_chat_completion_stream_tool_call_invalid_json(self) -> None:
        """Test streaming with tool call that has invalid JSON arguments."""
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://api.example.com",
            default_model="test-model",
        )

        mock_tc_delta = MagicMock()
        mock_tc_delta.index = 0
        mock_tc_delta.id = "call_123"
        mock_tc_delta.function = MagicMock()
        mock_tc_delta.function.name = "test_tool"
        mock_tc_delta.function.arguments = "invalid json"

        mock_chunk1 = MagicMock()
        mock_chunk1.choices = [MagicMock()]
        mock_chunk1.choices[0].delta.content = None
        mock_chunk1.choices[0].delta.tool_calls = [mock_tc_delta]
        mock_chunk1.choices[0].finish_reason = None

        mock_chunk2 = MagicMock()
        mock_chunk2.choices = [MagicMock()]
        mock_chunk2.choices[0].delta.content = None
        mock_chunk2.choices[0].delta.tool_calls = None
        mock_chunk2.choices[0].finish_reason = "tool_calls"

        async def mock_stream():
            yield mock_chunk1
            yield mock_chunk2

        async def mock_create(**kwargs):  # noqa: ARG001
            return mock_stream()

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)

            messages = [Message(role="user", content="Test")]
            chunks = []
            async for chunk in provider.chat_completion_stream(messages):
                chunks.append(chunk)

            # Should still work, but with empty arguments
            assert chunks[1].tool_calls is not None
            assert chunks[1].tool_calls[0].arguments == {}

    @pytest.mark.asyncio
    async def test_chat_completion_stream_custom_model(self) -> None:
        """Test streaming with custom model override."""
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://api.example.com",
            default_model="default-model",
        )

        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta.content = "Hello"
        mock_chunk.choices[0].delta.tool_calls = None
        mock_chunk.choices[0].finish_reason = "stop"

        async def mock_stream():
            yield mock_chunk

        captured_kwargs = {}

        async def mock_create(**kwargs):
            captured_kwargs.update(kwargs)
            return mock_stream()

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)

            messages = [Message(role="user", content="Hi")]
            async for _ in provider.chat_completion_stream(messages, model="custom-model"):
                pass

            assert captured_kwargs["model"] == "custom-model"

    @pytest.mark.asyncio
    async def test_chat_completion_stream_tool_call_no_function(self) -> None:
        """Test streaming with tool call delta that has no function attribute."""
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://api.example.com",
            default_model="test-model",
        )

        # Tool call delta with no function (can happen in streaming)
        mock_tc_delta = MagicMock()
        mock_tc_delta.index = 0
        mock_tc_delta.id = "call_123"
        mock_tc_delta.function = None  # No function yet

        mock_chunk1 = MagicMock()
        mock_chunk1.choices = [MagicMock()]
        mock_chunk1.choices[0].delta.content = None
        mock_chunk1.choices[0].delta.tool_calls = [mock_tc_delta]
        mock_chunk1.choices[0].finish_reason = None

        # Second chunk adds function info
        mock_tc_delta2 = MagicMock()
        mock_tc_delta2.index = 0
        mock_tc_delta2.id = None
        mock_tc_delta2.function = MagicMock()
        mock_tc_delta2.function.name = "test_tool"
        mock_tc_delta2.function.arguments = "{}"

        mock_chunk2 = MagicMock()
        mock_chunk2.choices = [MagicMock()]
        mock_chunk2.choices[0].delta.content = None
        mock_chunk2.choices[0].delta.tool_calls = [mock_tc_delta2]
        mock_chunk2.choices[0].finish_reason = "tool_calls"

        async def mock_stream():
            yield mock_chunk1
            yield mock_chunk2

        async def mock_create(**kwargs):  # noqa: ARG001
            return mock_stream()

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)

            messages = [Message(role="user", content="Test")]
            chunks = []
            async for chunk in provider.chat_completion_stream(messages):
                chunks.append(chunk)

            # Should complete successfully
            assert len(chunks) == 2
            assert chunks[1].tool_calls is not None
            assert chunks[1].tool_calls[0].name == "test_tool"

    @pytest.mark.asyncio
    async def test_chat_completion_stream_tool_call_no_arguments(self) -> None:
        """Test streaming with tool call that has function but no arguments."""
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://api.example.com",
            default_model="test-model",
        )

        # Tool call with function name but no arguments string
        mock_tc_delta = MagicMock()
        mock_tc_delta.index = 0
        mock_tc_delta.id = "call_123"
        mock_tc_delta.function = MagicMock()
        mock_tc_delta.function.name = "no_args_tool"
        mock_tc_delta.function.arguments = None  # No arguments

        mock_chunk1 = MagicMock()
        mock_chunk1.choices = [MagicMock()]
        mock_chunk1.choices[0].delta.content = None
        mock_chunk1.choices[0].delta.tool_calls = [mock_tc_delta]
        mock_chunk1.choices[0].finish_reason = "tool_calls"

        async def mock_stream():
            yield mock_chunk1

        async def mock_create(**kwargs):  # noqa: ARG001
            return mock_stream()

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)

            messages = [Message(role="user", content="Test")]
            chunks = []
            async for chunk in provider.chat_completion_stream(messages):
                chunks.append(chunk)

            # Should complete with empty arguments
            assert len(chunks) == 1
            assert chunks[0].tool_calls is not None
            assert chunks[0].tool_calls[0].name == "no_args_tool"
            assert chunks[0].tool_calls[0].arguments == {}
