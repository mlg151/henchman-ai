"""Tests for DeepSeek provider."""

import os
from unittest.mock import patch

from henchman.providers.deepseek import DeepSeekProvider


class TestDeepSeekProvider:
    """Tests for DeepSeekProvider."""

    def test_instantiation_with_explicit_key(self) -> None:
        """Test creating provider with explicit API key."""
        provider = DeepSeekProvider(api_key="test-deepseek-key")
        assert provider.api_key == "test-deepseek-key"
        assert provider.base_url == "https://api.deepseek.com"
        assert provider.default_model == "deepseek-chat"

    def test_instantiation_with_env_var(self) -> None:
        """Test creating provider with environment variable."""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "env-key"}):
            provider = DeepSeekProvider()
            assert provider.api_key == "env-key"

    def test_instantiation_without_key(self) -> None:
        """Test creating provider without API key (empty string)."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove DEEPSEEK_API_KEY if it exists
            os.environ.pop("DEEPSEEK_API_KEY", None)
            provider = DeepSeekProvider()
            assert provider.api_key == ""

    def test_custom_model(self) -> None:
        """Test creating provider with custom model."""
        provider = DeepSeekProvider(api_key="test-key", model="deepseek-reasoner")
        assert provider.default_model == "deepseek-reasoner"

    def test_name_property(self) -> None:
        """Test that name property returns 'deepseek'."""
        provider = DeepSeekProvider(api_key="test-key")
        assert provider.name == "deepseek"

    def test_list_models(self) -> None:
        """Test listing available models."""
        provider = DeepSeekProvider(api_key="test-key")
        models = provider.list_models()
        assert "deepseek-chat" in models
        assert "deepseek-reasoner" in models

    def test_inherits_from_openai_compatible(self) -> None:
        """Test that DeepSeekProvider inherits from OpenAICompatibleProvider."""
        from henchman.providers.openai_compat import OpenAICompatibleProvider

        provider = DeepSeekProvider(api_key="test-key")
        assert isinstance(provider, OpenAICompatibleProvider)
