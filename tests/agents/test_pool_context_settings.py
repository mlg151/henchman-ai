"""Team context budgets survive provider switches without losing role overrides."""

from types import SimpleNamespace

import pytest

from henchman.agents.config import AgentConfig
from henchman.agents.orchestrator import Orchestrator
from henchman.agents.pool import AgentPool, ContextConfig
from henchman.cli.provider_switch import switch_runtime_provider
from henchman.config.schema import Settings
from henchman.core.eventbus import EventBus
from henchman.providers import OllamaProvider, OpenRouterProvider
from henchman.providers.base import Message
from henchman.tools.registry import ToolRegistry
from henchman.utils.tokens import get_model_limit


def _pool(max_tokens: int | None) -> AgentPool:
    configs = {
        role: AgentConfig(name=role, role=role, description="Test", **overrides)
        for role, overrides in {
            "inherited": {},
            "pinned": {"provider": "ollama", "model": "gpt-4"},
            "model_only": {"model": "gpt-4"},
            "future": {},
        }.items()
    }
    return AgentPool(
        configs,
        OllamaProvider(model="gpt-4"),
        None,
        ToolRegistry(),
        EventBus(),
        context_config=ContextConfig(max_tokens=max_tokens),
    )


@pytest.mark.parametrize("max_tokens", [3072, None])
def test_cached_and_new_agents_keep_context_policy_when_provider_changes(
    max_tokens: int | None,
) -> None:
    pool = _pool(max_tokens)
    inherited = pool.get_agent("inherited")
    pinned = pool.get_agent("pinned")
    model_only = pool.get_agent("model_only")
    pinned_provider = pinned.provider
    original_budget = max_tokens or int(get_model_limit("gpt-4") * 0.85)
    assert inherited.max_tokens == original_budget
    assert pinned.max_tokens == original_budget
    assert model_only.max_tokens == original_budget
    inherited.messages.append(Message(role="user", content="Remember this"))
    messages = inherited.messages

    replacement = OpenRouterProvider(api_key="test-key", model="gpt-4-turbo")
    pool.set_default_provider(replacement)
    switched_budget = max_tokens or int(get_model_limit("gpt-4-turbo") * 0.85)
    assert pool.get_agent("inherited") is inherited
    assert inherited.provider is replacement
    assert inherited.max_tokens == switched_budget
    assert inherited.messages is messages
    assert inherited.messages[-1].content == "Remember this"
    assert pinned.provider is pinned_provider
    assert pinned.max_tokens == original_budget
    assert model_only.provider.name == "openrouter"
    assert model_only.model == "gpt-4"
    assert model_only.max_tokens == original_budget
    future = pool.get_agent("future")
    assert future.provider is replacement
    assert future.max_tokens == switched_budget


@pytest.mark.parametrize("threshold,expected", [(0.5, 1536), (0.0, 1), (1.0, 3072)])
def test_orchestrator_applies_threshold_to_lead_and_specialists_across_switch(
    threshold: float,
    expected: int,
) -> None:
    settings = Settings(
        context={
            "max_tokens": 3072,
            "compaction_threshold": threshold,
        }
    )
    provider = OllamaProvider(model="gpt-4")
    orchestrator = Orchestrator(default_provider=provider, settings=settings)
    cached = orchestrator.pool.get_agent("explorer")
    lead = orchestrator.tech_lead
    assert cached.max_tokens == expected
    assert lead.max_tokens == expected
    lead.messages.append(Message(role="user", content="Remember the lead history"))
    lead_history = lead.messages
    runtime = SimpleNamespace(orchestrator=orchestrator, agent=lead, provider=provider)

    replacement = OpenRouterProvider(api_key="test-key", model="gpt-4-turbo")
    switch_runtime_provider(runtime, replacement)

    assert orchestrator.pool.get_agent("explorer") is cached
    assert cached.provider is replacement
    assert cached.max_tokens == expected
    assert lead.provider is replacement
    assert lead.max_tokens == expected
    assert lead.messages is lead_history
    assert lead.messages[-1].content == "Remember the lead history"
    future = orchestrator.pool.get_agent("engineer")
    assert future.provider is replacement
    assert future.max_tokens == expected
