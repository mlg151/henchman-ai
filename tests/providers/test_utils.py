"""Tests for provider utility functions."""

import os
from unittest.mock import patch

from henchman.providers.utils import (
    get_api_key_for_provider,
    get_env_var_for_provider,
)


class TestGetEnvVarForProvider:
    """Tests for get_env_var_for_provider function."""

    def test_deepseek(self) -> None:
        """Test environment variable mapping for DeepSeek."""
        result = get_env_var_for_provider("deepseek")
        assert result == "DEEPSEEK_API_KEY"

    def test_openai(self) -> None:
        """Test environment variable mapping for OpenAI."""
        result = get_env_var_for_provider("openai")
        assert result == "OPENAI_API_KEY"

    def test_anthropic(self) -> None:
        """Test environment variable mapping for Anthropic."""
        result = get_env_var_for_provider("anthropic")
        assert result == "ANTHROPIC_API_KEY"

    def test_openrouter(self) -> None:
        """Test environment variable mapping for OpenRouter."""
        result = get_env_var_for_provider("openrouter")
        assert result == "OPENROUTER_API_KEY"

    def test_openai_compat(self) -> None:
        """Test environment variable mapping for OpenAI-compatible providers."""
        result = get_env_var_for_provider("openai_compat")
        assert result == "HENCHMAN_API_KEY"

    def test_together(self) -> None:
        """Test environment variable mapping for Together AI."""
        result = get_env_var_for_provider("together")
        assert result == "TOGETHER_API_KEY"

    def test_groq(self) -> None:
        """Test environment variable mapping for Groq."""
        result = get_env_var_for_provider("groq")
        assert result == "GROQ_API_KEY"

    def test_fireworks(self) -> None:
        """Test environment variable mapping for Fireworks AI."""
        result = get_env_var_for_provider("fireworks")
        assert result == "FIREWORKS_API_KEY"

    def test_ollama(self) -> None:
        """Test environment variable mapping for Ollama (no API key)."""
        result = get_env_var_for_provider("ollama")
        assert result == ""

    def test_unknown_provider(self) -> None:
        """Test environment variable mapping for unknown provider."""
        result = get_env_var_for_provider("unknown_provider")
        # Unknown providers default to HENCHMAN_API_KEY as fallback
        assert result == "HENCHMAN_API_KEY"


class TestGetApiKeyForProvider:
    """Tests for get_api_key_for_provider function."""

    def test_deepseek_with_key(self) -> None:
        """Test API key retrieval for DeepSeek with environment variable set."""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-deepseek-key"}):
            result = get_api_key_for_provider("deepseek")
            assert result == "test-deepseek-key"

    def test_deepseek_without_key(self) -> None:
        """Test API key retrieval for DeepSeek without environment variable."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_api_key_for_provider("deepseek")
            assert result is None

    def test_openrouter_with_key(self) -> None:
        """Test API key retrieval for OpenRouter with OPENROUTER_API_KEY set."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-openrouter-key"}):
            result = get_api_key_for_provider("openrouter")
            assert result == "test-openrouter-key"

    def test_openrouter_with_henchman_fallback(self) -> None:
        """Test API key retrieval for OpenRouter with HENCHMAN_API_KEY fallback."""
        with patch.dict(os.environ, {"HENCHMAN_API_KEY": "test-henchman-key"}):
            # Ensure OPENROUTER_API_KEY is not set
            os.environ.pop("OPENROUTER_API_KEY", None)
            result = get_api_key_for_provider("openrouter")
            assert result == "test-henchman-key"

    def test_openrouter_precedence(self) -> None:
        """Test that OPENROUTER_API_KEY takes precedence over HENCHMAN_API_KEY."""
        with patch.dict(os.environ, {
            "OPENROUTER_API_KEY": "test-openrouter-key",
            "HENCHMAN_API_KEY": "test-henchman-key"
        }):
            result = get_api_key_for_provider("openrouter")
            assert result == "test-openrouter-key"

    def test_openai_compat_with_henchman_key(self) -> None:
        """Test API key retrieval for OpenAI-compatible with HENCHMAN_API_KEY."""
        with patch.dict(os.environ, {"HENCHMAN_API_KEY": "test-henchman-key"}):
            result = get_api_key_for_provider("openai_compat")
            assert result == "test-henchman-key"

    def test_together_with_henchman_key(self) -> None:
        """Test API key retrieval for Together AI with HENCHMAN_API_KEY."""
        with patch.dict(os.environ, {"HENCHMAN_API_KEY": "test-henchman-key"}):
            result = get_api_key_for_provider("together")
            assert result == "test-henchman-key"

    def test_groq_with_henchman_key(self) -> None:
        """Test API key retrieval for Groq with HENCHMAN_API_KEY."""
        with patch.dict(os.environ, {"HENCHMAN_API_KEY": "test-henchman-key"}):
            result = get_api_key_for_provider("groq")
            assert result == "test-henchman-key"

    def test_fireworks_with_henchman_key(self) -> None:
        """Test API key retrieval for Fireworks AI with HENCHMAN_API_KEY."""
        with patch.dict(os.environ, {"HENCHMAN_API_KEY": "test-henchman-key"}):
            result = get_api_key_for_provider("fireworks")
            assert result == "test-henchman-key"

    def test_ollama_no_key(self) -> None:
        """Test API key retrieval for Ollama (no API key needed)."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_api_key_for_provider("ollama")
            assert result is None

    def test_anthropic_with_key(self) -> None:
        """Test API key retrieval for Anthropic with environment variable set."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-anthropic-key"}):
            result = get_api_key_for_provider("anthropic")
            assert result == "test-anthropic-key"

    def test_unknown_provider(self) -> None:
        """Test API key retrieval for unknown provider."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_api_key_for_provider("unknown_provider")
            assert result is None
