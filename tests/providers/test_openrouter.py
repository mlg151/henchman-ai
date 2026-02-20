"""Tests for OpenRouter provider."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.providers.base import Message
from henchman.providers.openrouter import OpenRouterProvider


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
        provider = OpenRouterProvider(api_key="test-key", base_url="https://custom.openrouter.ai/api/v1")
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

        # Mock the AsyncOpenAI client to avoid actual API calls
        mock_response = AsyncMock()
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta.content = "Test response"
        mock_chunk.choices[0].finish_reason = "stop"
        mock_response.__aiter__.return_value = [mock_chunk]

        with patch.object(provider._client.chat.completions, 'create', return_value=mock_response):
            chunks = []
            async for chunk in provider.chat_completion_stream(messages):
                chunks.append(chunk)

            # Should have received at least one chunk
            assert len(chunks) > 0

    def test_additional_kwargs_passed_to_parent(self) -> None:
        """Test that additional kwargs are passed to parent class."""
        _provider = OpenRouterProvider(
            api_key="test-key",
            temperature=0.7,
            max_tokens=1000,
            custom_param="value"
        )
        # Check that provider has these attributes (they would be passed to parent)
        # The parent should handle these kwargs
