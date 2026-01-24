"""Tests for Ollama provider."""

from unittest.mock import patch

from henchman.providers.base import ModelProvider
from henchman.providers.ollama import OllamaProvider
from henchman.providers.openai_compat import OpenAICompatibleProvider


class TestOllamaProvider:
    """Tests for OllamaProvider."""

    def test_instantiation_default(self) -> None:
        """Test creating provider with defaults."""
        provider = OllamaProvider()
        assert provider.base_url == "http://localhost:11434/v1"
        assert provider.default_model == "llama3.2"

    def test_custom_base_url(self) -> None:
        """Test creating provider with custom base URL."""
        provider = OllamaProvider(base_url="http://192.168.1.100:11434/v1")
        assert provider.base_url == "http://192.168.1.100:11434/v1"

    def test_custom_model(self) -> None:
        """Test creating provider with custom model."""
        provider = OllamaProvider(model="codellama")
        assert provider.default_model == "codellama"

    def test_base_url_from_env(self) -> None:
        """Test base URL from environment variable."""
        with patch.dict("os.environ", {"OLLAMA_HOST": "http://remote:11434/v1"}):
            provider = OllamaProvider()
            assert provider.base_url == "http://remote:11434/v1"

    def test_name_property(self) -> None:
        """Test that name property returns 'ollama'."""
        provider = OllamaProvider()
        assert provider.name == "ollama"

    def test_list_models(self) -> None:
        """Test listing suggested models."""
        provider = OllamaProvider()
        models = provider.list_models()
        assert "llama3.2" in models
        assert "codellama" in models
        assert "qwen2.5" in models

    def test_is_model_provider(self) -> None:
        """Test that OllamaProvider implements ModelProvider."""
        provider = OllamaProvider()
        assert isinstance(provider, ModelProvider)

    def test_inherits_from_openai_compatible(self) -> None:
        """Test that OllamaProvider inherits from OpenAICompatibleProvider."""
        provider = OllamaProvider()
        assert isinstance(provider, OpenAICompatibleProvider)

    def test_no_api_key_required(self) -> None:
        """Test that Ollama doesn't require an API key."""
        provider = OllamaProvider()
        # Should have dummy key since OpenAI client requires one
        assert provider.api_key == "ollama"
