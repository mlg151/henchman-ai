"""Runtime-bound tools for dynamic background agent conversations."""

from __future__ import annotations

import json

from henchman.agents.delegation_admission import DelegationAdmissionError
from henchman.agents.subagents import BackgroundSubagentManager
from henchman.core.operation_recovery import OperationRecoveryError
from henchman.core.run_budget import BudgetControlError
from henchman.providers.continuation import ProviderContinuationError
from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.repair_scope import RepairControlError


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
    if isinstance(exc, (OperationRecoveryError, BudgetControlError, ProviderContinuationError, RepairControlError)):
        raise exc
    message = str(exc)
    if isinstance(exc, DelegationAdmissionError):
        return ToolResult(content=json.dumps({"message": message, "admission": exc.payload}),
                          success=False, error=message, metadata={"admission": exc.payload})
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
            "arrive as parent notifications. Requires prior user/runtime delegation opt-in "
            "and shared capacity. Supply write_paths for staged file-only work that requires "
            "parent review before publication. Use send_message for ordinary follow-ups."
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
                "write_paths": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Optional explicit project-relative files for staged child work.",
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
            task, role, prompt = (_required_string(params, name) for name in ("task", "role", "system_prompt"))
            if "write_paths" in params:
                paths = params["write_paths"]
                if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
                    raise ValueError("write_paths must be a list of paths")
                record = manager.spawn(task, role=role, system_prompt=prompt, tools=tools, write_paths=paths)
            else:
                record = manager.spawn(task, role=role, system_prompt=prompt, tools=tools)
            return ToolResult(content=json.dumps(record.as_dict()))
        except (ValueError, PermissionError, RuntimeError) as exc:
            return _failure(exc)


class ManageSubagentsTool(_SubagentTool):
    """Inspect or cancel children and review staged proposals."""

    @property
    def name(self) -> str:
        return "manage_subagents"

    @property
    def description(self) -> str:
        return (
            "List background subagents, inspect one conversation's status and bounded output, "
            "or cancel a subagent. Results and assistance requests arrive reactively; polling "
            "is unnecessary. For staged children, review the complete proposal and use "
            "publish_subagent_proposal with its review_token; staged children do not accept follow-ups."
        )

    @property
    def kind(self) -> ToolKind:
        return ToolKind.WRITE

    def execution_kind(self, params: dict[str, object]) -> ToolKind:
        """Keep inspection and review read-only; apply write policy to effects."""
        return ToolKind.READ if params.get("action", "list") in ("list", "get", "review") else ToolKind.WRITE

    @property
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "get", "cancel", "review"], "default": "list"},
                "conversation_id": {"type": "string", "description": "Required for every action except list."},
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
            elif action == "review":
                return ToolResult(content=await manager.review_staged(_required_string(params, "conversation_id")))
            else:
                raise ValueError("action must be list, get, cancel, or review")
            return ToolResult(content=json.dumps(value))
        except (ValueError, PermissionError, RuntimeError) as exc:
            return _failure(exc)


class PublishSubagentProposalTool(_SubagentTool):
    """Publish one complete parent-reviewed child proposal under WRITE policy."""

    @property
    def name(self) -> str:
        return "publish_subagent_proposal"

    @property
    def description(self) -> str:
        return "Publish a completed staged child's exact reviewed proposal using its review_token."

    @property
    def kind(self) -> ToolKind:
        return ToolKind.WRITE

    @property
    def parameters(self) -> dict[str, object]:
        return {"type": "object", "properties": {
            "conversation_id": {"type": "string", "description": "The directly owned staged child."},
            "review_token": {"type": "string", "description": "Token from the complete parent review."},
        }, "required": ["conversation_id", "review_token"], "additionalProperties": False}

    async def execute(self, **params: object) -> ToolResult:
        try:
            result = self._require_manager().publish_staged(_required_string(params, "conversation_id"),
                                                            _required_string(params, "review_token"))
            return ToolResult(content=json.dumps({"changed_paths": list(result.changed_paths),
                                                  "invalidate_checks": result.invalidate_checks}))
        except (ValueError, PermissionError, RuntimeError) as exc:
            return _failure(exc)
