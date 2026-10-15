"""Session model switches update team context policy without losing state."""

from types import SimpleNamespace
from typing import Any

import pytest

from henchman.agents.config import AgentConfig
from henchman.agents.orchestrator import Orchestrator
from henchman.cli.provider_switch import switch_runtime_provider
from henchman.config.schema import Settings
from henchman.core.agent import Agent
from henchman.providers import OllamaProvider, OpenRouterProvider
from henchman.providers.base import Message


def _runtime() -> SimpleNamespace:
    settings = Settings(context={"max_tokens": 4096, "compaction_threshold": 0.5})
    provider = OllamaProvider(model="initial")
    orch = Orchestrator(default_provider=provider, settings=settings)
    orch.pool.configs.update(
        {
            "pinned": AgentConfig(
                name="Pinned", role="pinned", description="Test", provider="ollama", model="pinned"
            ),
            "model_only": AgentConfig(
                name="Model", role="model_only", description="Test", model="specialized"
            ),
        }
    )
    return SimpleNamespace(
        provider=provider,
        agent=orch.tech_lead,
        orchestrator=orch,
        settings=settings,
    )


def test_context_override_reaches_lead_cached_and_future_agents_and_survives_switch() -> None:
    runtime = _runtime()
    orch = runtime.orchestrator
    agents = [
        orch.tech_lead,
        orch.pool.get_agent("explorer"),
        orch.pool.get_agent("pinned"),
        orch.pool.get_agent("model_only"),
    ]
    pinned_provider = agents[2].provider
    histories = []
    registries = []
    for agent in agents:
        agent.messages.append(Message(role="user", content="Keep this conversation"))
        histories.append(agent.messages)
        registries.append(agent.tool_registry)
    replacement = OpenRouterProvider(api_key="test-key", model="new-model", max_tokens=512)

    switch_runtime_provider(runtime, replacement, context_length=3072)

    assert runtime.settings.context.max_tokens == 3072
    assert runtime.settings.context.compaction_threshold == 0.5
    assert orch.pool.context_config.max_tokens == 1536
    for index, agent in enumerate(agents):
        assert agent.max_tokens == 1536
        assert agent.messages is histories[index]
        assert agent.messages[-1].content == "Keep this conversation"
        assert agent.tool_registry is registries[index]
    assert agents[2].provider is pinned_provider
    assert agents[2].model == "pinned"
    assert agents[3].model == "specialized"
    assert replacement.request_defaults["max_tokens"] == 512
    assert orch.pool.get_agent("engineer").max_tokens == 1536

    switch_runtime_provider(runtime, OllamaProvider(model="later"))

    assert runtime.settings.context.max_tokens == 3072
    assert all(agent.max_tokens == 1536 for agent in agents)
    assert orch.pool.get_agent("engineer").max_tokens == 1536
    assert agents[2].provider is pinned_provider


@pytest.mark.parametrize("invalid", [True, False, 0, -1, 1.5, "4096"])
def test_invalid_context_length_rejected_before_any_runtime_mutation(invalid: Any) -> None:
    runtime = _runtime()
    old_provider = runtime.provider
    child = runtime.orchestrator.pool.get_agent("explorer")
    with pytest.raises(ValueError, match="positive integer"):
        switch_runtime_provider(runtime, OllamaProvider(model="new"), context_length=invalid)
    assert runtime.provider is old_provider
    assert runtime.agent.provider is old_provider
    assert runtime.orchestrator.pool.default_provider is old_provider
    assert child.provider is old_provider
    assert runtime.settings.context.max_tokens == 4096
    assert runtime.agent.max_tokens == child.max_tokens == 2048


def test_override_provider_preparation_failure_preserves_context_and_references(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("HENCHMAN_API_KEY", raising=False)
    runtime = _runtime()
    old_provider = runtime.provider
    child = runtime.orchestrator.pool.get_agent("model_only")
    old_child_provider = child.provider
    with pytest.raises(ValueError, match="API key"):
        switch_runtime_provider(
            runtime,
            OpenRouterProvider(api_key=""),
            context_length=1024,
        )
    assert runtime.provider is old_provider
    assert runtime.agent.provider is old_provider
    assert runtime.orchestrator.pool.default_provider is old_provider
    assert child.provider is old_child_provider
    assert runtime.settings.context.max_tokens == 4096
    assert runtime.agent.max_tokens == child.max_tokens == 2048
    assert runtime.orchestrator.pool.context_config.max_tokens == 2048


@pytest.mark.parametrize("settings_source", ["runtime", "orchestrator", "default"])
def test_context_threshold_resolution_and_inactive_lead(settings_source: str) -> None:
    runtime = _runtime()
    lead = runtime.orchestrator.tech_lead
    runtime.agent = Agent(runtime.provider)
    if settings_source != "runtime":
        del runtime.settings
    if settings_source == "default":
        del runtime.orchestrator.settings
    expected = 750 if settings_source == "default" else 500
    switch_runtime_provider(runtime, OllamaProvider(model="new"), context_length=1000)
    assert runtime.agent.max_tokens == lead.max_tokens == expected
    assert runtime.orchestrator.pool.get_agent("engineer").max_tokens == expected


def test_distinct_runtime_and_orchestrator_settings_are_both_updated() -> None:
    runtime = _runtime()
    runtime.settings = Settings(context={"max_tokens": 9999, "compaction_threshold": 0.25})
    switch_runtime_provider(runtime, OllamaProvider(model="new"), context_length=1000)
    assert runtime.settings.context.max_tokens == 1000
    assert runtime.orchestrator.settings.context.max_tokens == 1000
    assert runtime.agent.max_tokens == 250


@pytest.mark.parametrize("invalid", [True, 0, -1, 2.5, "1234"])
def test_direct_context_setters_reject_invalid_values(invalid: Any) -> None:
    runtime = _runtime()
    child = runtime.orchestrator.pool.get_agent("explorer")
    with pytest.raises(ValueError, match="positive integer"):
        runtime.agent.set_context_limit(invalid)
    with pytest.raises(ValueError, match="positive integer"):
        runtime.orchestrator.pool.set_context_limit(invalid)
    assert runtime.agent.max_tokens == child.max_tokens == 2048
    assert runtime.orchestrator.pool.context_config.max_tokens == 2048
