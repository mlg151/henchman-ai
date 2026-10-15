"""Synchronize provider references without rebuilding an interactive runtime."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from henchman.core.agent import Agent
    from henchman.providers.base import ModelProvider


def switch_runtime_provider(
    runtime: Any,
    provider: ModelProvider,
    *,
    agent: Agent | None = None,
    context_length: int | None = None,
) -> None:
    """Install a constructed provider while retaining sessions, tools, and history."""
    orchestrator = getattr(runtime, "orchestrator", None)
    pool = getattr(orchestrator, "pool", None)
    active_agent = agent if agent is not None else getattr(runtime, "agent", None)
    context_settings = []
    budget = None
    if context_length is not None:
        from henchman.agents.pool import effective_context_budget
        from henchman.config.schema import ContextSettings
        from henchman.core.agent import validate_context_limit

        validate_context_limit(context_length)
        for owner in (runtime, orchestrator):
            settings = getattr(owner, "settings", None)
            context = getattr(settings, "context", None)
            if context is not None:
                context_settings.append(context)
        context = context_settings[0] if context_settings else ContextSettings()
        budget = effective_context_budget(context_length, context.compaction_threshold)
    if pool is not None:
        # Pool construction can fail; complete it before changing other references.
        pool.set_default_provider(provider)
    if active_agent is not None:
        active_agent.set_provider(provider)
    if budget is not None:
        if pool is not None:
            pool.set_context_limit(budget, context_window=context_length)
        if active_agent is not None:
            active_agent.set_context_limit(budget, context_window=context_length)
        lead = getattr(orchestrator, "tech_lead", None)
        if lead is not None and lead is not active_agent:
            lead.set_context_limit(budget, context_window=context_length)
        for context in context_settings:
            context.max_tokens = context_length
    if orchestrator is not None:
        orchestrator.default_provider = provider
    runtime.provider = provider
    for name in ("output_handler", "command_processor", "tool_executor", "core_context"):
        component = getattr(runtime, name, None)
        if component is not None:
            component.provider = provider
