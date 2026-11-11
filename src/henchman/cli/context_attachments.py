"""Coordinate explicit MCP attachments without starting or rebuilding a turn."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from typing import Any

from henchman.cli.commands import CommandContext
from henchman.cli.evidence import runtime_evidence_redactor
from henchman.cli.output_handler import resolve_active_agent
from henchman.cli.session_manager import ReplSessionManager
from henchman.core.agent import Agent
from henchman.core.goals import GoalService
from henchman.core.session import Session
from henchman.mcp.context import McpContextResult
from henchman.ops.operation_store import OperationStore
from henchman.providers.base import Message
from henchman.utils.context_attachments import attachment_payload, context_attachment_content


@dataclass(frozen=True)
class AttachmentTarget:
    runtime: Any
    sessions: ReplSessionManager
    session: Session
    agent: Agent

    def check_current(self) -> None:
        if self.sessions.current is not self.session or resolve_active_agent(self.runtime) is not self.agent:
            raise ValueError("Active session or agent changed; retrieve a new MCP preview")


def capture_attachment_target(ctx: CommandContext) -> AttachmentTarget | None:
    """Capture before retrieval; embedded preview-only consumers need no session."""
    runtime = ctx.repl
    context = getattr(runtime, "core_context", None)
    sessions = getattr(context, "session_manager", None) or getattr(runtime, "session_manager", None)
    if not isinstance(sessions, ReplSessionManager) or not isinstance(ctx.agent, Agent) or not isinstance(ctx.session, Session):
        return None
    target = AttachmentTarget(runtime, sessions, ctx.session, ctx.agent)
    target.check_current()
    return target


def require_attachment_idle(target: AttachmentTarget) -> None:
    """Allow the current command worker, but never alter an active agent turn."""
    target.check_current()
    runtime = target.runtime
    owner = asyncio.current_task()
    tasks = [getattr(runtime, name, None) for name in ("current_agent_task", "_turn_worker")]
    if any(isinstance(task, asyncio.Task) and task is not owner and not task.done() for task in tasks):
        raise ValueError("MCP attachment requires idle execution")
    if getattr(runtime, "is_processing", False) and owner not in tasks:
        raise ValueError("MCP attachment requires idle execution")
    prompt = getattr(getattr(runtime, "_tool_prompts", None), "_answer", None)
    if isinstance(prompt, asyncio.Future) and not prompt.done():
        raise ValueError("Finish the pending tool decision before attaching context")
    context = getattr(runtime, "core_context", None)
    orchestrator = getattr(context, "orchestrator", None) or getattr(runtime, "orchestrator", None)
    operations = getattr(orchestrator, "operation_runtime", None)
    if getattr(operations, "_inflight", None):
        raise ValueError("MCP attachment requires settled tool operations")
    if operations is not None:
        _require_settled_operations(target.session, operations)
    subagents = getattr(orchestrator, "subagents", None)
    if subagents is not None and subagents.has_running_work():
        raise ValueError("Finish delegated work before attaching context")
    pending: set[str] = set()
    for message in target.agent.messages:
        if message.role == "assistant":
            pending.update(call.id for call in message.tool_calls or [])
        elif message.role == "tool" and message.tool_call_id:
            pending.discard(message.tool_call_id)
    if pending:
        raise ValueError("Resolve the pending tool exchange before attaching context")
    workflow = getattr(target.session, "workflow_runtime", None)
    if workflow is not None:
        report = workflow.report()
        if workflow.has_active_dispatch() or report.blocking_input_ids or report.failure_reason:
            raise ValueError("Resolve workflow recovery before attaching context")
    goal = GoalService().get(target.session)
    if goal is not None and goal.status == "active":
        raise ValueError("Pause the active goal before attaching context without an automatic turn")


def _require_settled_operations(session: Session, operations: Any) -> None:
    """Inspect existing authority without opening a new journal or recovering it."""
    key = (session.project_hash, session.id)
    path = getattr(operations, "path", None)
    existing = OperationStore.existing_reference(path, *key) if path is not None else None
    reference = session.operations.reference if session.operations is not None else None
    cached = getattr(operations, "_active", {}).get(key)
    if reference != existing or (existing is not None and cached is None):
        raise ValueError("Resolve operation recovery before attaching context")
    if cached is None:
        return
    owner, journal = cached
    if owner is not session or getattr(journal, "reference", None) != existing:
        raise ValueError("Resolve operation recovery before attaching context")
    if any(record.state in {"started", "outcome_unknown"} and record.resolution is None
           for record in journal.report().records):
        raise ValueError("Resolve operation recovery before attaching context")


def attach_context_preview(ctx: CommandContext, identity: str) -> None:
    """Append only a bound captured result; no network, provider or restore path."""
    target = capture_attachment_target(ctx)
    if target is None or ctx.mcp_manager is None:
        raise ValueError("MCP attachment requires an explicitly current session and agent")
    require_attachment_idle(target)

    def append(result: McpContextResult) -> None:
        records = [attachment_payload(asdict(result), runtime_evidence_redactor(target.runtime))]
        message = Message("user", context_attachment_content(records), context_attachments=records)
        require_attachment_idle(target)
        target.sessions.append_context_attachment(target.agent, message, expected_session=target.session)

    ctx.mcp_manager.commit_context_preview(identity, target.session, target.agent, append)
