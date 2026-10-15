"""Tier 5 builtin tools for team collaboration workflows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from henchman.team import (
    BridgeSessionService,
    PushNotificationService,
    RemoteTriggerService,
    TeamMemorySyncService,
    TeamWorkspaceService,
    WorkflowService,
)
from henchman.tools.base import Tool, ToolKind, ToolResult

_TEAM_CREATE_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "workspace": {"type": "string"},
        "members": {"type": "array", "items": {"type": "string"}},
        "description": {"type": "string"},
    },
    "required": ["workspace"],
}

_TEAM_DELETE_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {"workspace": {"type": "string"}},
    "required": ["workspace"],
}

_SEND_MESSAGE_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "conversation_id": {
            "type": "string",
            "description": "Dynamic subagent conversation or its parent; omit for legacy workspace messaging",
        },
        "workspace": {"type": "string"},
        "sender": {"type": "string"},
        "message": {"type": "string"},
        "channel": {"type": "string"},
        "recipients": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["message"],
}

_SEND_USER_FILE_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "workspace": {"type": "string"},
        "sender": {"type": "string"},
        "path": {"type": "string"},
        "recipient": {"type": "string"},
        "note": {"type": "string"},
    },
    "required": ["workspace", "sender", "path"],
}

_WORKFLOW_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": [
                "define",
                "run",
                "open_bridge",
                "close_bridge",
                "create_trigger",
                "trigger",
            ],
        },
        "workspace": {"type": "string"},
        "workflow": {"type": "string"},
        "steps": {"type": "array", "items": {"type": "string"}},
        "actor": {"type": "string"},
        "inputs": {"type": "object"},
        "trigger": {"type": "string"},
        "bridge_id": {"type": "string"},
        "remote_session": {"type": "string"},
    },
    "required": ["action", "workspace"],
}


def _require_string(params: dict[str, object], key: str, *, label: str | None = None) -> str:
    """Return a required non-empty string parameter."""

    value = params.get(key)
    cleaned = value.strip() if isinstance(value, str) else ""
    if cleaned:
        return cleaned
    name = label or key.replace("_", " ")
    raise ValueError(f"A {name} is required.")


def _optional_string_list(value: object) -> tuple[str, ...]:
    """Return a tuple of non-empty strings from a list-like value."""

    if not isinstance(value, list | tuple):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _optional_mapping(value: object) -> dict[str, object]:
    """Return a shallow mapping when the value is object-like."""

    return value if isinstance(value, dict) else {}


class _Tier5ToolBase(Tool):
    """Shared runtime binding and service orchestration for Tier 5 tools."""

    def __init__(self) -> None:
        """Initialize the default project-local collaboration services."""

        self._project_root = Path.cwd()
        self._session_manager: Any | None = None
        self._subagent_manager: Any | None = None
        self._refresh_services()

    def bind_runtime(
        self,
        *,
        tool_registry: Any,
        session_manager: Any | None = None,
        project_root: Path | None = None,
        agent: Any | None = None,
        subagent_manager: Any | None = None,
        **kwargs: Any,
    ) -> None:
        """Bind runtime state for interactive use."""

        del tool_registry, agent
        if project_root is not None:
            self._project_root = project_root.resolve()
        if session_manager is not None:
            self._session_manager = session_manager
        if subagent_manager is not None:
            self._subagent_manager = subagent_manager
        self._refresh_services()

    @property
    def kind(self) -> ToolKind:
        """Treat Tier 5 collaboration actions as write operations."""

        return ToolKind.WRITE

    def _refresh_services(self) -> None:
        """Rebuild collaboration services using the current project root."""

        notifications = PushNotificationService(project_root=self._project_root)
        self._workspace_service = TeamWorkspaceService(
            project_root=self._project_root,
            notification_service=notifications,
        )
        self._memory_service = TeamMemorySyncService(project_root=self._project_root)
        self._workflow_service = WorkflowService(
            project_root=self._project_root,
            notification_service=notifications,
        )
        self._bridge_service = BridgeSessionService(
            project_root=self._project_root,
            notification_service=notifications,
        )
        self._trigger_service = RemoteTriggerService(
            project_root=self._project_root,
            workflow_service=self._workflow_service,
            bridge_service=self._bridge_service,
            notification_service=notifications,
        )

    def _sync_current_session_memories(self, workspace_id: str) -> int:
        """Sync the active session memories into the target workspace when possible."""

        session = getattr(self._session_manager, "current", None) if self._session_manager else None
        if session is None:
            return 0
        return len(self._memory_service.sync_session(workspace_id=workspace_id, session=session))


class TeamCreateTool(_Tier5ToolBase):
    """Create a project-local team workspace."""

    @property
    def name(self) -> str:
        """Return the unique tool identifier."""

        return "team_create"

    @property
    def description(self) -> str:
        """Return the tool description."""

        return "Create a team collaboration workspace under project-local storage."

    @property
    def parameters(self) -> dict[str, object]:
        """Return the JSON Schema for team creation parameters."""

        return _TEAM_CREATE_PARAMETERS

    async def execute(self, **params: object) -> ToolResult:
        """Create a new workspace."""

        record = self._workspace_service.create_workspace(
            name=_require_string(params, "workspace"),
            members=_optional_string_list(params.get("members")),
            description=str(params["description"]) if isinstance(params.get("description"), str) else None,
        )
        return ToolResult(
            content=(
                f'Created team workspace "{record.workspace_id}" '
                f"with {len(record.members)} member(s)."
            ),
        )


class TeamDeleteTool(_Tier5ToolBase):
    """Delete a project-local team workspace."""

    @property
    def name(self) -> str:
        """Return the unique tool identifier."""

        return "team_delete"

    @property
    def description(self) -> str:
        """Return the tool description."""

        return "Delete a team collaboration workspace and its persisted state."

    @property
    def parameters(self) -> dict[str, object]:
        """Return the JSON Schema for team deletion parameters."""

        return _TEAM_DELETE_PARAMETERS

    async def execute(self, **params: object) -> ToolResult:
        """Delete an existing workspace."""

        workspace = _require_string(params, "workspace")
        deleted = self._workspace_service.delete_workspace(workspace)
        if not deleted:
            return ToolResult(
                content=f'Team workspace "{workspace}" was not found.',
                success=False,
                error="Workspace not found",
            )
        return ToolResult(content=f'Deleted team workspace "{workspace}".')


class SendMessageTool(_Tier5ToolBase):
    """Send a message to a workspace channel."""

    @property
    def name(self) -> str:
        """Return the unique tool identifier."""

        return "send_message"

    @property
    def description(self) -> str:
        """Return the tool description."""

        return "Message a background subagent conversation, or send a legacy workspace channel message."

    @property
    def parameters(self) -> dict[str, object]:
        """Return the JSON Schema for message parameters."""

        return _SEND_MESSAGE_PARAMETERS

    async def execute(self, **params: object) -> ToolResult:
        """Persist one team message and sync the active session memories."""

        if "conversation_id" in params:
            if self._subagent_manager is None:
                return ToolResult(
                    content="Dynamic subagent messaging requires a bound runtime.",
                    success=False, error="Subagent runtime unavailable",
                )
            try:
                if "workspace" in params or "sender" in params:
                    raise ValueError("Use conversation_id or workspace/sender, not both.")
                target = _require_string(params, "conversation_id")
                await self._subagent_manager.send_message(
                    target, _require_string(params, "message"),
                )
                return ToolResult(content=json.dumps({"conversation_id": target, "queued": True}))
            except (ValueError, PermissionError, RuntimeError) as exc:
                return ToolResult(content=str(exc), success=False, error=str(exc))
        workspace = _require_string(params, "workspace")
        recipients = _optional_string_list(params.get("recipients"))
        record = self._workspace_service.post_message(
            workspace_id=workspace,
            sender=_require_string(params, "sender"),
            body=_require_string(params, "message", label="message"),
            channel=str(params["channel"]) if isinstance(params.get("channel"), str) else "general",
            recipients=recipients,
        )
        synced_count = self._sync_current_session_memories(record.workspace_id)
        return ToolResult(
            content=(
                f'Sent message to "{record.workspace_id}/{record.channel}" '
                f"for {len(recipients)} recipient(s); synced {synced_count} memory record(s)."
            ),
        )


class SendUserFileTool(_Tier5ToolBase):
    """Share a file into a team workspace."""

    @property
    def name(self) -> str:
        """Return the unique tool identifier."""

        return "send_user_file"

    @property
    def description(self) -> str:
        """Return the tool description."""

        return "Copy a local file into a team workspace and notify the recipient."

    @property
    def parameters(self) -> dict[str, object]:
        """Return the JSON Schema for file-share parameters."""

        return _SEND_USER_FILE_PARAMETERS

    async def execute(self, **params: object) -> ToolResult:
        """Persist one shared file and sync the active session memories."""

        workspace = _require_string(params, "workspace")
        record = self._workspace_service.share_file(
            workspace_id=workspace,
            sender=_require_string(params, "sender"),
            path=_require_string(params, "path"),
            recipient=str(params["recipient"]) if isinstance(params.get("recipient"), str) else None,
            note=str(params["note"]) if isinstance(params.get("note"), str) else None,
        )
        synced_count = self._sync_current_session_memories(record.workspace_id)
        return ToolResult(
            content=(
                f'Shared "{Path(record.original_path).name}" into "{record.workspace_id}" '
                f'and synced {synced_count} memory record(s).'
            ),
        )


class WorkflowTool(_Tier5ToolBase):
    """Prepare workflow metadata and manage triggers and bridge sessions."""

    @property
    def name(self) -> str:
        """Return the unique tool identifier."""

        return "workflow"

    @property
    def description(self) -> str:
        """Return the tool description."""

        return (
            "Define workflow metadata and manage collaboration triggers and bridges. "
            "Run and trigger actions prepare rendered steps only and report execution unavailable."
        )

    @property
    def parameters(self) -> dict[str, object]:
        """Return the JSON Schema for workflow parameters."""

        return _WORKFLOW_PARAMETERS

    async def execute(self, **params: object) -> ToolResult:
        """Run the requested workflow action."""

        action = _require_string(params, "action")
        workspace = _require_string(params, "workspace")
        if action == "define":
            definition = self._workflow_service.define(
                workspace_id=workspace,
                workflow_name=_require_string(params, "workflow"),
                steps=_optional_string_list(params.get("steps")),
                created_by=_require_string(params, "actor"),
            )
            return ToolResult(
                content=(
                    f'Defined workflow "{definition.workflow_name}" '
                    f"with {len(definition.steps)} step(s)."
                ),
            )
        if action == "run":
            run = self._workflow_service.run(
                workspace_id=workspace,
                workflow_name=_require_string(params, "workflow"),
                requested_by=_require_string(params, "actor"),
                inputs=_optional_mapping(params.get("inputs")),
            )
            return ToolResult(
                content=(
                    f'Prepared workflow "{run.workflow_name}" with rendered steps: '
                    f"{', '.join(run.rendered_steps)}. "
                    "Execution is unavailable. No steps were executed."
                ),
                success=False,
                error="Workflow execution is unavailable",
            )
        if action == "open_bridge":
            bridge = self._bridge_service.open_bridge(
                workspace_id=workspace,
                remote_session=_require_string(params, "remote_session", label="remote session"),
                created_by=_require_string(params, "actor"),
            )
            return ToolResult(
                content=f'Opened bridge "{bridge.bridge_id}" for "{bridge.remote_session}".',
            )
        if action == "close_bridge":
            bridge = self._bridge_service.close_bridge(
                workspace_id=workspace,
                bridge_id=_require_string(params, "bridge_id", label="bridge id"),
            )
            return ToolResult(content=f'Closed bridge "{bridge.bridge_id}".')
        if action == "create_trigger":
            trigger = self._trigger_service.create_trigger(
                workspace_id=workspace,
                trigger_name=_require_string(params, "trigger"),
                workflow_name=_require_string(params, "workflow"),
                created_by=_require_string(params, "actor"),
                bridge_session_id=(
                    str(params["bridge_id"]) if isinstance(params.get("bridge_id"), str) else None
                ),
            )
            return ToolResult(
                content=(
                    f'Created trigger "{trigger.trigger_name}" '
                    f'for workflow "{trigger.workflow_name}".'
                ),
            )
        if action == "trigger":
            run = self._trigger_service.invoke_trigger(
                workspace_id=workspace,
                trigger_name=_require_string(params, "trigger"),
                invoked_by=_require_string(params, "actor"),
                inputs=_optional_mapping(params.get("inputs")),
            )
            return ToolResult(
                content=(
                    f'Prepared triggered workflow "{run.workflow_name}" with rendered steps: '
                    f"{', '.join(run.rendered_steps)}. "
                    "Execution is unavailable. No steps were executed."
                ),
                success=False,
                error="Workflow execution is unavailable",
            )
        return ToolResult(
            content=f'Unsupported workflow action "{action}".',
            success=False,
            error="Unsupported workflow action",
        )


__all__ = [
    "SendMessageTool",
    "SendUserFileTool",
    "TeamCreateTool",
    "TeamDeleteTool",
    "WorkflowTool",
]
