"""Synchronize provider references without rebuilding an interactive runtime."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from henchman.cli.session_manager import ReplSessionManager
from henchman.config.runtime import RuntimeSettingsState, runtime_settings_state
from henchman.config.settings import SettingOrigin

if TYPE_CHECKING:
    from henchman.core.agent import Agent
    from henchman.providers.base import ModelProvider


def capture_startup_provider_settings(
    state: RuntimeSettingsState, provider: ModelProvider, *, injected: bool = False,
) -> None:
    """Include constructor defaults or explicit injected selection in inspection."""
    name = getattr(provider, "_accounting_provider_name", None)
    if not isinstance(name, str):
        name = provider.name
    if not isinstance(name, str):
        return
    if not injected and name != state.settings.providers.default:
        # A fallback (for example the TUI null provider) is not a user override.
        return
    actual_model = getattr(provider, "default_model", None)
    selection: dict[str, Any] = {}
    origin = SettingOrigin("session" if injected else "default")
    if injected:
        selection["default"] = name
    configured = getattr(state.settings.providers, name, None)
    if (
        isinstance(configured, dict) and isinstance(actual_model, str)
        and (injected or configured.get("model") != actual_model)
    ):
        selection[name] = {"model": actual_model}
        if not injected and configured.get("default_model") == actual_model:
            origin = state.snapshot().origins.get(f"providers.{name}.default_model", origin)
    if selection:
        state.update({"providers": selection}, origin=origin)


def switch_runtime_provider(
    runtime: Any,
    provider: ModelProvider,
    *,
    agent: Agent | None = None,
    context_length: int | None = None,
    provider_name: str | None = None,
    model_name: str | None = None,
) -> None:
    """Install a constructed provider while retaining sessions, tools, and history."""
    if context_length is not None:
        from henchman.core.agent import validate_context_limit

        validate_context_limit(context_length)
    orchestrator = getattr(runtime, "orchestrator", None)
    pool = getattr(orchestrator, "pool", None)
    active_agent = agent if agent is not None else getattr(runtime, "agent", None)
    state = runtime_settings_state(runtime)
    name = provider_name or getattr(provider, "_accounting_provider_name", None) or provider.name
    overrides: dict[str, Any] = {"providers": {"default": name}}
    actual_model = getattr(provider, "default_model", None)
    configured = getattr(state.settings.providers, name, None)
    # Custom registered providers may not declare a typed options group. Their
    # configured identity remains inspectable without inventing schema keys.
    if (
        isinstance(configured, dict) and isinstance(actual_model, str)
        and (model_name is not None or configured.get("model") != actual_model)
    ):
        overrides["providers"][name] = {"model": actual_model}
    if context_length is not None:
        overrides["context"] = {"max_tokens": context_length}
    prepared = state.prepare(overrides)
    context_settings = []
    budget = None
    if context_length is not None:
        from henchman.agents.pool import effective_context_budget
        from henchman.config.schema import ContextSettings
        for owner in (runtime, orchestrator):
            settings = getattr(owner, "settings", None)
            context = getattr(settings, "context", None)
            if context is not None:
                context_settings.append(context)
        context = context_settings[0] if context_settings else ContextSettings()
        budget = effective_context_budget(context_length, context.compaction_threshold)
    if active_agent is not None:
        from henchman.providers.continuation import validate_runtime_continuations

        validate_runtime_continuations(active_agent.messages, provider)
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
    session_manager = getattr(runtime, "session_manager", None)
    if isinstance(session_manager, ReplSessionManager):
        session_manager.register_credentials(provider=provider)
    runtime.provider = provider
    for name in ("output_handler", "command_processor", "tool_executor", "core_context"):
        component = getattr(runtime, name, None)
        if component is not None:
            component.provider = provider
    state.commit(prepared)
