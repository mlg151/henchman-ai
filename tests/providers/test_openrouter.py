"""Tests for OpenRouter provider."""

import os
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
from openai.types.chat import ChatCompletionChunk

from henchman.providers.base import FinishReason, Message
from henchman.providers.openrouter import OpenRouterProvider
from tests.providers.stream_helpers import SDKResponse


class TestOpenRouterProvider:
    """Tests for OpenRouterProvider."""

    def test_instantiation_with_explicit_key(self) -> None:
        """Test creating provider with explicit API key."""
        provider = OpenRouterProvider(api_key="test-openrouter-key")
        assert provider.api_key == "test-openrouter-key"
        assert provider.default_model == "openai/gpt-4o-mini"

    def test_instantiation_with_env_var(self) -> None:
        """Test creating provider with environment variable."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "env-key"}):
            provider = OpenRouterProvider()
            assert provider.api_key == "env-key"

    def test_instantiation_without_key(self) -> None:
        """Test creating provider without API key (empty string)."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OPENROUTER_API_KEY", None)
            provider = OpenRouterProvider()
            assert provider.api_key == ""

    def test_custom_model(self) -> None:
        """Test creating provider with custom model."""
        provider = OpenRouterProvider(api_key="test-key", model="anthropic/claude-3.5-sonnet")
        assert provider.default_model == "anthropic/claude-3.5-sonnet"

    def test_name_property(self) -> None:
        """Test that name property returns 'openrouter'."""
        provider = OpenRouterProvider(api_key="test-key")
        assert provider.name == "openrouter"

    def test_list_models(self) -> None:
        """Test listing available models."""
        provider = OpenRouterProvider(api_key="test-key")
        models = provider.list_models()
        assert "openai/gpt-4o-mini" in models
        assert "openai/gpt-4o" in models
        assert "anthropic/claude-3.5-sonnet" in models
        assert "deepseek/deepseek-chat" in models
        assert "google/gemini-pro-1.5" in models
        assert "meta-llama/llama-3.1-405b-instruct" in models

    def test_base_url_default(self) -> None:
        """Test that base_url defaults to OpenRouter API."""
        provider = OpenRouterProvider(api_key="test-key")
        # Since base_url is passed to parent, we need to check it was set correctly
        # The parent OpenAICompatibleProvider should have the correct base_url
        assert "openrouter.ai" in provider.base_url

    def test_base_url_custom(self) -> None:
        """Test that custom base_url can be provided."""
        provider = OpenRouterProvider(
            api_key="test-key", base_url="https://custom.openrouter.ai/api/v1"
        )
        assert "custom.openrouter.ai" in provider.base_url

    def test_inherits_from_openai_compatible(self) -> None:
        """Test that OpenRouterProvider inherits from OpenAICompatibleProvider."""
        provider = OpenRouterProvider(api_key="test-key")
        from henchman.providers.openai_compat import OpenAICompatibleProvider

        assert isinstance(provider, OpenAICompatibleProvider)

    @pytest.mark.asyncio
    async def test_chat_completion_stream_inherited(self) -> None:
        """Test that chat_completion_stream method works (inherited from parent)."""
        provider = OpenRouterProvider(api_key="test-key")
        messages = [Message(role="user", content="Hello")]

        async def response() -> AsyncIterator[ChatCompletionChunk]:
            yield ChatCompletionChunk.model_validate(
                {
                    "id": "completion_1",
                    "created": 0,
                    "object": "chat.completion.chunk",
                    "model": "openai/gpt-4o-mini",
                    "choices": [
                        {"index": 0, "delta": {"content": "Test response"}, "finish_reason": "stop"}
                    ],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
                }
            )

        with patch.object(
            provider._client.chat.completions,
            "create",
            new=AsyncMock(return_value=SDKResponse(response())),
        ):
            chunks = [chunk async for chunk in provider.chat_completion_stream(messages)]

        assert "".join(chunk.content or "" for chunk in chunks) == "Test response"
        assert chunks[-1].finish_reason == FinishReason.STOP
        assert chunks[-1].usage == {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}
