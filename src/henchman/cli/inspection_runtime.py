"""Framework-free binding, policy and joined-read helpers for inspection."""
from __future__ import annotations

import asyncio
from typing import Any, TypeVar

from henchman.cli.evidence import runtime_evidence_redactor
from henchman.core.session_data import Session
from henchman.providers.continuation import ProviderContinuationError, effective_continuation_model
from henchman.utils.evidence_redaction import EvidenceRedactor

_T = TypeVar("_T")


def _context(runtime: Any) -> Any:
    """Use a held Textual context or the classic frontend itself."""
    return getattr(runtime, "core_context", runtime)


def _agent(runtime: Any) -> Any:
    """Inspect an already constructed role; never instantiate an agent/provider."""
    context = _context(runtime)
    role = getattr(getattr(runtime, "config", None), "agent_role", None)
    if isinstance(role, str) and role:
        pool = getattr(getattr(context, "orchestrator", None), "pool", None)
        agents = getattr(pool, "_agents", None)
        return agents.get(role) if isinstance(agents, dict) else None
    return getattr(context, "agent", None)


def _provider_name(provider: Any) -> Any:
    return getattr(provider, "_accounting_provider_name", None) or getattr(provider, "name", None)


def _model(provider: Any) -> str | None:
    """Read the adapter's model precedence without preparing a request."""
    try:
        return effective_continuation_model(provider)
    except ProviderContinuationError:
        # Legacy injected providers may expose only `model`. Malformed declared
        # request defaults must remain unavailable instead of suggesting a fallback.
        if getattr(provider, "request_defaults", None) is None and getattr(provider, "default_model", None) is None:
            value = getattr(provider, "model", None)
            return value if isinstance(value, str) and value else None
        return None


def _current_policy(runtime: Any) -> EvidenceRedactor:
    """Refresh selected credentials without constructing agents or authority."""
    policy = runtime_evidence_redactor(runtime)
    context = _context(runtime)
    session = getattr(getattr(context, "session_manager", None), "current", None)
    if isinstance(session, Session):
        policy.register_policy(session.evidence_redactor)
    credential = getattr(getattr(_agent(runtime), "provider", None), "api_key", None)
    if isinstance(credential, str):
        policy.register_secret(credential)
    return policy


def _binding(runtime: Any) -> tuple[Any, ...]:
    context = _context(runtime)
    manager = getattr(context, "session_manager", None)
    session = getattr(manager, "current", None)
    orchestrator = getattr(context, "orchestrator", None)
    agent = _agent(runtime)
    provider = getattr(agent, "provider", None)
    return (
        id(context), id(manager), id(session), getattr(session, "id", None),
        getattr(session, "project_hash", None), getattr(context, "project_root", None),
        id(orchestrator), id(getattr(orchestrator, "accounting_runtime", None)),
        id(agent), id(provider), _provider_name(provider), _model(provider),
        getattr(agent, "context_window", None), getattr(agent, "max_tokens", None),
    )


async def _joined(task: asyncio.Task[_T]) -> _T:
    """Keep a read/close owner joined even when its caller is cancelled again."""
    cancelled = None
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError as error:
            cancelled = cancelled or error
        except BaseException:
            if not task.done():
                raise
    try:
        result = task.result()
    except BaseException:
        if cancelled is not None:
            cancelled.add_note("Context inspection also failed while closing")
            raise cancelled from None
        raise
    if cancelled is not None:
        raise cancelled
    return result
