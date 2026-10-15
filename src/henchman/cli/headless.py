"""Render team execution as one authoritative headless run."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from henchman.agents.orchestrator import Orchestrator
from henchman.agents.orchestrator_execution import _close_stream
from henchman.core.events import AgentEvent, EventType


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
) -> bool:
    """Publish one terminal event without claiming whole-task verification."""
    metadata = dict(completion or {})
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


async def run_orchestrator_json(
    orchestrator: Orchestrator,
    prompt: str,
    render_event: Callable[[AgentEvent], None],
    agent_role: str | None = None,
) -> bool:
    """Reuse the configured team runtime and close it on every exit path."""
    role = agent_role or "tech_lead"
    outcome = _RenderedRun()
    try:
        stream = (
            orchestrator.run_direct(agent_role, prompt)
            if agent_role
            else orchestrator.run(prompt)
        )
        await _forward_events(stream, role, render_event, outcome)
    except Exception as exc:
        if outcome.renderer_failed:
            raise
        return _finish_run(
            role, outcome.completion, render_event, f"{type(exc).__name__}: {exc}",
        )
    return _finish_run(role, outcome.completion, render_event)
