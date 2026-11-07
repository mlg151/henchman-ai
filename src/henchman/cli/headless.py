"""Render team execution as one authoritative headless run."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from henchman.agents.orchestrator import Orchestrator
from henchman.agents.orchestrator_execution import _close_stream
from henchman.core.events import AgentEvent, EventType
from henchman.core.run_accounting import RunInvocation, budget_snapshot_payload
from henchman.core.run_budget import BudgetControlError
from henchman.core.usage_summary import budget_evidence_redactor
from henchman.providers.runtime_budget import RunBudgetScope
from henchman.utils.evidence_redaction import EvidenceRedactor


@dataclass
class _RenderedRun:
    completion: dict[str, Any] | None = None
    renderer_failed: bool = False


async def _forward_events(
    stream: AsyncIterator[AgentEvent],
    role: str,
    render_event: Callable[[AgentEvent], None],
    outcome: _RenderedRun,
) -> None:
    """Forward nested activity while retaining only marked root completion."""
    primary_error: BaseException | None = None
    try:
        async for event in stream:
            if event.type == EventType.FINISHED:
                continue
            if (
                event.type == EventType.AGENT_COMPLETED
                and event.source_agent == "orchestrator"
                and isinstance(event.data, dict)
                and event.data.get("agent") == role
                and event.data.get("scope") == "run"
            ):
                outcome.completion = event.data
            try:
                render_event(event)
            except BaseException:
                outcome.renderer_failed = True
                raise
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        await _close_stream(stream, primary_error=primary_error)


def _finish_run(
    role: str,
    completion: dict[str, Any] | None,
    render_event: Callable[[AgentEvent], None],
    error: str | None = None,
    budget: dict[str, Any] | None = None,
) -> bool:
    """Publish one terminal event without claiming whole-task verification."""
    metadata = dict(completion or {})
    if budget is not None:
        metadata["budget"] = budget
    status = metadata.get("status")
    successful = error is None and status in ("completed", "responded")
    if not successful:
        message = error or (
            "Orchestrator ended without a root completion event"
            if completion is None
            else f"Orchestrator did not complete successfully: {status!r}"
        )
        render_event(AgentEvent(EventType.ERROR, message, source_agent="orchestrator"))
    metadata.update({
        "agent": role,
        "scope": "run",
        "status": "failed" if error else status,
        "finish_reason": "stop" if successful else "error",
        "task_verified": False,
    })
    render_event(AgentEvent(EventType.FINISHED, metadata, source_agent="orchestrator"))
    return successful


def _budget_evidence(scope: RunBudgetScope | None, redactor: EvidenceRedactor) -> dict[str, Any] | None:
    """Keep accounting evidence on failed runs without inventing missing totals."""
    if not isinstance(scope, RunBudgetScope):
        return None
    try:
        return budget_snapshot_payload(scope.ledger.snapshot(), redactor=redactor)
    except BudgetControlError as exc:
        return {"run_id": scope.ledger.run_id, "accounting_error": str(exc)}


async def run_orchestrator_json(
    orchestrator: Orchestrator,
    prompt: str,
    render_event: Callable[[AgentEvent], None],
    agent_role: str | None = None,
) -> bool:
    """Reuse the configured team runtime and close it on every exit path."""
    role = agent_role or "tech_lead"
    outcome = _RenderedRun()
    policy = budget_evidence_redactor(orchestrator)
    invocation = RunInvocation()
    try:
        stream = (
            orchestrator.run_direct(agent_role, prompt, invocation=invocation)
            if agent_role
            else orchestrator.run(prompt, invocation=invocation)
        )
        await _forward_events(stream, role, render_event, outcome)
    except Exception as exc:
        if outcome.renderer_failed:
            raise
        # Control failures can skip normal finalization after registering a new
        # credential in the session. Refresh before emitting partial evidence.
        policy.register_policy(budget_evidence_redactor(orchestrator))
        return _finish_run(
            role, outcome.completion, render_event, f"{type(exc).__name__}: {exc}",
            budget=_budget_evidence(invocation.budget_scope, policy),
        )
    finally:
        if invocation.claimed:
            # Embedded successful runtimes need not call finalize_run. Capture
            # their current session policy before cleanup can replace bindings.
            policy.register_policy(budget_evidence_redactor(orchestrator))
            await orchestrator.aclose()
    return _finish_run(role, outcome.completion, render_event, budget=_budget_evidence(invocation.budget_scope, policy))
