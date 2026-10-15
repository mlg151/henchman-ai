"""The actual leader uses the pool's configuration and lifecycle."""

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock

import pytest

from henchman.agents.config import AgentConfig
from henchman.agents.orchestrator import Orchestrator
from henchman.agents.pool import AgentPool, ContextConfig
from henchman.config.schema import ProviderSettings, Settings
from henchman.core.eventbus import EventBus
from henchman.providers.anthropic import AnthropicProvider
from henchman.providers.base import FinishReason, StreamChunk
from henchman.providers.factory import create_configured_provider
from henchman.providers.ollama import OllamaProvider
from henchman.providers.openai_compat import OpenAICompatibleProvider
from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.registry import ToolRegistry

PROVIDERS = ["openrouter", "openai_compat", "ollama", "deepseek", "anthropic"]


def leader_config(**overrides: Any) -> AgentConfig:
    return AgentConfig(
        name="Configured leader", role="tech_lead", description="Configured identity",
        **overrides,
    )


def saved_provider_settings(name: str) -> ProviderSettings:
    options: dict[str, Any] = {"model": "saved-model", "max_tokens": 1234}
    if name != "ollama":
        options["api_key"] = "saved-test-key"
    if name != "anthropic":
        options.update(base_url="https://saved.test/v1", temperature=0.25)
    else:
        options.update(max_retries=5, tokens_per_minute=12345)
    settings = ProviderSettings()
    setattr(settings, name, options)
    return settings


@pytest.mark.parametrize("name", PROVIDERS)
@pytest.mark.parametrize("model", [None, "leader-model"])
def test_actual_leader_uses_saved_explicit_provider_settings(
    name: str, model: str | None,
) -> None:
    settings = Settings(providers=saved_provider_settings(name))
    settings.agents.agents["tech_lead"] = leader_config(provider=name, model=model)
    inherited = OllamaProvider(model="inherited")
    orch = Orchestrator(inherited, settings=settings)
    leader = orch.tech_lead
    expected = create_configured_provider(
        settings.providers, provider_name=name, model=model
    )

    assert type(leader.provider) is type(expected)
    assert leader.provider is not inherited
    assert isinstance(leader.provider, AnthropicProvider | OpenAICompatibleProvider)
    assert leader.model == leader.provider.default_model == (model or "saved-model")
    assert leader.provider.prepare_output_budget(999).output_tokens == 1234
    if isinstance(leader.provider, AnthropicProvider):
        assert leader.provider.api_key == "saved-test-key"
        assert leader.provider.max_retries == 5
        assert leader.provider._rate_limiter.tokens_per_minute == 12345
    else:
        assert isinstance(leader.provider, OpenAICompatibleProvider)
        assert leader.provider.base_url == "https://saved.test/v1"
        assert leader.provider.request_defaults["temperature"] == 0.25
        assert leader.provider.api_key == (
            "ollama" if name == "ollama" else "saved-test-key"
        )
    assert leader is orch.pool.get_agent("tech_lead")


@pytest.mark.parametrize("name", PROVIDERS)
def test_actual_leader_model_only_override_preserves_live_provider(name: str) -> None:
    saved = saved_provider_settings(name)
    live = create_configured_provider(saved, provider_name=name)
    settings = Settings()
    settings.agents.agents["tech_lead"] = leader_config(model="leader-model")
    orch = Orchestrator(live, settings=settings)
    provider = orch.tech_lead.provider

    assert provider is not live and type(provider) is type(live)
    assert isinstance(provider, AnthropicProvider | OpenAICompatibleProvider)
    assert isinstance(live, AnthropicProvider | OpenAICompatibleProvider)
    assert orch.tech_lead.model == provider.default_model == "leader-model"
    assert live.default_model == "saved-model"
    assert provider.prepare_output_budget(999).output_tokens == 1234
    if isinstance(provider, AnthropicProvider):
        assert provider.api_key == "saved-test-key"
        assert provider.max_retries == 5
        assert provider._rate_limiter.tokens_per_minute == 12345
    else:
        assert isinstance(provider, OpenAICompatibleProvider)
        assert provider.base_url == "https://saved.test/v1"
        assert provider.request_defaults["temperature"] == 0.25


