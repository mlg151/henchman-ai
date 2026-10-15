"""Tier 2 builtin tools for plan mode and git worktree isolation."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Any

from henchman.tools.base import Tool, ToolKind, ToolResult

_ENTER_WORKTREE_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "path": {"type": "string"},
        "branch": {"type": "string"},
        "repo_path": {"type": "string"},
    },
    "required": ["path"],
}

_EXIT_WORKTREE_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "path": {"type": "string"},
        "repo_path": {"type": "string"},
        "force": {"type": "boolean"},
    },
    "required": ["path"],
}


def _coerce_repo_root(project_root: Path | None, repo_path: object | None) -> Path:
    """Resolve a repository root for git worktree operations."""

    if isinstance(repo_path, str) and repo_path.strip():
        return Path(repo_path).expanduser().resolve()
    if project_root is not None:
        return project_root.expanduser().resolve()
    return Path.cwd().resolve()


def _run_git(argv: list[str]) -> subprocess.CompletedProcess[str]:
    """Execute one git command and capture its output."""

    return subprocess.run(argv, capture_output=True, text=True, check=False)


class _PlanModeToolBase(Tool):
    """Shared runtime binding for plan-mode toggle tools."""

    def __init__(self) -> None:
        """Initialize the unbound plan-mode runtime."""

        self._tool_registry: Any | None = None
        self._session_manager: Any | None = None
        self._agent: Any | None = None

    def bind_runtime(
        self,
        *,
        tool_registry: Any,
        session_manager: Any | None = None,
        project_root: Path | None = None,
        agent: Any | None = None,
        **kwargs: Any,
    ) -> None:
        """Bind the live runtime dependencies used by the tool."""

        del project_root
        self._tool_registry = tool_registry
        self._session_manager = session_manager
        self._agent = agent

    @property
    def kind(self) -> ToolKind:
        """Treat plan-mode toggles as safe local state changes."""

        return ToolKind.READ

    @property
    def parameters(self) -> dict[str, object]:
        """Plan-mode tools take no parameters."""

        return {"type": "object", "properties": {}}

    def _set_plan_mode(self, enabled: bool) -> ToolResult:
        """Apply one plan-mode transition to the bound runtime."""
        from henchman.cli.commands.plan import apply_plan_mode

        if self._tool_registry is None:
            return ToolResult(
                content="Plan mode runtime is unavailable in this build.",
                success=False,
                error="Plan mode runtime unavailable",
            )

        session = getattr(self._session_manager, "current", None) if self._session_manager else None
        apply_plan_mode(
            enabled=enabled,
            session=session,
            tool_registry=self._tool_registry,
            agent=self._agent,
        )

        backing_manager = getattr(self._session_manager, "session_manager", self._session_manager)
        save = getattr(backing_manager, "save", None)
        if callable(save) and session is not None:
            save(session)

        action = "enabled" if enabled else "disabled"
        return ToolResult(content=f"Plan mode {action}.")


class EnterPlanModeTool(_PlanModeToolBase):
    """Enable plan mode for the active interactive session."""

    @property
    def name(self) -> str:
        """Return the unique tool identifier."""

        return "enter_plan_mode"

    @property
    def description(self) -> str:
        """Return the tool description."""

        return "Enable read-only plan mode for the current session."

    async def execute(self, **params: object) -> ToolResult:
        """Enable plan mode."""

        del params
        return self._set_plan_mode(True)


class ExitPlanModeTool(_PlanModeToolBase):
    """Disable plan mode for the active interactive session."""

    @property
    def name(self) -> str:
        """Return the unique tool identifier."""

        return "exit_plan_mode"

    @property
    def description(self) -> str:
        """Return the tool description."""

        return "Disable read-only plan mode for the current session."

    async def execute(self, **params: object) -> ToolResult:
        """Disable plan mode."""

        del params
        return self._set_plan_mode(False)


class _WorktreeToolBase(Tool):
    """Shared git-worktree helpers."""

    def __init__(self, project_root: Path | None = None) -> None:
        """Initialize the tool with an optional repository root."""

        self._project_root = project_root

    def bind_runtime(
        self,
        *,
        tool_registry: Any,
        session_manager: Any | None = None,
        project_root: Path | None = None,
        agent: Any | None = None,
        **kwargs: Any,
    ) -> None:
        """Bind the current project root for interactive execution."""

        del tool_registry, session_manager, agent
        if project_root is not None:
            self._project_root = project_root

    @property
    def kind(self) -> ToolKind:
        """Git worktree operations execute git commands."""

        return ToolKind.EXECUTE

    async def _run(self, argv: list[str]) -> subprocess.CompletedProcess[str]:
        """Execute one git command asynchronously."""

        return await asyncio.to_thread(_run_git, argv)


class EnterWorktreeTool(_WorktreeToolBase):
    """Create a detached git worktree for isolated edits."""

    @property
    def name(self) -> str:
        """Return the unique tool identifier."""

        return "enter_worktree"

    @property
    def description(self) -> str:
        """Return the tool description."""

        return "Create an isolated git worktree and branch."

    @property
    def parameters(self) -> dict[str, object]:
        """Return the JSON Schema for enter-worktree parameters."""

        return _ENTER_WORKTREE_PARAMETERS

    async def execute(self, **params: object) -> ToolResult:
        """Create a new worktree rooted at the requested path."""

        raw_path = params.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            return ToolResult(
                content="A destination path is required.",
                success=False,
                error="Missing worktree path",
            )

        repo_root = _coerce_repo_root(self._project_root, params.get("repo_path"))
        worktree_path = Path(raw_path).expanduser().resolve()
        if worktree_path.exists():
            return ToolResult(
                content=f"Worktree path already exists: {worktree_path}",
                success=False,
                error="Worktree path already exists",
            )

        branch = params.get("branch")
        branch_name = str(branch).strip() if isinstance(branch, str) and branch.strip() else None
        if branch_name is None:
            branch_name = f"henchman/{worktree_path.name}"

        result = await self._run(
            [
                "git",
                "-C",
                str(repo_root),
                "worktree",
                "add",
                "-b",
                branch_name,
                str(worktree_path),
            ],
        )
        if result.returncode != 0:
            error_text = result.stderr.strip() or result.stdout.strip() or "git worktree add failed"
            return ToolResult(content=error_text, success=False, error=error_text)

        return ToolResult(
            content=f"Created worktree {worktree_path} on branch {branch_name}.",
        )


class ExitWorktreeTool(_WorktreeToolBase):
    """Remove a previously created git worktree."""

    @property
    def name(self) -> str:
        """Return the unique tool identifier."""

        return "exit_worktree"

    @property
    def description(self) -> str:
        """Return the tool description."""

        return "Remove an isolated git worktree."

    @property
    def parameters(self) -> dict[str, object]:
        """Return the JSON Schema for exit-worktree parameters."""

        return _EXIT_WORKTREE_PARAMETERS

    async def execute(self, **params: object) -> ToolResult:
        """Remove the requested git worktree."""

        raw_path = params.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            return ToolResult(
                content="A worktree path is required.",
                success=False,
                error="Missing worktree path",
            )

        repo_root = _coerce_repo_root(self._project_root, params.get("repo_path"))
        worktree_path = Path(raw_path).expanduser().resolve()
        argv = ["git", "-C", str(repo_root), "worktree", "remove"]
        if params.get("force") is True:
            argv.append("--force")
        argv.append(str(worktree_path))

        result = await self._run(argv)
        if result.returncode != 0:
            error_text = result.stderr.strip() or result.stdout.strip() or "git worktree remove failed"
            return ToolResult(content=error_text, success=False, error=error_text)

        return ToolResult(content=f"Removed worktree {worktree_path}.")


__all__ = [
    "EnterPlanModeTool",
    "EnterWorktreeTool",
    "ExitPlanModeTool",
    "ExitWorktreeTool",
]
