"""OpenRouter provider implementation."""

import os
from typing import Any

from henchman.providers.openai_compat import OpenAICompatibleProvider

__all__ = ["OpenRouterProvider"]


class OpenRouterProvider(OpenAICompatibleProvider):
    """Provider for OpenRouter API.

    OpenRouter uses an OpenAI-compatible API, so this provider extends
    OpenAICompatibleProvider with OpenRouter-specific defaults.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "openai/gpt-4o-mini",
        **kwargs: Any,
    ) -> None:
        """Initialize the OpenRouter provider.

        Args:
            api_key: OpenRouter API key. If not provided, reads from
                OPENROUTER_API_KEY environment variable.
            model: Model to use. Defaults to "openai/gpt-4o-mini".
            **kwargs: Additional parameters passed to OpenAICompatibleProvider.
        """
        resolved_key = api_key if api_key is not None else os.environ.get("OPENROUTER_API_KEY", "")

        # OpenRouter recommends these headers
        base_url = kwargs.pop("base_url", "https://openrouter.ai/api/v1")

        super().__init__(
            api_key=resolved_key,
            base_url=base_url,
            default_model=model,
        )

    @property
    def name(self) -> str:
        """The unique name of this provider."""
        return "openrouter"

    def list_models(self) -> list[str]:
        """List commonly used OpenRouter models.

        Returns:
            List of model names available from OpenRouter.
        """
        return [
            "openai/gpt-4o-mini",
            "openai/gpt-4o",
            "anthropic/claude-3.5-sonnet",
            "deepseek/deepseek-chat",
            "google/gemini-pro-1.5",
            "meta-llama/llama-3.1-405b-instruct",
        ]
