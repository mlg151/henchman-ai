"""Runtime-bound tools for dynamic background agent conversations."""

from __future__ import annotations

import json

from henchman.agents.subagents import BackgroundSubagentManager
from henchman.tools.base import Tool, ToolKind, ToolResult


class _SubagentTool(Tool):
    def __init__(self, manager: BackgroundSubagentManager | None = None) -> None:
        self._manager = manager

    def bind_runtime(
        self,
        *,
        subagent_manager: BackgroundSubagentManager | None = None,
        **kwargs: object,
    ) -> None:
        """Attach the live runtime without creating a second manager."""
        del kwargs
        if subagent_manager is not None:
            self._manager = subagent_manager

    def _require_manager(self) -> BackgroundSubagentManager:
        if self._manager is None:
            raise RuntimeError("Background subagent runtime is not initialized")
        return self._manager


def _required_string(params: dict[str, object], name: str) -> str:
    value = params.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _failure(exc: Exception) -> ToolResult:
    message = str(exc)
    return ToolResult(content=message, success=False, error=message)


class InvokeSubagentTool(_SubagentTool):
    """Launch an independent custom agent without waiting for its result."""

    @property
    def name(self) -> str:
        return "invoke_subagent"

    @property
    def description(self) -> str:
        return (
            "Launch a background subagent with a custom role, system prompt, task, and explicit "
            "tool subset. Returns a conversation_id immediately; results and requests for input "
            "arrive as parent notifications. Use send_message for follow-ups."
        )

    @property
    def kind(self) -> ToolKind:
        return ToolKind.EXECUTE

    @property
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Concrete delegated work."},
                "role": {"type": "string", "description": "Custom descriptive role."},
                "system_prompt": {"type": "string", "description": "Custom agent instructions."},
                "tools": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Explicit subset of your available tools; [] grants no tools.",
                },
            },
            "required": ["task", "role", "system_prompt", "tools"],
            "additionalProperties": False,
        }

    async def execute(self, **params: object) -> ToolResult:
        """Validate scope and start an owned background conversation."""
        try:
            manager = self._require_manager()
            tools = params.get("tools")
            if not isinstance(tools, list) or not all(isinstance(name, str) for name in tools):
                raise ValueError("tools must be an explicit list of tool names")
            record = manager.spawn(
                _required_string(params, "task"),
                role=_required_string(params, "role"),
                system_prompt=_required_string(params, "system_prompt"),
                tools=tools,
            )
            return ToolResult(content=json.dumps(record.as_dict()))
        except (ValueError, PermissionError, RuntimeError) as exc:
            return _failure(exc)


class ManageSubagentsTool(_SubagentTool):
    """Inspect descendants or cancel and join one background worker."""

    @property
    def name(self) -> str:
        return "manage_subagents"

    @property
    def description(self) -> str:
        return (
            "List background subagents, inspect one conversation's status and bounded output, "
            "or cancel a subagent. Results and assistance requests arrive reactively; polling "
            "is unnecessary. Completed conversations accept follow-ups through send_message."
        )

    @property
    def kind(self) -> ToolKind:
        return ToolKind.WRITE

    def execution_kind(self, params: dict[str, object]) -> ToolKind:
        """Keep status reads available while applying policy to cancellation."""
        return ToolKind.READ if params.get("action", "list") in ("list", "get") else ToolKind.WRITE

    @property
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "get", "cancel"], "default": "list"},
                "conversation_id": {"type": "string", "description": "Required for get or cancel."},
            },
            "additionalProperties": False,
        }

    async def execute(self, **params: object) -> ToolResult:
        """Perform a scoped read or explicit cancellation without polling."""
        try:
            manager = self._require_manager()
            action = params.get("action", "list")
            if action == "list":
                value: object = [record.as_dict() for record in manager.list()]
            elif action in ("get", "cancel"):
                conversation_id = _required_string(params, "conversation_id")
                record = (
                    await manager.cancel(conversation_id)
                    if action == "cancel"
                    else manager.get(conversation_id)
                )
                value = record.as_dict()
            else:
                raise ValueError("action must be list, get, or cancel")
            return ToolResult(content=json.dumps(value))
        except (ValueError, PermissionError, RuntimeError) as exc:
            return _failure(exc)
