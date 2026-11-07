"""Structured completion of the current user-authorized goal."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from henchman.advanced.tasks import TaskService
from henchman.core.goals import GoalService, save_goal_session
from henchman.core.session_data import Session
from henchman.core.workflow_state import WorkflowError
from henchman.tools.base import Tool, ToolResult


class GoalStatusTool(Tool):
    """Read a bound session goal or complete its current revision."""

    def __init__(self) -> None:
        """Start unbound so standalone tools cannot change another session."""
        self._session_manager: object | None = None
        self._project_root: Path | None = None

    def bind_runtime(
        self, *, session_manager: object | None = None,
        project_root: Path | None = None, **_: object,
    ) -> None:
        """Bind the runtime manager that owns the current session."""
        self._session_manager = session_manager
        self._project_root = project_root

    @property
    def name(self) -> str:
        """Return the model-facing tool name."""
        return "goal_status"

    @property
    def description(self) -> str:
        """Explain the completion contract."""
        return (
            "Read the current goal or mark it complete only when all required work is "
            "finished and verified. Supply the current goal_id, goal_revision and verification summary. "
            "Only the user can start, pause, resume, or replace a goal."
        )

    @property
    def parameters(self) -> dict[str, object]:
        """Expose explicit status and completion actions."""
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["status", "complete"]},
                "goal_id": {"type": "string"},
                "goal_revision": {"type": "integer", "minimum": 1},
                "summary": {"type": "string"},
            },
            "required": ["action"],
        }

    async def execute(self, **params: object) -> ToolResult:
        """Read or complete the bound session goal without parsing model prose."""
        session = getattr(self._session_manager, "current", None)
        if not isinstance(session, Session):
            return ToolResult(content="No session goal runtime is bound", success=False,
                              error="Goal runtime unavailable")
        service = GoalService()
        try:
            action = params.get("action", "status")
            if action == "complete":
                goal_id = params.get("goal_id")
                summary = params.get("summary")
                if not isinstance(goal_id, str) or not isinstance(summary, str):
                    raise ValueError("Completion requires goal_id and summary strings")
                unresolved = [task for task in TaskService(project_root=self._project_root).list_tasks()
                              if task.status in {"queued", "started", "running", "outcome_unknown"}
                              or task.metadata.get("status_persisted") == "false"]
                if unresolved:
                    ids = ", ".join(task.task_id for task in unresolved)
                    raise ValueError(f"Project background tasks remain unresolved: {ids}")
                revision = params.get("goal_revision")
                service.complete(session, goal_id=goal_id, summary=summary,
                                 goal_revision=revision if type(revision) is int else None)
                save_goal_session(self._session_manager, session)
            elif action != "status":
                raise ValueError("action must be status or complete; lifecycle changes require /goal")
            goal = service.get(session)
            return ToolResult(content=json.dumps(asdict(goal) if goal else {"status": "unset"}))
        except ValueError as exc:
            return ToolResult(content=str(exc), success=False, error=str(exc))
        except WorkflowError as exc:
            if exc.reason not in {"goal_revision_required", "goal_revision_conflict", "goal_not_active", "goal_checks_unverified"}:
                raise
            return ToolResult(content=str(exc), success=False, error=str(exc))
