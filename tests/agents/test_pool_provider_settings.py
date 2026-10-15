"""Configured provider selection and inheritance in delegated agents."""

import pytest

from henchman.agents.config import AgentConfig
from henchman.agents.pool import AgentPool
from henchman.config.schema import ProviderSettings
from henchman.core.eventbus import EventBus
from henchman.providers import (
    AnthropicProvider,
    DeepSeekProvider,
    OllamaProvider,
    OpenRouterProvider,
)
from henchman.providers.base import Message
from henchman.providers.openai_compat import OpenAICompatibleProvider
from henchman.tools.registry import ToolRegistry


def _config(role: str, **overrides: str) -> AgentConfig:
    return AgentConfig(name=role, role=role, description="test", **overrides)


def test_explicit_provider_uses_saved_settings_without_registry() -> None:
    settings = ProviderSettings(openrouter={
        "api_key": "saved-key", "model": "vendor/coder", "base_url": "https://router.test/v1",
    })
    pool = AgentPool(
        {"coder": _config("coder", provider="openrouter")}, OllamaProvider(),
        None, ToolRegistry(), EventBus(), provider_settings=settings,
    )
    agent = pool.get_agent("coder")
    assert agent.provider.name == "openrouter"
    assert agent.provider.api_key == "saved-key"
    assert agent.provider.base_url == "https://router.test/v1"
    assert agent.model == "vendor/coder"


def test_model_override_clones_live_generic_provider() -> None:
    default = OpenAICompatibleProvider(
        "live-key", "https://live.test/v1", "original", temperature=0.25,
    )
    pool = AgentPool(
        {"coder": _config("coder", model="specialized")}, default,
        None, ToolRegistry(), EventBus(),
        provider_settings=ProviderSettings(default="openrouter"),
    )
    agent = pool.get_agent("coder")
    assert agent.provider is not default
    assert agent.provider.default_model == "specialized"
    assert agent.provider.api_key == "live-key"
    assert agent.provider.base_url == "https://live.test/v1"
    assert agent.provider.request_defaults == {"temperature": 0.25}
    assert default.default_model == "original"


def test_switch_default_preserves_history_and_explicit_overrides() -> None:
    default = OllamaProvider(model="initial")
    configs = {
        "inherited": _config("inherited"),
        "pinned": _config("pinned", provider="ollama", model="pinned"),
        "model_only": _config("model_only", model="specialized"),
        "future": _config("future"),
    }
    pool = AgentPool(configs, default, None, ToolRegistry(), EventBus())
    inherited = pool.get_agent("inherited")
    pinned = pool.get_agent("pinned")
    model_only = pool.get_agent("model_only")
    inherited.messages.append(Message(role="user", content="remember this"))
    messages = inherited.messages
    replacement = OpenRouterProvider(api_key="router-key", model="vendor/coder")
    pool.set_default_provider(replacement)
    assert inherited.provider is replacement
    assert inherited.model == "vendor/coder"
    assert inherited.messages is messages
    assert inherited.messages[-1].content == "remember this"
    assert pinned.provider.name == "ollama"
    assert pinned.model == "pinned"
    assert model_only.provider.name == "openrouter"
    assert model_only.provider.api_key == "router-key"
    assert model_only.provider.default_model == "specialized"
    assert model_only.model == "specialized"
    assert pool.get_agent("future").provider is replacement


def test_failed_override_preparation_does_not_mutate_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("HENCHMAN_API_KEY", raising=False)
    default = OllamaProvider()
    pool = AgentPool(
        {"inherited": _config("inherited"), "model_only": _config("model_only", model="specialized")},
        default, None, ToolRegistry(), EventBus(),
    )
    inherited = pool.get_agent("inherited")
    model_only = pool.get_agent("model_only")
    original_override = model_only.provider
    replacement = OpenRouterProvider(api_key="")
    with pytest.raises(ValueError, match="API key"):
        pool.set_default_provider(replacement)
    assert pool.default_provider is default
    assert inherited.provider is default
    assert model_only.provider is original_override


@pytest.mark.parametrize("switch", [False, True])
def test_deepseek_model_override_preserves_live_connection(switch: bool) -> None:
    default = DeepSeekProvider(
        api_key="live-key", base_url="https://proxy.test/deepseek", temperature=0.4,
    )
    pool = AgentPool(
        {"coder": _config("coder", model="deepseek-reasoner")},
        OllamaProvider() if switch else default, None, ToolRegistry(), EventBus(),
    )
    agent = pool.get_agent("coder")
    messages = agent.messages
    if switch:
        pool.set_default_provider(default)
    assert agent.provider is not default
    assert agent.provider.name == "deepseek"
    assert agent.provider.api_key == "live-key"
    assert agent.provider.base_url == "https://proxy.test/deepseek"
    assert agent.provider.request_defaults == {"temperature": 0.4}
    assert agent.provider.default_model == "deepseek-reasoner"
    assert default.default_model == "deepseek-chat"
    assert agent.messages is messages


@pytest.mark.parametrize("switch", [False, True])
def test_native_model_override_preserves_live_configuration(switch: bool) -> None:
    default = AnthropicProvider(
        api_key="native-key", model="original", max_tokens=4096,
        max_retries=7, tokens_per_minute=12345,
    )
    pool = AgentPool(
        {"coder": _config("coder", model="specialized")},
        OllamaProvider() if switch else default, None, ToolRegistry(), EventBus(),
        provider_settings=ProviderSettings(anthropic={"max_tokens": 1024}),
    )
    agent = pool.get_agent("coder")
    if switch:
        pool.set_default_provider(default)
    assert isinstance(agent.provider, AnthropicProvider)
    assert agent.provider is not default
    assert agent.provider.api_key == "native-key"
    assert agent.provider.default_model == "specialized"
    assert agent.provider.max_tokens == 4096
    assert agent.provider.max_retries == 7
    assert agent.provider._rate_limiter.tokens_per_minute == 12345
    assert default.default_model == "original"
