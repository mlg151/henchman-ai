"""Tests for provider registry."""

import pytest

from henchman.providers.base import ModelProvider, StreamChunk
from henchman.providers.deepseek import DeepSeekProvider
from henchman.providers.registry import ProviderRegistry, get_default_registry


class MockProvider(ModelProvider):
    """Mock provider for testing."""

    @property
    def name(self) -> str:
        return "mock"

    async def chat_completion_stream(self, messages, tools=None, **kwargs):  # noqa: ARG002
        yield StreamChunk(content="mock response")


class TestProviderRegistry:
    """Tests for ProviderRegistry."""

    def test_register_provider_class(self) -> None:
        """Test registering a provider class."""
        registry = ProviderRegistry()
        registry.register("mock", MockProvider)
        assert "mock" in registry.list_providers()

    def test_get_provider_class(self) -> None:
        """Test getting a registered provider class."""
        registry = ProviderRegistry()
        registry.register("mock", MockProvider)
        provider_class = registry.get("mock")
        assert provider_class == MockProvider

    def test_get_unregistered_provider(self) -> None:
        """Test getting an unregistered provider raises error."""
        registry = ProviderRegistry()
        with pytest.raises(KeyError):
            registry.get("nonexistent")

    def test_list_providers(self) -> None:
        """Test listing all registered providers."""
        registry = ProviderRegistry()
        registry.register("mock1", MockProvider)
        registry.register("mock2", MockProvider)
        providers = registry.list_providers()
        assert "mock1" in providers
        assert "mock2" in providers

    def test_create_provider_instance(self) -> None:
        """Test creating a provider instance from registry."""
        registry = ProviderRegistry()
        registry.register("mock", MockProvider)
        provider = registry.create("mock")
        assert isinstance(provider, MockProvider)
        assert provider.name == "mock"

    def test_create_provider_with_kwargs(self) -> None:
        """Test creating provider with constructor arguments."""
        registry = ProviderRegistry()
        registry.register("deepseek", DeepSeekProvider)
        provider = registry.create("deepseek", api_key="test-key", model="deepseek-reasoner")
        assert isinstance(provider, DeepSeekProvider)
        assert provider.api_key == "test-key"
        assert provider.default_model == "deepseek-reasoner"


class TestDefaultRegistry:
    """Tests for the default provider registry."""

    def test_default_registry_has_deepseek(self) -> None:
        """Test that default registry includes DeepSeek provider."""
        registry = get_default_registry()
        assert "deepseek" in registry.list_providers()

    def test_default_registry_singleton(self) -> None:
        """Test that get_default_registry returns same instance."""
        registry1 = get_default_registry()
        registry2 = get_default_registry()
        assert registry1 is registry2
