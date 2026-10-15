"""Requested capacity remains separate from effective compaction budgets."""

from types import SimpleNamespace
from typing import Any

import pytest

from henchman.agents.config import AgentConfig
from henchman.agents.orchestrator import Orchestrator
from henchman.agents.pool import AgentPool
from henchman.cli.provider_switch import switch_runtime_provider
from henchman.config.schema import Settings
from henchman.core.eventbus import EventBus
from henchman.providers import OllamaProvider, OpenRouterProvider
from henchman.providers.base import Message
from henchman.tools.registry import ToolRegistry


def _orchestrator() -> Orchestrator:
    settings = Settings(context={"max_tokens": 4096, "compaction_threshold": 0.5})
    orch = Orchestrator(default_provider=OllamaProvider(model="initial"), settings=settings)
    orch.pool.configs["pinned"] = AgentConfig(
        name="Pinned",
        role="pinned",
        description="Test",
        provider="ollama",
        model="pinned",
    )
    return orch


def test_initial_requested_capacity_reaches_lead_and_lazy_specialists() -> None:
    orch = _orchestrator()
    assert orch.pool.context_config.context_window == 4096
    for agent in (orch.tech_lead, orch.pool.get_agent("explorer"), orch.pool.get_agent("pinned")):
        assert agent._config.context_window == 4096
        assert agent.max_tokens == 2048


def test_switch_retains_raw_capacity_for_cached_future_and_pinned_agents() -> None:
    orch = _orchestrator()
    cached = orch.pool.get_agent("explorer")
    pinned = orch.pool.get_agent("pinned")
    pinned_provider = pinned.provider
    cached.messages.append(Message(role="user", content="Keep history"))
    history = cached.messages
    runtime = SimpleNamespace(orchestrator=orch, agent=orch.tech_lead, settings=orch.settings)
    switch_runtime_provider(
        runtime,
        OpenRouterProvider(api_key="test-key", model="replacement"),
        context_length=3072,
    )
    assert orch.pool.context_config.context_window == 3072
    future = orch.pool.get_agent("engineer")
    for agent in (orch.tech_lead, cached, pinned, future):
        assert agent._config.context_window == 3072
        assert agent.max_tokens == 1536
    assert pinned.provider is pinned_provider
    assert cached.messages is history
    assert cached.messages[-1].content == "Keep history"

    switch_runtime_provider(runtime, OllamaProvider(model="later"))
    for agent in (orch.tech_lead, cached, pinned, future):
        assert agent._config.context_window == 3072
        assert agent.max_tokens == 1536
    assert pinned.provider is pinned_provider


def test_pool_budget_only_change_preserves_existing_raw_capacity() -> None:
    orch = _orchestrator()
    cached = orch.pool.get_agent("explorer")
    orch.pool.set_context_limit(1000, context_window=3000)
    orch.pool.set_context_limit(900)
    assert orch.pool.context_config.context_window == 3000
    for agent in (cached, orch.pool.get_agent("engineer")):
        assert agent._config.context_window == 3000
        assert agent.max_tokens == 900


@pytest.mark.parametrize("invalid", [True, 0, -1, 2.5, "4096"])
def test_invalid_raw_capacity_cannot_partially_change_pool(invalid: Any) -> None:
    orch = _orchestrator()
    cached = orch.pool.get_agent("explorer")
    with pytest.raises(ValueError, match="positive integer"):
        orch.pool.set_context_limit(1000, context_window=invalid)
    assert orch.pool.context_config.max_tokens == 2048
    assert orch.pool.context_config.context_window == 4096
    assert cached.max_tokens == 2048
    assert cached._config.context_window == 4096


def test_invalid_budget_cannot_change_valid_raw_capacity() -> None:
    orch = _orchestrator()
    cached = orch.pool.get_agent("explorer")
    with pytest.raises(ValueError, match="positive integer"):
        orch.pool.set_context_limit(0, context_window=3000)
    assert orch.pool.context_config.context_window == 4096
    assert cached._config.context_window == 4096
    assert cached.max_tokens == 2048


def test_standalone_pool_keeps_unspecified_capacity_and_model_budget() -> None:
    pool = AgentPool(
        {"test": AgentConfig(name="Test", role="test", description="Test")},
        OllamaProvider(model="gpt-4"),
        None,
        ToolRegistry(),
        EventBus(),
    )
    agent = pool.get_agent("test")
    assert pool.context_config.context_window is None
    assert agent._config.context_window is None
    assert agent.max_tokens == int(8192 * 0.85)
    pool.set_default_provider(OllamaProvider(model="gpt-4-turbo"))
    assert agent._config.context_window is None
    assert agent.max_tokens == int(128000 * 0.85)
