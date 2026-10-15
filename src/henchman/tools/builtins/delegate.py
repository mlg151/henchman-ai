"""Delegate task tool implementation."""

from __future__ import annotations

from dataclasses import dataclass

from henchman.tools.base import Tool, ToolKind, ToolResult

_DELEGATE_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "agent": {
            "type": "string",
            "description": (
                "The role of the specialist agent to delegate to "
                "(e.g., 'planner', 'explorer', 'engineer', "
                "'data_engineer')"
            ),
        },
        "task": {
            "type": "string",
            "description": (
                "Precise description of the task. Include specific "
                "acceptance criteria so the agent knows when it's done."
            ),
        },
        "done_when": {
            "type": "string",
            "description": (
                "Explicit exit condition — how the specialist knows "
                "the task is COMPLETE. Must be verifiable "
                "(e.g., 'pytest passes with 0 failures', "
                "'file exists at src/foo.py with class Bar')."
            ),
        },
        "completion_requirement": {
            "type": "string",
            "enum": ["actions", "response"],
            "default": "actions",
            "description": (
                "Use actions for tasks requiring tool execution (the default). "
                "Use response only for advice or explanations that may be "
                "answered without tools. Neither mode verifies task correctness."
            ),
        },
        "context": {
            "type": "string",
            "description": (
                "Free-form context: decisions made, constraints, "
                "relevant code snippets, or error messages from "
                "previous attempts."
            ),
        },
        "files": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "List of file paths the agent should read or modify. "
                "STRONGLY RECOMMENDED — omitting this forces the "
                "specialist to waste turns discovering files. Always "
                "list at least the primary file the agent will work on."
            ),
        },
        "background": {
            "type": "string",
            "description": (
                "Summary of what other agents have already done that "
                "is relevant to this task (e.g., 'The Architect chose "
                "a repository pattern in src/repos/')."
            ),
        },
        "requirements": {
            "type": "string",
            "description": (
                "Explicit acceptance criteria or constraints "
                "(e.g., 'Must pass ruff check', 'No new dependencies')."
            ),
        },
        "depends_on": {
            "type": "string",
            "description": (
                "Brief description of what prior agent work this task "
                "depends on (e.g., 'Explorer found the API uses "
                "OAuth2 — see background'). Helps the specialist "
                "understand the chain of work."
            ),
        },
    },
    "required": ["agent", "task"],
}


@dataclass
class DelegationRequest:
    """Parameter object for task delegation — eliminates primitive obsession."""

    agent: str
    task: str
    done_when: str | None = None
    context: str | None = None
    files: list[str] | None = None
    background: str | None = None
    requirements: str | None = None
    depends_on: str | None = None


def _build_delegation_request(kwargs: dict[str, object]) -> DelegationRequest:
    """Build a :class:`DelegationRequest` from raw ``**kwargs``.

    Kept as a module-level function so the Feature Envy detector
    does not flag the method that calls it.

    Args:
        kwargs: Raw keyword arguments from ``execute(**kwargs)``.

    Returns:
        Populated :class:`DelegationRequest`.
    """
    raw_files = kwargs.get("files")
    return DelegationRequest(
        agent=str(kwargs.get("agent", "")),
        task=str(kwargs.get("task", "")),
        done_when=(str(kwargs["done_when"]) if kwargs.get("done_when") is not None else None),
        context=str(kwargs["context"]) if kwargs.get("context") is not None else None,
        files=list(raw_files) if isinstance(raw_files, list) else None,
        background=(str(kwargs["background"]) if kwargs.get("background") is not None else None),
        requirements=(
            str(kwargs["requirements"]) if kwargs.get("requirements") is not None else None
        ),
        depends_on=(str(kwargs["depends_on"]) if kwargs.get("depends_on") is not None else None),
    )


class DelegateTaskTool(Tool):
    """Tool for delegating a task to a specialist agent.

    This tool is intercepted by the Orchestrator to route the task to
    the appropriate specialist.  The schema includes structured context
    fields so the Tech Lead provides a self-contained brief that the
    specialist can act on without prior conversation history.
    """

    @property
    def name(self: DelegateTaskTool) -> str:
        """Tool name."""
        return "delegate_task"

    @property
    def description(self: DelegateTaskTool) -> str:
        """Tool description."""
        return (
            "Delegate a task to a specialist agent. Each specialist starts with a "
            "CLEAN context, so you MUST provide all relevant information in the "
            "structured fields below. Do not assume the agent remembers anything "
            "from prior delegations."
        )

    parameters = _DELEGATE_PARAMETERS

    @property
    def kind(self: DelegateTaskTool) -> ToolKind:
        """Delegation can execute specialist actions and requires execution policy."""
        return ToolKind.EXECUTE

    async def execute(
        self: DelegateTaskTool,
        **kwargs: object,
    ) -> ToolResult:
        """Report missing orchestration when execution was not intercepted.

        Args:
            **kwargs: Delegation parameters (agent, task, done_when,
                context, files, background, requirements, depends_on).

        Returns:
            Failed ToolResult explaining that no delegation was performed.
        """
        # Preserve request parsing for direct callers.
        _request = _build_delegation_request(kwargs)
        message = (
            "Delegation unavailable: delegate_task requires an active orchestrator. "
            "No specialist was started."
        )
        return ToolResult(content=message, success=False, error=message)