@pytest.mark.parametrize(("configured", "runtime", "expected"), [
    ("configured", "runtime", "runtime"),
    ("", "runtime", "runtime"),
    ("configured", None, "configured"),
    ("configured", "", "configured"),
    ("", None, ""),
    ("", "", ""),
    (None, None, None),
    (None, "", None),
])
def test_leader_prompt_precedence_and_identity(
    configured: str | None, runtime: str | None, expected: str | None,
) -> None:
    settings = Settings()
    settings.agents.agents["tech_lead"] = leader_config(system_prompt=configured)
    orch = Orchestrator(
        OllamaProvider(), settings=settings, system_prompt=runtime,
        environment_context="UNIQUE ENVIRONMENT CONTEXT",
    )
    prompt = orch.tech_lead.system_prompt
    if expected is not None:
        assert prompt == expected
    else:
        assert "UNIQUE ENVIRONMENT CONTEXT" in prompt
        assert "Primary Coding Agent" in prompt
        assert "invoke_subagent" in prompt
    assert orch.tech_lead is orch.pool.get_agent("tech_lead")
    assert orch.tech_lead.identity is not None
    assert orch.tech_lead.identity.name == "Configured leader"
    assert orch.tech_lead.identity.description == "Configured identity"
    assert not orch.tech_lead._stall.enabled


def test_pool_supports_leader_runtime_prompt_without_orchestrator() -> None:
    pool = AgentPool(
        {"tech_lead": leader_config(system_prompt="configured")}, OllamaProvider(),
        None, ToolRegistry(), EventBus(),
        context_config=ContextConfig(leader_system_prompt="runtime"),
    )
    assert pool.get_agent("tech_lead").system_prompt == "runtime"


async def test_normal_and_direct_leader_share_history_and_reset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OllamaProvider()

    async def stream(*_args: Any, **_kwargs: Any) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content="Acknowledged.", finish_reason=FinishReason.STOP)

    monkeypatch.setattr(provider, "chat_completion_stream", stream)
    orch = Orchestrator(provider, system_prompt="Shared prompt")
    leader = orch.tech_lead
    assert leader is orch.pool.get_agent("tech_lead")
    _normal = [event async for event in orch.run("First request")]
    _direct = [event async for event in orch.run_direct("tech_lead", "Second request")]
    user_content = [message.content for message in leader.messages if message.role == "user"]
    assert "First request" in user_content
    assert "Second request" in user_content
    orch.pool.reset_agent("tech_lead")
    assert not any(message.role == "user" for message in leader.messages)
    assert leader is orch.pool.get_agent("tech_lead")
    assert leader.system_prompt == "Shared prompt"


class WriteTool(Tool):
    name = "custom_write"
    description = "Configured write operation"
    kind = ToolKind.WRITE

    async def execute(self, **params: object) -> ToolResult:
        return ToolResult("written")


async def test_pool_leader_retains_custom_scope_and_inherits_live_root_approval() -> None:
    parent = ToolRegistry()
    parent.register(WriteTool())
    parent.set_confirmation_handler(AsyncMock(return_value=False))
    settings = Settings()
    settings.agents.agents["tech_lead"] = leader_config(tools=["custom_write"])
    orch = Orchestrator(OllamaProvider(), settings=settings, tool_registry=parent)
    registry = orch.pool.get_agent("tech_lead").tool_registry
    assert registry is orch.tech_lead.tool_registry
    assert registry.list_tools() == ["custom_write"]
    assert registry.get("delegate_task") is None
    assert parent.get("delegate_task") is not None
    assert not (await registry.execute("custom_write", {})).success
    parent.add_auto_approve_policy("custom_write")
    assert (await registry.execute("custom_write", {})).success
    parent.set_plan_mode(enabled=True)
    assert not (await registry.execute("custom_write", {})).success
