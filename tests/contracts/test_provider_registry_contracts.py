"""Contract tests for the ProviderRegistry and default registry factory.

These tests validate that the provider registry satisfies its
registration/lookup/creation behavioral contract.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from henchman.providers.base import Message, ModelProvider, StreamChunk, ToolDeclaration
from henchman.providers.registry import ProviderRegistry, get_default_registry


class _MockProvider(ModelProvider):
    """Minimal provider double for registry testing."""

    def __init__(self, **kwargs: object) -> None:
        self.api_key = kwargs.get("api_key", "mock-key")

    @property
    def name(self) -> str:
        return "mock"

    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        return
        yield  # pragma: no cover

    async def chat_completion(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration] | None = None,
    ) -> object:
        return type("Response", (), {
            "content": "mock",
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })()


class TestProviderRegistryContract:
    """ProviderRegistry must satisfy the registration/lookup contract."""

    def test_register_and_list(self) -> None:
        """Registered providers should appear in list_providers."""
        registry = ProviderRegistry()
        registry.register("mock", _MockProvider)
        providers = registry.list_providers()
        assert "mock" in providers

    def test_get_registered_provider(self) -> None:
        """get() should return the registered class."""
        registry = ProviderRegistry()
        registry.register("mock", _MockProvider)
        provider_class = registry.get("mock")
        assert provider_class is _MockProvider

    def test_get_unregistered_raises(self) -> None:
        """get() for an unregistered provider must raise KeyError."""
        registry = ProviderRegistry()
        with pytest.raises(KeyError, match="not registered"):
            registry.get("nonexistent")

    def test_create_provider_instance(self) -> None:
        """create() should instantiate the provider with kwargs."""
        registry = ProviderRegistry()
        registry.register("mock", _MockProvider)
        provider = registry.create("mock", api_key="test-key")
        assert isinstance(provider, _MockProvider)
        assert provider.api_key == "test-key"

    def test_create_with_default_kwargs(self) -> None:
        """create() should work without extra kwargs."""
        registry = ProviderRegistry()
        registry.register("mock", _MockProvider)
        provider = registry.create("mock")
        assert isinstance(provider, _MockProvider)

    def test_list_providers_empty(self) -> None:
        """A fresh registry should have no providers."""
        registry = ProviderRegistry()
        assert registry.list_providers() == []

    def test_multiple_registrations(self) -> None:
        """Multiple providers can be registered and listed."""
        registry = ProviderRegistry()
        registry.register("a", _MockProvider)
        registry.register("b", _MockProvider)
        assert set(registry.list_providers()) == {"a", "b"}


class TestDefaultRegistryContract:
    """get_default_registry() must contain all built-in providers."""

    def test_default_registry_contains_all_builtins(self) -> None:
        """get_default_registry() must include all expected providers."""
        registry = get_default_registry()
        providers = registry.list_providers()
        for name in ["anthropic", "deepseek", "ollama", "openrouter", "openai_compat"]:
            assert name in providers, f"Missing built-in provider: {name}"

    def test_default_registry_is_singleton(self) -> None:
        """get_default_registry() should return the same instance."""
        registry_a = get_default_registry()
        registry_b = get_default_registry()
        assert registry_a is registry_b

    def test_default_providers_are_model_provider_subclasses(self) -> None:
        """All default-registry providers must be ModelProvider subclasses."""
        registry = get_default_registry()
        for name in registry.list_providers():
            provider_class = registry.get(name)
            assert issubclass(provider_class, ModelProvider), (
                f"Provider '{name}' is not a ModelProvider subclass"
            )
