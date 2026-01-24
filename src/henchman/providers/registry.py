"""Provider registry for discovering and creating providers."""

from typing import Any

from henchman.providers.base import ModelProvider

__all__ = ["ProviderRegistry", "get_default_registry"]


class ProviderRegistry:
    """Registry for model providers.

    Allows registering provider classes by name and creating instances
    with configuration.
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._providers: dict[str, type[ModelProvider]] = {}

    def register(self, name: str, provider_class: type[ModelProvider]) -> None:
        """Register a provider class.

        Args:
            name: Unique name for the provider.
            provider_class: The provider class to register.
        """
        self._providers[name] = provider_class

    def get(self, name: str) -> type[ModelProvider]:
        """Get a registered provider class.

        Args:
            name: Name of the provider.

        Returns:
            The provider class.

        Raises:
            KeyError: If the provider is not registered.
        """
        if name not in self._providers:
            raise KeyError(f"Provider '{name}' not registered")
        return self._providers[name]

    def list_providers(self) -> list[str]:
        """List all registered provider names.

        Returns:
            List of provider names.
        """
        return list(self._providers.keys())

    def create(self, name: str, **kwargs: Any) -> ModelProvider:
        """Create a provider instance.

        Args:
            name: Name of the provider.
            **kwargs: Arguments passed to the provider constructor.

        Returns:
            A new provider instance.

        Raises:
            KeyError: If the provider is not registered.
        """
        provider_class = self.get(name)
        return provider_class(**kwargs)


# Singleton default registry
_default_registry: ProviderRegistry | None = None


def get_default_registry() -> ProviderRegistry:
    """Get the default provider registry.

    The default registry is pre-populated with built-in providers.

    Returns:
        The default ProviderRegistry instance.
    """
    global _default_registry

    if _default_registry is None:
        _default_registry = ProviderRegistry()

        # Register built-in providers
        from henchman.providers.anthropic import AnthropicProvider
        from henchman.providers.deepseek import DeepSeekProvider
        from henchman.providers.ollama import OllamaProvider

        _default_registry.register("deepseek", DeepSeekProvider)
        _default_registry.register("anthropic", AnthropicProvider)
        _default_registry.register("ollama", OllamaProvider)

    return _default_registry
