"""Ollama local model provider.

This provider connects to a local Ollama instance which provides an
OpenAI-compatible API.
"""

import os

from henchman.providers.openai_compat import OpenAICompatibleProvider

__all__ = ["OllamaProvider"]

# Commonly available Ollama models
OLLAMA_MODELS = [
    "llama3.2",
    "llama3.1",
    "llama3",
    "llama2",
    "codellama",
    "qwen2.5",
    "qwen2.5-coder",
    "mistral",
    "mixtral",
    "phi3",
    "gemma2",
    "deepseek-coder-v2",
]


class OllamaProvider(OpenAICompatibleProvider):
    """Provider for local Ollama models.

    Ollama provides an OpenAI-compatible API at http://localhost:11434/v1.
    No API key is required for local usage.

    Example:
        >>> provider = OllamaProvider(model="llama3.2")
        >>> async for chunk in provider.chat_completion_stream(messages):
        ...     print(chunk.content, end="")
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str = "llama3.2",
    ) -> None:
        """Initialize the Ollama provider.

        Args:
            base_url: Ollama API URL. Defaults to OLLAMA_HOST env var or localhost.
            model: Default model to use.
        """
        default_url = os.getenv("OLLAMA_HOST", "http://localhost:11434/v1")
        actual_url = base_url or default_url

        super().__init__(
            api_key="ollama",  # Ollama doesn't need a real key
            base_url=actual_url,
            default_model=model,
        )

    @property
    def name(self) -> str:
        """The unique name of this provider."""
        return "ollama"

    @staticmethod
    def list_models() -> list[str]:
        """List commonly available Ollama models.

        Note: Actual available models depend on what's installed locally.

        Returns:
            List of commonly available model names.
        """
        return OLLAMA_MODELS.copy()
