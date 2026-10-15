"""Shared leaders retain role configuration and state during runtime switches."""

from types import SimpleNamespace
from typing import Any

import pytest

from henchman.agents.config import AgentConfig
from henchman.agents.orchestrator import Orchestrator
from henchman.cli.provider_switch import switch_runtime_provider
from henchman.config.schema import ProviderSettings, Settings
from henchman.core.agent import Agent
from henchman.providers import DeepSeekProvider, OllamaProvider, OpenRouterProvider
from henchman.providers.base import Message, ModelProvider
from henchman.tools.registry import ToolRegistry


def runtime_for(default: ModelProvider, **leader_options: Any) -> SimpleNamespace:
    settings = Settings(providers=ProviderSettings(ollama={
        "model": "saved-local", "base_url": "http://127.0.0.1:19876/v1",
    }))
    settings.agents.agents["tech_lead"] = AgentConfig(
        name="Configured Leader", role="tech_lead", description="Configured role",
        tools=["read_file"], system_prompt="Configured leader prompt", **leader_options,
    )
    orch = Orchestrator(default_provider=default, settings=settings)
    return SimpleNamespace(
        provider=default, settings=settings, orchestrator=orch, agent=orch.tech_lead,
        output_handler=SimpleNamespace(provider=default),
        command_processor=SimpleNamespace(provider=default),
        tool_executor=SimpleNamespace(provider=default),
        core_context=SimpleNamespace(provider=default),
    )


def retain_leader_state(
    runtime: SimpleNamespace,
) -> tuple[Agent, list[Message], ToolRegistry, str | None]:
    lead = runtime.orchestrator.tech_lead
    lead.messages.append(Message("user", "Keep the leader history"))
    return lead, lead.messages, lead.tool_registry, lead.messages[0].content


def test_switch_with_another_active_role_keeps_pinned_leader_and_updates_capacity() -> None:
    runtime = runtime_for(OpenRouterProvider(api_key="offline", model="initial"),
                          provider="ollama", model="pinned-leader")
    lead, history, tools, prompt = retain_leader_state(runtime)
    assert lead.provider.name == "ollama"
    assert lead.model == "pinned-leader"
    provider = lead.provider
    actor = runtime.orchestrator.pool.get_agent("engineer")
    runtime.agent = actor
    replacement = DeepSeekProvider(api_key="offline", model="replacement")
    switch_runtime_provider(runtime, replacement, context_length=16384)
    assert runtime.orchestrator.pool.get_agent("tech_lead") is lead
    assert lead.provider is provider
    assert lead.model == "pinned-leader"
    assert lead.messages is history and lead.tool_registry is tools
    assert lead.messages[0].content == prompt == "Configured leader prompt"
    assert lead.context_window == 16384 and lead.max_tokens == 12288
    assert actor.provider is replacement
    assert runtime.orchestrator.pool.get_agent("explorer").provider is replacement
    assert runtime.orchestrator.default_provider is replacement


def test_model_only_leader_tracks_live_default_connection_while_another_role_is_active() -> None:
    initial = OpenRouterProvider(api_key="offline", model="initial", temperature=0.2)
    runtime = runtime_for(initial, model="role-model")
    lead, history, tools, prompt = retain_leader_state(runtime)
    assert lead.provider is not initial
    assert lead.model == "role-model"
    runtime.agent = runtime.orchestrator.pool.get_agent("engineer")
    replacement = OllamaProvider(base_url="http://127.0.0.1:19877/v1", model="selected", max_tokens=1024)
    switch_runtime_provider(runtime, replacement, context_length=32768)
    assert runtime.orchestrator.pool.get_agent("tech_lead") is lead
    assert lead.provider.name == "ollama"
    assert lead.provider is not replacement
    assert isinstance(lead.provider, OllamaProvider)
    assert lead.provider.base_url == replacement.base_url
    assert lead.provider.request_defaults == {"max_tokens": 1024}
    assert lead.model == "role-model"
    assert lead.messages is history and lead.tool_registry is tools
    assert lead.messages[0].content == prompt
    assert lead.context_window == 32768 and lead.max_tokens == 24576
    assert runtime.agent.provider is replacement


def test_explicit_active_leader_selection_overrides_saved_pin_without_changing_saved_config() -> None:
    runtime = runtime_for(OllamaProvider(model="initial"), provider="ollama", model="pinned-leader")
    lead, history, tools, prompt = retain_leader_state(runtime)
    saved = runtime.settings.model_dump()
    replacement = OpenRouterProvider(api_key="offline", model="xiaomi/mimo-v2.6-pro")
    switch_runtime_provider(runtime, replacement, context_length=700000)
    assert runtime.orchestrator.pool.get_agent("tech_lead") is lead
    assert lead.provider is replacement
    assert lead.model == "xiaomi/mimo-v2.6-pro"
    assert lead.messages is history and lead.tool_registry is tools
    assert lead.messages[0].content == prompt
    assert lead.context_window == 700000 and lead.max_tokens == 525000
    assert runtime.settings.agents.model_dump() == saved["agents"]
    assert runtime.orchestrator.pool.get_agent("explorer").provider is replacement


def test_invalid_replacement_preparation_keeps_cached_leader_runtime_and_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for variable in ("OPENROUTER_API_KEY", "HENCHMAN_API_KEY"):
        monkeypatch.delenv(variable, raising=False)
    initial = OllamaProvider(model="initial")
    runtime = runtime_for(initial, model="role-model")
    lead, history, tools, prompt = retain_leader_state(runtime)
    provider = lead.provider
    actor = runtime.orchestrator.pool.get_agent("engineer")
    runtime.agent = actor
    saved = runtime.settings.model_dump()
    invalid = OpenRouterProvider(api_key="", model="replacement")
    with pytest.raises(ValueError, match="API key"):
        switch_runtime_provider(runtime, invalid, context_length=32768)
    assert runtime.provider is initial
    assert runtime.orchestrator.default_provider is initial
    assert runtime.orchestrator.pool.default_provider is initial
    assert actor.provider is initial
    assert lead.provider is provider
    assert lead.messages is history and lead.tool_registry is tools
    assert lead.messages[0].content == prompt
    assert runtime.settings.model_dump() == saved
    assert lead.context_window == 8000 and lead.max_tokens == 6000
