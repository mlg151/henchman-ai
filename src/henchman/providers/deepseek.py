"""DeepSeek provider implementation."""

import os

from henchman.providers.openai_compat import OpenAICompatibleProvider

__all__ = ["DeepSeekProvider"]


class DeepSeekProvider(OpenAICompatibleProvider):
    """Provider for DeepSeek API.

    DeepSeek uses an OpenAI-compatible API, so this provider extends
    OpenAICompatibleProvider with DeepSeek-specific defaults.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "deepseek-chat",
    ) -> None:
        """Initialize the DeepSeek provider.

        Args:
            api_key: DeepSeek API key. If not provided, reads from
                DEEPSEEK_API_KEY environment variable.
            model: Model to use. Defaults to "deepseek-chat".
        """
        resolved_key = api_key if api_key is not None else os.environ.get("DEEPSEEK_API_KEY", "")
        super().__init__(
            api_key=resolved_key,
            base_url="https://api.deepseek.com",
            default_model=model,
        )

    @property
    def name(self) -> str:
        """The unique name of this provider."""
        return "deepseek"

    def list_models(self) -> list[str]:
        """List available DeepSeek models.

        Returns:
            List of model names available from DeepSeek.
        """
        return ["deepseek-chat", "deepseek-reasoner"]
