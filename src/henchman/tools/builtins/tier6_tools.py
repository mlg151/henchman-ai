"""Tier 6 builtin tools for advanced task, MCP, REPL, plan, LSP, and scheduling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from henchman.advanced import (
    CronScheduleService,
    ExperimentReplService,
    PlanExecutionService,
    TaskRecord,
    TaskService,
    TungstenService,
)
from henchman.lsp import LspService
from henchman.mcp.auth import McpAuthService
from henchman.tools.base import ConfirmationRequest, Tool, ToolKind, ToolResult

_TASK_CREATE_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "argv": {"type": "array", "items": {"type": "string"}},
        "title": {"type": "string"},
        "cwd": {"type": "string"},
        "metadata": {"type": "object"},
    },
    "required": ["argv"],
}

_TASK_ID_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {"task_id": {"type": "string"}},
    "required": ["task_id"],
}

_TASK_LIST_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {"status": {"type": "string"}},
}

_TASK_OUTPUT_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "task_id": {"type": "string"},
        "lines": {"type": "integer"},
    },
    "required": ["task_id"],
}

_TASK_UPDATE_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "task_id": {"type": "string"},
        "title": {"type": "string"},
        "metadata": {"type": "object"},
    },
    "required": ["task_id"],
}

_MCP_AUTH_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["set", "clear", "status"]},
        "server": {"type": "string"},
        "token": {"type": "string"},
    },
    "required": ["action"],
}

_MCP_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["status", "connect", "disconnect", "discover"]},
        "server": {"type": "string"},
    },
    "required": ["action"],
}

_REPL_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["start", "input", "history", "close", "list"]},
        "session_id": {"type": "string"},
        "name": {"type": "string"},
        "code": {"type": "string"},
    },
    "required": ["action"],
}

_CHECK_SCHEMAS: list[dict[str, object]] = [
    {
        "type": "object", "additionalProperties": False,
        "properties": {"kind": {"const": kind}, **properties},
        "required": ["kind", *required],
    }
    for kind, properties, required in (
        ("file_exists", {"path": {"type": "string"}}, ["path"]),
        ("file_contains", {"path": {"type": "string"},
                           "text": {"type": "string", "maxLength": 4096}}, ["path", "text"]),
        ("file_changed", {"path": {"type": "string"}}, ["path"]),
        ("command", {"argv": {"type": "array", "items": {"type": "string"},
                               "minItems": 1, "maxItems": 64},
                     "expected_exit": {"type": "integer", "default": 0},
                     "timeout": {"type": "integer", "minimum": 1, "maximum": 300}}, ["argv"]),
        ("pytest", {"path": {"type": "string"},
                    "timeout": {"type": "integer", "minimum": 1, "maximum": 300}}, ["path"]),
    )
]

_VERIFY_PLAN_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["create", "next", "complete", "verify", "status", "list"]},
        "plan_id": {"type": "string"},
        "title": {"type": "string"},
        "steps": {"type": "array", "items": {"type": "string"}},
        "plan": {"type": "string"},
        "step": {"type": "integer"},
        "evidence": {"type": "string"},
        "checks": {"type": "array", "minItems": 1, "maxItems": 20,
                   "items": {"oneOf": _CHECK_SCHEMAS}},
    },
    "required": ["action"],
}

_LSP_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["register", "list", "start", "stop", "request"]},
        "server": {"type": "string"},
        "command": {"type": "string"},
        "args": {"type": "array", "items": {"type": "string"}},
        "language": {"type": "string"},
        "root_uri": {"type": "string"},
        "method": {"type": "string"},
        "params": {"type": "object"},
    },
    "required": ["action"],
}

_SCHEDULE_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["create", "list", "pause", "resume", "delete"]},
        "schedule_id": {"type": "string"},
        "title": {"type": "string"},
        "cron": {"type": "string"},
        "argv": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["action"],
}

_TUNGSTEN_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["snapshot", "compare", "list"]},
        "name": {"type": "string"},
        "paths": {"type": "array", "items": {"type": "string"}},
        "left": {"type": "string"},
        "right": {"type": "string"},
    },
    "required": ["action"],
}


def _require_task_id(params: dict[str, object]) -> str:
    """Return a required task identifier from tool parameters."""

    task_id = params.get("task_id")
    if isinstance(task_id, str) and task_id.strip():
        return task_id.strip()
    msg = "A task_id is required."
    raise ValueError(msg)


def _render_task(record: TaskRecord) -> str:
    """Return a compact human-readable summary for one task."""

    return (
        f"{record.task_id} [{record.status}] {record.title} "
        f"(cwd={record.cwd}, rc={record.return_code})"
        + (f" Error: {record.metadata['error']}" if record.metadata.get("error") else "")
    )


class _Tier6TaskToolBase(Tool):
    """Shared runtime binding for Tier 6 task tools."""

    def __init__(self) -> None:
        """Initialize the task tool runtime."""

        self._project_root = Path.cwd()
        self._task_service = TaskService(project_root=self._project_root)

    def bind_runtime(
        self,
        *,
        tool_registry: Any,
        session_manager: Any | None = None,
        project_root: Path | None = None,
        agent: Any | None = None,
        **kwargs: Any,
    ) -> None:
        """Bind the current project root for task persistence."""

        del tool_registry, session_manager, agent
        if project_root is not None:
            self._project_root = project_root.resolve()
        self._task_service = TaskService(project_root=self._project_root)


class _Tier6McpToolBase(Tool):
    """Shared runtime binding for Tier 6 MCP tools."""

    def __init__(self) -> None:
        """Initialize the MCP management runtime."""

        self._project_root = Path.cwd()
        self._auth_service = McpAuthService(project_root=self._project_root)
        self._mcp_manager: Any | None = None

    def bind_runtime(
        self,
        *,
        project_root: Path | None = None,
        mcp_manager: object | None = None,
        **_: object,
    ) -> None:
        """Bind project-local auth storage and an active MCP manager."""

        if project_root is not None:
            self._project_root = project_root.resolve()
        self._auth_service = McpAuthService(project_root=self._project_root)
        if mcp_manager is not None:
            self._mcp_manager = mcp_manager


class _Tier6ReplToolBase(Tool):
    """Shared runtime binding for Tier 6 REPL tools."""

    def __init__(self) -> None:
        """Initialize the REPL service runtime."""

        self._project_root = Path.cwd()
        self._repl_service = ExperimentReplService(project_root=self._project_root)

    def bind_runtime(self, *, project_root: Path | None = None, **_: object) -> None:
        """Bind project-local REPL session storage."""

        if project_root is not None:
            self._project_root = project_root.resolve()
        self._repl_service = ExperimentReplService(project_root=self._project_root)


class _Tier6PlanToolBase(Tool):
    """Shared runtime binding for plan verification tools."""

    def __init__(self) -> None:
        """Initialize the plan execution service runtime."""

        self._project_root = Path.cwd()
        self._plan_service = PlanExecutionService(project_root=self._project_root)

    def bind_runtime(self, *, project_root: Path | None = None, **_: object) -> None:
        """Bind project-local plan verification storage."""

        if project_root is not None:
            self._project_root = project_root.resolve()
        self._plan_service = PlanExecutionService(project_root=self._project_root)


class _Tier6LspToolBase(Tool):
    """Shared runtime binding for Tier 6 LSP tools."""

    def __init__(self) -> None:
        """Initialize the LSP service runtime."""

        self._project_root = Path.cwd()
        self._lsp_service = LspService(project_root=self._project_root)

    def bind_runtime(self, *, project_root: Path | None = None, **_: object) -> None:
        """Bind project-local LSP storage."""

        if project_root is not None:
            self._project_root = project_root.resolve()
        self._lsp_service = LspService(project_root=self._project_root)


class _Tier6ScheduleToolBase(Tool):
    """Shared runtime binding for cron scheduling tools."""

    def __init__(self) -> None:
        """Initialize the cron scheduling runtime."""

        self._project_root = Path.cwd()
        self._schedule_service = CronScheduleService(project_root=self._project_root)

    def bind_runtime(self, *, project_root: Path | None = None, **_: object) -> None:
        """Bind project-local schedule storage."""

        if project_root is not None:
            self._project_root = project_root.resolve()
        self._schedule_service = CronScheduleService(project_root=self._project_root)


class _Tier6TungstenToolBase(Tool):
    """Shared runtime binding for Tungsten snapshot tooling."""

    def __init__(self) -> None:
        """Initialize the Tungsten service runtime."""

        self._project_root = Path.cwd()
        self._tungsten_service = TungstenService(project_root=self._project_root)

    def bind_runtime(self, *, project_root: Path | None = None, **_: object) -> None:
        """Bind project-local Tungsten storage."""

        if project_root is not None:
            self._project_root = project_root.resolve()
        self._tungsten_service = TungstenService(project_root=self._project_root)


class TaskCreateTool(_Tier6TaskToolBase):
    """Create and start a background task."""

    @property
    def name(self) -> str:
        """Return the unique tool identifier."""

        return "task_create"

    @property
    def description(self) -> str:
        """Return the tool description."""

        return "Start a background task with argv-based execution and captured output."

    @property
    def parameters(self) -> dict[str, object]:
        """Return the JSON Schema for task creation."""

        return _TASK_CREATE_PARAMETERS

    @property
    def kind(self) -> ToolKind:
        """Task creation runs a background process."""

        return ToolKind.EXECUTE

    async def execute(self, **params: object) -> ToolResult:
        """Start one background task."""

        raw_argv = params.get("argv")
        argv = [str(item) for item in raw_argv] if isinstance(raw_argv, list) else []
        raw_metadata = params.get("metadata")
        metadata: dict[str, object] | None = (
            {str(key): value for key, value in raw_metadata.items()}
            if isinstance(raw_metadata, dict)
            else None
        )
        record = await self._task_service.start_task(
            argv=argv,
            title=str(params["title"]) if isinstance(params.get("title"), str) else None,
            cwd=str(params["cwd"]) if isinstance(params.get("cwd"), str) else None,
            metadata=metadata,
        )
        return ToolResult(content=f"Created task {_render_task(record)}")


class TaskGetTool(_Tier6TaskToolBase):
    """Fetch metadata for one task."""

    @property
    def name(self) -> str:
        """Return the unique tool identifier."""

        return "task_get"

    @property
    def description(self) -> str:
        """Return the tool description."""

        return "Get one task record by ID."

    @property
    def parameters(self) -> dict[str, object]:
        """Return the JSON Schema for task lookup."""

        return _TASK_ID_PARAMETERS

    async def execute(self, **params: object) -> ToolResult:
        """Return one task summary."""

        record = self._task_service.get_task(_require_task_id(params))
        if record is None:
            return ToolResult(content="Task not found.", success=False, error="Task not found")
        return ToolResult(content=_render_task(record))


class TaskListTool(_Tier6TaskToolBase):
    """List known background tasks."""

    @property
    def name(self) -> str:
        """Return the unique tool identifier."""

        return "task_list"

    @property
    def description(self) -> str:
        """Return the tool description."""

        return "List background tasks for the current project."

    @property
    def parameters(self) -> dict[str, object]:
        """Return the JSON Schema for task listing."""

        return _TASK_LIST_PARAMETERS

    async def execute(self, **params: object) -> ToolResult:
        """Return a compact multi-line list of tasks."""

        status = str(params["status"]) if isinstance(params.get("status"), str) else None
        records = self._task_service.list_tasks(status=status)
        if not records:
            return ToolResult(content="No tasks found.")
        return ToolResult(content="\n".join(_render_task(record) for record in records))


class TaskOutputTool(_Tier6TaskToolBase):
    """Read task output captured to the project-local log."""

    @property
    def name(self) -> str:
        """Return the unique tool identifier."""

        return "task_output"

    @property
    def description(self) -> str:
        """Return the tool description."""

        return "Tail captured output for one background task."

    @property
    def parameters(self) -> dict[str, object]:
        """Return the JSON Schema for task output lookup."""

        return _TASK_OUTPUT_PARAMETERS

    async def execute(self, **params: object) -> ToolResult:
        """Return task output for the requested task."""

        task_id = _require_task_id(params)
        raw_lines = params.get("lines")
        lines = raw_lines if isinstance(raw_lines, int) else 25
        try:
            content = self._task_service.tail_output(task_id, lines=lines)
        except KeyError as exc:
            return ToolResult(content=str(exc), success=False, error=str(exc))
        return ToolResult(content=content or "(no output yet)")


class TaskStopTool(_Tier6TaskToolBase):
    """Stop one running background task."""

    @property
    def name(self) -> str:
        """Return the unique tool identifier."""

        return "task_stop"

    @property
    def description(self) -> str:
        """Return the tool description."""

        return "Stop a running background task."

    @property
    def parameters(self) -> dict[str, object]:
        """Return the JSON Schema for task stop requests."""

        return _TASK_ID_PARAMETERS

    @property
    def kind(self) -> ToolKind:
        """Stopping a task affects process execution."""

        return ToolKind.EXECUTE

    async def execute(self, **params: object) -> ToolResult:
        """Stop one task and return its final state."""

        try:
            record = await self._task_service.stop_task(_require_task_id(params))
        except KeyError as exc:
            return ToolResult(content=str(exc), success=False, error=str(exc))
        return ToolResult(content=f"Stopped task {_render_task(record)}")


class TaskUpdateTool(_Tier6TaskToolBase):
    """Update task metadata."""

    @property
    def name(self) -> str:
        """Return the unique tool identifier."""

        return "task_update"

    @property
    def description(self) -> str:
        """Return the tool description."""

        return "Update a task title or metadata."

    @property
    def parameters(self) -> dict[str, object]:
        """Return the JSON Schema for task updates."""

        return _TASK_UPDATE_PARAMETERS

    @property
    def kind(self) -> ToolKind:
        """Task updates mutate persisted project-local state."""

        return ToolKind.WRITE

    async def execute(self, **params: object) -> ToolResult:
        """Apply one task metadata update."""

        raw_metadata = params.get("metadata")
        metadata: dict[str, object] | None = (
            {str(key): value for key, value in raw_metadata.items()}
            if isinstance(raw_metadata, dict)
            else None
        )
        try:
            record = self._task_service.update_task(
                _require_task_id(params),
                title=str(params["title"]) if isinstance(params.get("title"), str) else None,
                metadata=metadata,
            )
        except KeyError as exc:
            return ToolResult(content=str(exc), success=False, error=str(exc))
        return ToolResult(content=f"Updated task {_render_task(record)}")


class McpAuthTool(_Tier6McpToolBase):
    """Persist or inspect project-local MCP auth state."""

    @property
    def name(self) -> str:
        """Return the unique tool identifier."""

        return "mcp_auth"

    @property
    def description(self) -> str:
        """Return the tool description."""

        return "Persist, clear, or inspect project-local MCP auth tokens."

    @property
    def parameters(self) -> dict[str, object]:
        """Return the JSON Schema for MCP auth actions."""

        return _MCP_AUTH_PARAMETERS

    @property
    def kind(self) -> ToolKind:
        """Auth persistence mutates project-local state."""

        return ToolKind.WRITE

    async def execute(self, **params: object) -> ToolResult:
        """Persist or inspect MCP auth tokens."""

        action = str(params.get("action", "")).strip()
        server = str(params["server"]).strip() if isinstance(params.get("server"), str) else ""

        if action == "set":
            token = str(params["token"]).strip() if isinstance(params.get("token"), str) else ""
            if not server or not token:
                return ToolResult(
                    content="Both server and token are required.",
                    success=False,
                    error="Missing server or token",
                )
            self._auth_service.set_token(server, token)
            set_auth = getattr(self._mcp_manager, "set_auth_token", None)
            if callable(set_auth):
                set_auth(server, token)
            return ToolResult(content=f"Stored MCP auth for {server}.")

        if action == "clear":
            if not server:
                return ToolResult(
                    content="A server is required to clear MCP auth.",
                    success=False,
                    error="Missing server",
                )
            removed = self._auth_service.clear_token(server)
            clear_auth = getattr(self._mcp_manager, "clear_auth_token", None)
            if callable(clear_auth):
                clear_auth(server)
            if not removed:
                return ToolResult(content=f"No stored MCP auth for {server}.")
            return ToolResult(content=f"Cleared MCP auth for {server}.")

        if action == "status":
            statuses = self._auth_service.list_statuses()
            if not statuses:
                return ToolResult(content="No MCP auth tokens stored.")
            return ToolResult(
                content="\n".join(f"{server}: auth=yes" for server in sorted(statuses)),
            )

        return ToolResult(
            content=f"Unsupported MCP auth action '{action}'.",
            success=False,
            error="Unsupported MCP auth action",
        )


class MCPTool(_Tier6McpToolBase):
    """Manage configured MCP server connections and discovery."""

    @property
    def name(self) -> str:
        """Return the unique tool identifier."""

        return "mcp"

    @property
    def description(self) -> str:
        """Return the tool description."""

        return "Inspect, connect, disconnect, and discover configured MCP servers."

    @property
    def parameters(self) -> dict[str, object]:
        """Return the JSON Schema for MCP management actions."""

        return _MCP_PARAMETERS

    @property
    def kind(self) -> ToolKind:
        """MCP management can perform network/process operations."""

        return ToolKind.NETWORK

    async def execute(self, **params: object) -> ToolResult:
        """Execute an MCP management action."""

        if self._mcp_manager is None:
            return ToolResult(
                content="No MCP manager is bound to the current runtime.",
                success=False,
                error="MCP manager unavailable",
            )

        action = str(params.get("action", "")).strip()
        server = str(params["server"]).strip() if isinstance(params.get("server"), str) else None

        if action == "status":
            raw_servers: object = getattr(self._mcp_manager, "list_servers", lambda: [])()
            servers: list[dict[str, object]] = raw_servers if isinstance(raw_servers, list) else []
            if not servers:
                return ToolResult(content="No MCP servers configured.")
            lines = []
            for entry in servers:
                name = str(entry.get("name", "unknown"))
                connected = "yes" if entry.get("connected") else "no"
                trusted = "yes" if entry.get("trusted") else "no"
                auth = "yes" if self._auth_service.has_token(name) else "no"
                lines.append(
                    f"{name}: connected={connected} trusted={trusted} auth={auth}",
                )
            return ToolResult(content="\n".join(lines))

        if action == "connect":
            if not server:
                return ToolResult(
                    content="A server is required to connect.",
                    success=False,
                    error="Missing server",
                )
            await self._mcp_manager.connect_server(server)
            return ToolResult(content=f"Connected MCP server {server}.")

        if action == "disconnect":
            if not server:
                return ToolResult(
                    content="A server is required to disconnect.",
                    success=False,
                    error="Missing server",
                )
            await self._mcp_manager.disconnect_server(server)
            return ToolResult(content=f"Disconnected MCP server {server}.")

        if action == "discover":
            raw_discovered: object = getattr(
                self._mcp_manager,
                "discover_tools",
                lambda _server=None: [],
            )(server)
            discovered: list[object] = raw_discovered if isinstance(raw_discovered, list) else []
            if not discovered:
                return ToolResult(content="No MCP tools discovered.")
            return ToolResult(
                content="\n".join(str(getattr(tool, "name", tool)) for tool in discovered),
            )

        return ToolResult(
            content=f"Unsupported MCP action '{action}'.",
            success=False,
            error="Unsupported MCP action",
        )


class REPLTool(_Tier6ReplToolBase):
    """Manage local experimentation REPL sessions."""

    @property
    def name(self) -> str:
        """Return the unique tool identifier."""

        return "repl"

    @property
    def description(self) -> str:
        """Return the tool description."""

        return "Start and interact with a local experimentation REPL session."

    @property
    def parameters(self) -> dict[str, object]:
        """Return the JSON Schema for REPL actions."""

        return _REPL_PARAMETERS

    @property
    def kind(self) -> ToolKind:
        """REPL input executes code in a sandboxed local session."""

        return ToolKind.EXECUTE

    async def execute(self, **params: object) -> ToolResult:
        """Execute one REPL management action."""

        action = str(params.get("action", "")).strip()
        session_id = str(params["session_id"]).strip() if isinstance(params.get("session_id"), str) else ""

        if action == "start":
            record = self._repl_service.start_session(
                name=str(params["name"]) if isinstance(params.get("name"), str) else None,
            )
            return ToolResult(content=f"Started REPL session {record.session_id}.")

        if action == "list":
            records = self._repl_service.list_sessions()
            if not records:
                return ToolResult(content="No REPL sessions found.")
            return ToolResult(
                content="\n".join(
                    f"{record.session_id} [{ 'closed' if record.closed_at else 'open' }] {record.name}"
                    for record in records
                ),
            )

        if action == "input":
            source = str(params["code"]).strip() if isinstance(params.get("code"), str) else ""
            if not session_id or not source:
                return ToolResult(
                    content="Both session_id and code are required.",
                    success=False,
                    error="Missing session_id or code",
                )
            try:
                _, output = self._repl_service.execute(session_id, source)
            except (KeyError, ValueError) as exc:
                return ToolResult(content=str(exc), success=False, error=str(exc))
            return ToolResult(content=output)

        if action == "history":
            if not session_id:
                return ToolResult(
                    content="A session_id is required for history.",
                    success=False,
                    error="Missing session_id",
                )
            try:
                return ToolResult(content=self._repl_service.render_history(session_id))
            except KeyError as exc:
                return ToolResult(content=str(exc), success=False, error=str(exc))

        if action == "close":
            if not session_id:
                return ToolResult(
                    content="A session_id is required to close a REPL session.",
                    success=False,
                    error="Missing session_id",
                )
            try:
                record = self._repl_service.close_session(session_id)
            except KeyError as exc:
                return ToolResult(content=str(exc), success=False, error=str(exc))
            return ToolResult(content=f"Closed REPL session {record.session_id}.")

        return ToolResult(
            content=f"Unsupported REPL action '{action}'.",
            success=False,
            error="Unsupported REPL action",
        )


class VerifyPlanExecutionTool(_Tier6PlanToolBase):
    """Create and verify ordered plan execution checklists."""

    @property
    def name(self) -> str:
        """Return the unique tool identifier."""

        return "verify_plan_execution"

    @property
    def description(self) -> str:
        """Return the tool description."""

        return ("Track reported plan steps and run immutable file, argv-command, or pytest checks. "
                "Create checks before work; verify runs them. Passing checks do not establish task correctness.")

    @property
    def parameters(self) -> dict[str, object]:
        """Return the JSON Schema for plan verification actions."""

        return _VERIFY_PLAN_PARAMETERS

    @property
    def kind(self) -> ToolKind:
        """Acceptance checks can execute project commands."""

        return ToolKind.EXECUTE

    def needs_confirmation(self, params: dict[str, object]) -> ConfirmationRequest | None:
        """Show stored assertions and commands in the normal execution prompt."""
        request = super().needs_confirmation(params)
        if request is not None and params.get("action") == "verify":
            try:
                record = self._plan_service.get_plan(str(params.get("plan_id", "")))
            except (ValueError, OSError) as exc:
                request.description = f"Cannot inspect recorded checks: {exc}"
            else:
                if record is not None:
                    request.description = "Run recorded acceptance checks in the project directory"
                    request.params = dict(params, checks=[check.to_dict() for check in record.checks])
        return request

    async def execute(self, **params: object) -> ToolResult:
        """Return explicit validation and persistence failures to the agent."""
        try:
            return await self._execute_action(**params)
        except (KeyError, ValueError, OSError) as exc:
            return ToolResult(content=str(exc), success=False, error=str(exc))

    async def _execute_action(self, **params: object) -> ToolResult:
        """Execute one plan verification action."""

        action = str(params.get("action", "")).strip()
        plan_id = str(params["plan_id"]).strip() if isinstance(params.get("plan_id"), str) else ""

        if action == "create":
            raw_steps = params.get("steps")
            if raw_steps is not None and (
                not isinstance(raw_steps, list) or any(not isinstance(step, str) for step in raw_steps)
            ):
                raise ValueError("Plan steps must be an array of strings.")
            steps = raw_steps if isinstance(raw_steps, list) else None
            try:
                record = self._plan_service.create_plan(
                    title=str(params["title"]) if isinstance(params.get("title"), str) else None,
                    steps=steps,
                    checks=params.get("checks"),
                    plan=str(params["plan"]) if isinstance(params.get("plan"), str) else None,
                )
            except ValueError as exc:
                return ToolResult(content=str(exc), success=False, error=str(exc))
            return ToolResult(content=f"Created plan verification {record.plan_id}.")

        if action == "verify":
            if not plan_id:
                raise ValueError("A plan_id is required to run acceptance checks.")
            report = await self._plan_service.verify_plan(plan_id)
            passed = report.get("checks_passed") is True
            return ToolResult(content=json.dumps(report, sort_keys=True), success=passed,
                              error=None if passed else "Acceptance checks did not pass")

        if action == "list":
            records = self._plan_service.list_plans()
            if not records:
                return ToolResult(content="No plan verifications found.")
            return ToolResult(
                content="\n".join(
                    f"{record.plan_id}: {record.title} ({len(record.steps)} steps)"
                    for record in records
                ),
            )

        if action == "next":
            if not plan_id:
                return ToolResult(
                    content="A plan_id is required to inspect the next step.",
                    success=False,
                    error="Missing plan_id",
                )
            try:
                step_record = self._plan_service.next_step(plan_id)
            except KeyError as exc:
                return ToolResult(content=str(exc), success=False, error=str(exc))
            if step_record is None:
                return ToolResult(content="All steps reported complete. Run acceptance checks to inspect results.")
            return ToolResult(content=f"Next step: {step_record.index}. {step_record.text}")

        if action == "complete":
            step_value = params.get("step")
            if not plan_id or (not isinstance(step_value, int) or isinstance(step_value, bool)):
                return ToolResult(
                    content="Both plan_id and step are required to complete a step.",
                    success=False,
                    error="Missing plan_id or step",
                )
            try:
                record = self._plan_service.complete_step(
                    plan_id,
                    step=step_value,
                    evidence=str(params["evidence"]) if isinstance(params.get("evidence"), str) else None,
                )
            except (KeyError, ValueError) as exc:
                return ToolResult(content=str(exc), success=False, error=str(exc))
            return ToolResult(content=self._plan_service.render_status(record.plan_id))

        if action == "status":
            if not plan_id:
                return ToolResult(
                    content="A plan_id is required to inspect status.",
                    success=False,
                    error="Missing plan_id",
                )
            try:
                return ToolResult(content=self._plan_service.render_status(plan_id))
            except KeyError as exc:
                return ToolResult(content=str(exc), success=False, error=str(exc))

        return ToolResult(
            content=f"Unsupported plan verification action '{action}'.",
            success=False,
            error="Unsupported plan verification action",
        )


class LSPTool(_Tier6LspToolBase):
    """Manage project-local stdio LSP servers."""

    @property
    def name(self) -> str:
        """Return the unique tool identifier."""

        return "lsp"

    @property
    def description(self) -> str:
        """Return the tool description."""

        return "Register, start, stop, and query generic stdio language servers."

    @property
    def parameters(self) -> dict[str, object]:
        """Return the JSON Schema for LSP actions."""

        return _LSP_PARAMETERS

    @property
    def kind(self) -> ToolKind:
        """LSP management launches and communicates with background processes."""

        return ToolKind.EXECUTE

    async def execute(self, **params: object) -> ToolResult:
        """Execute one LSP management action."""

        action = str(params.get("action", "")).strip()
        server = str(params["server"]).strip() if isinstance(params.get("server"), str) else ""

        if action == "register":
            command = str(params["command"]).strip() if isinstance(params.get("command"), str) else ""
            raw_args = params.get("args")
            args = [str(item) for item in raw_args] if isinstance(raw_args, list) else []
            try:
                record = self._lsp_service.register_server(
                    server=server,
                    command=command,
                    args=args,
                    language=str(params["language"]) if isinstance(params.get("language"), str) else None,
                    root_uri=str(params["root_uri"]) if isinstance(params.get("root_uri"), str) else None,
                )
            except ValueError as exc:
                return ToolResult(content=str(exc), success=False, error=str(exc))
            return ToolResult(content=f"Registered LSP server {record.server}.")

        if action == "list":
            records = self._lsp_service.list_servers()
            if not records:
                return ToolResult(content="No LSP servers configured.")
            return ToolResult(
                content="\n".join(
                    f"{record.server}: running={'yes' if record.running else 'no'} language={record.language or '-'}"
                    for record in records
                ),
            )

        if action == "start":
            if not server:
                return ToolResult(content="A server is required to start LSP.", success=False, error="Missing server")
            try:
                record = await self._lsp_service.start_server(server)
            except (KeyError, ValueError, RuntimeError) as exc:
                return ToolResult(content=str(exc), success=False, error=str(exc))
            return ToolResult(content=f"Started LSP server {record.server}.")

        if action == "stop":
            if not server:
                return ToolResult(content="A server is required to stop LSP.", success=False, error="Missing server")
            try:
                stopped_record = await self._lsp_service.stop_server(server)
            except RuntimeError as exc:
                return ToolResult(content=str(exc), success=False, error=str(exc))
            if stopped_record is None:
                return ToolResult(content="LSP server not found.", success=False, error="LSP server not found")
            return ToolResult(content=f"Stopped LSP server {stopped_record.server}.")

        if action == "request":
            method = str(params["method"]).strip() if isinstance(params.get("method"), str) else ""
            raw_request_params = params.get("params")
            request_params: dict[str, object] = (
                {str(key): value for key, value in raw_request_params.items()}
                if isinstance(raw_request_params, dict)
                else {}
            )
            if not server or not method:
                return ToolResult(
                    content="Both server and method are required for LSP requests.",
                    success=False,
                    error="Missing server or method",
                )
            try:
                result = await self._lsp_service.request(server, method, request_params)
            except (KeyError, ValueError, RuntimeError) as exc:
                return ToolResult(content=str(exc), success=False, error=str(exc))
            return ToolResult(content=json.dumps(result, sort_keys=True))

        return ToolResult(
            content=f"Unsupported LSP action '{action}'.",
            success=False,
            error="Unsupported LSP action",
        )


class ScheduleCronTool(_Tier6ScheduleToolBase):
    """Manage project-local recurring cron schedules."""

    @property
    def name(self) -> str:
        """Return the unique tool identifier."""

        return "schedule_cron"

    @property
    def description(self) -> str:
        """Return the tool description."""

        return "Persist and manage cron schedule metadata only; no background runner is started."

    @property
    def parameters(self) -> dict[str, object]:
        """Return the JSON Schema for scheduling actions."""

        return _SCHEDULE_PARAMETERS

    @property
    def kind(self) -> ToolKind:
        """Scheduling mutates project-local state."""

        return ToolKind.WRITE

    async def execute(self, **params: object) -> ToolResult:
        """Execute one scheduling action."""

        action = str(params.get("action", "")).strip()
        schedule_id = str(params["schedule_id"]).strip() if isinstance(params.get("schedule_id"), str) else ""

        if action == "create":
            raw_argv = params.get("argv")
            argv = [str(item) for item in raw_argv] if isinstance(raw_argv, list) else []
            try:
                record = self._schedule_service.create_schedule(
                    title=str(params["title"]) if isinstance(params.get("title"), str) else "",
                    cron=str(params["cron"]) if isinstance(params.get("cron"), str) else "",
                    argv=argv,
                )
            except ValueError as exc:
                return ToolResult(content=str(exc), success=False, error=str(exc))
            return ToolResult(
                content=(
                    f"Created schedule {record.schedule_id}. Metadata only; "
                    "no background runner was started."
                ),
            )

        if action == "list":
            records = self._schedule_service.list_schedules()
            if not records:
                return ToolResult(content="No cron schedule metadata configured.")
            return ToolResult(
                content="Configured cron schedule metadata only (no background runner):\n"
                + "\n".join(
                    f"{record.schedule_id}: {record.title} [{ 'enabled' if record.enabled else 'paused' }] {record.cron}"
                    for record in records
                ),
            )

        if action == "pause":
            if not schedule_id:
                return ToolResult(content="A schedule_id is required to pause.", success=False, error="Missing schedule_id")
            try:
                record = self._schedule_service.pause(schedule_id)
            except KeyError as exc:
                return ToolResult(content=str(exc), success=False, error=str(exc))
            return ToolResult(content=f"Paused schedule {record.schedule_id}.")

        if action == "resume":
            if not schedule_id:
                return ToolResult(content="A schedule_id is required to resume.", success=False, error="Missing schedule_id")
            try:
                record = self._schedule_service.resume(schedule_id)
            except KeyError as exc:
                return ToolResult(content=str(exc), success=False, error=str(exc))
            return ToolResult(content=f"Resumed schedule {record.schedule_id}.")

        if action == "delete":
            if not schedule_id:
                return ToolResult(content="A schedule_id is required to delete.", success=False, error="Missing schedule_id")
            deleted = self._schedule_service.delete(schedule_id)
            if not deleted:
                return ToolResult(content="Schedule not found.", success=False, error="Schedule not found")
            return ToolResult(content=f"Deleted schedule {schedule_id}.")

        return ToolResult(
            content=f"Unsupported schedule action '{action}'.",
            success=False,
            error="Unsupported schedule action",
        )


class TungstenTool(_Tier6TungstenToolBase):
    """Create and compare immutable workspace snapshots."""

    @property
    def name(self) -> str:
        """Return the unique tool identifier."""

        return "tungsten"

    @property
    def description(self) -> str:
        """Return the tool description."""

        return "Create immutable workspace snapshots and compare them deterministically."

    @property
    def parameters(self) -> dict[str, object]:
        """Return the JSON Schema for Tungsten actions."""

        return _TUNGSTEN_PARAMETERS

    @property
    def kind(self) -> ToolKind:
        """Snapshots persist project-local state."""

        return ToolKind.WRITE

    async def execute(self, **params: object) -> ToolResult:
        """Execute one Tungsten action."""

        action = str(params.get("action", "")).strip()

        if action == "snapshot":
            raw_paths = params.get("paths")
            paths = [str(item) for item in raw_paths] if isinstance(raw_paths, list) else None
            record = self._tungsten_service.snapshot(
                name=str(params["name"]) if isinstance(params.get("name"), str) else "snapshot",
                paths=paths,
            )
            return ToolResult(content=f"Created Tungsten snapshot {record.snapshot_id}.")

        if action == "list":
            records = self._tungsten_service.list_snapshots()
            if not records:
                return ToolResult(content="No Tungsten snapshots found.")
            return ToolResult(
                content="\n".join(
                    f"{record.snapshot_id}: {record.name} ({len(record.files)} files)"
                    for record in records
                ),
            )

        if action == "compare":
            left = str(params["left"]).strip() if isinstance(params.get("left"), str) else ""
            right = str(params["right"]).strip() if isinstance(params.get("right"), str) else ""
            if not left or not right:
                return ToolResult(
                    content="Both left and right snapshot IDs are required.",
                    success=False,
                    error="Missing snapshot IDs",
                )
            try:
                diff_lines = self._tungsten_service.compare(left, right)
            except KeyError as exc:
                return ToolResult(content=str(exc), success=False, error=str(exc))
            return ToolResult(content="\n".join(diff_lines))

        return ToolResult(
            content=f"Unsupported Tungsten action '{action}'.",
            success=False,
            error="Unsupported Tungsten action",
        )


__all__ = [
    "LSPTool",
    "MCPTool",
    "McpAuthTool",
    "REPLTool",
    "ScheduleCronTool",
    "TaskCreateTool",
    "TaskGetTool",
    "TaskListTool",
    "TaskOutputTool",
    "TaskStopTool",
    "TaskUpdateTool",
    "TungstenTool",
    "VerifyPlanExecutionTool",
]
