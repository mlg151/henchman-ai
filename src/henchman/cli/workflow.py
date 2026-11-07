"""Shared frontend dispatch ownership and cancellation settlement."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any, Literal, TypeVar

from henchman.core.runtime_workflow import use_workflow_input
from henchman.core.session_workflow import SessionWorkflow, WorkflowDispatch
from henchman.core.workflow_state import WorkflowError

_T = TypeVar("_T")
CommandRoute = Literal["queued", "control", "idle"]


def command_route(text: str) -> CommandRoute | None:
    """Route user commands without granting their own underlying permissions.

    Recovery and inspection must remain reachable while input dispatch is held.
    History/config mutations stay serialized; idle-only commands never acquire
    a workflow claim that would invalidate their existing execution guards.
    """
    parts = text.strip().split()
    if not parts or not parts[0].startswith("/"):
        return None
    name = parts[0].lower()
    action = parts[1].lower() if len(parts) > 1 else ""
    if name in {"/chat", "/session"}:
        return "idle"
    if name == "/mcp":
        if action == "attach":
            return "idle"
        if action in {"", "list", "status", "resources", "templates", "read", "prompts", "prompt"}:
            return "control"
        if action == "logging" and (len(parts) == 2 or parts[2].lower() == "status"):
            return "control"
        return "queued"
    if name == "/checkpoint":
        return "idle" if action in {"apply", "recover", "discard", "prune"} else "control"
    if name == "/recovery":
        return "idle" if action in {"retry", "complete", "abandon"} else "control"
    if name == "/model":
        return "control" if action in {"", "list"} else "queued"
    if name == "/context":
        if action in {"", "stats"} or (action == "strategy" and (len(parts) < 3 or parts[2].lower() != "set")):
            return "control"
        return "queued"
    if name == "/team":
        return "queued" if action == "reset" else "control"
    if name in {"/clear", "/plan", "/unlimited"}:
        return "queued"
    return "control"


def command_starts_work(text: str) -> bool:
    """Only explicit queue send or goal start/resume can wake autonomous work."""
    parts = text.strip().lower().split()
    if len(parts) < 2:
        return False
    if parts[0] == "/queue":
        return parts[1] == "send"
    return parts[0] == "/goal" and parts[1] not in {"status", "pause", "complete", "clear", "bind-plan", "unbind-plan"}


def idle_control_active(frontend: Any) -> bool:
    task = getattr(frontend, "_idle_control_task", None)
    return isinstance(task, asyncio.Task) and not task.done()


def frontend_has_active_work(frontend: Any) -> bool:
    """Inspect local execution ownership without creating/recovering authority."""
    from henchman.advanced.tasks import TaskService

    owner = asyncio.current_task()
    tasks = [getattr(frontend, name, None) for name in ("_turn_worker", "current_agent_task", "_idle_control_task")]
    if any(isinstance(task, asyncio.Task) and task is not owner and not task.done() for task in tasks):
        return True
    if getattr(frontend, "is_processing", False) and owner not in tasks:
        return True
    context = getattr(frontend, "core_context", None)
    sessions = getattr(context, "session_manager", None) or getattr(frontend, "session_manager", None)
    session = getattr(sessions, "current", None)
    workflow = getattr(session, "workflow_runtime", None)
    if isinstance(workflow, SessionWorkflow) and workflow.has_active_dispatch():
        return True
    orchestrator = getattr(context, "orchestrator", None) or getattr(frontend, "orchestrator", None)
    if getattr(orchestrator, "_public_run_active", False):
        return True
    operations = getattr(orchestrator, "operation_runtime", None)
    subagents = getattr(orchestrator, "subagents", None)
    prompt = getattr(getattr(frontend, "_tool_prompts", None), "_answer", None)
    return (bool(getattr(operations, "_inflight", None))
            or (subagents is not None and subagents.has_running_work())
            or (isinstance(prompt, asyncio.Future) and not prompt.done())
            or TaskService.has_active_work(Path.cwd()))


@contextmanager
def idle_command(frontend: Any) -> Iterator[None]:
    """Reserve a frontend's idle command interval without granting queue work."""
    if frontend_has_active_work(frontend):
        raise WorkflowError("command_requires_idle_work")
    previous = getattr(frontend, "_idle_control_task", None)
    frontend._idle_control_task = asyncio.current_task()
    try:
        yield
    finally:
        frontend._idle_control_task = previous


async def execute_workflow_input(runtime: SessionWorkflow, dispatch: WorkflowDispatch,
                                 execute: Callable[[], Awaitable[_T]]) -> _T:
    """Join actual work before cancellation releases the frontend's permit."""
    async def work() -> _T:
        with use_workflow_input(runtime, dispatch):
            return await execute()

    task = asyncio.create_task(work())
    try:
        result = await task
    except asyncio.CancelledError as primary:
        runtime.hold_pending()
        if not task.done():
            task.cancel()
        with suppress(BaseException):
            await task
        try:
            runtime.interrupt()
        except BaseException as cleanup:
            primary.add_note(f"Workflow interruption settlement failed: {type(cleanup).__name__}")
            raise cleanup from primary
        raise
    except BaseException as primary:
        try:
            runtime.finish(dispatch, outcome="failure")
        except BaseException as cleanup:
            raise cleanup from primary
        raise
    runtime.finish(dispatch, outcome="failure" if result is False else "success")
    return result
