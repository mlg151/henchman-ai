"""Delegate task tool implementation."""

from typing import Any

from henchman.tools.base import Tool, ToolKind, ToolResult


class DelegateTaskTool(Tool):
    """Tool for delegating a task to a specialist agent.

    This tool is intercepted by the Orchestrator to route the task to
    the appropriate specialist.  The schema includes structured context
    fields so the Tech Lead provides a self-contained brief that the
    specialist can act on without prior conversation history.
    """

    @property
    def name(self) -> str:
        """Tool name."""
        return "delegate_task"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Delegate a task to a specialist agent. Each specialist starts with a "
            "CLEAN context, so you MUST provide all relevant information in the "
            "structured fields below. Do not assume the agent remembers anything "
            "from prior delegations.\n\n"
            "**DELEGATION PRIORITY RULES**:\n"
            "1. ALWAYS consider delegation before doing work yourself\n"
            "2. Use specialists for their designated expertise\n"
            "3. Provide COMPLETE context - specialists have no memory\n"
            "4. Include explicit 'done_when' criteria\n\n"
            "**WHEN TO DELEGATE**:\n"
            "- Architecture/design → Planner\n"
            "- Research/exploration → Explorer\n"
            "- Implementation/testing → Engineer\n"
            "- Documentation → Explorer\n"
            "- Complex debugging → Engineer"
        )

    @property
    def parameters(self) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "agent": {
                    "type": "string",
                    "description": (
                        "The role of the specialist agent to delegate to "
                        "(e.g., 'planner', 'explorer', 'engineer')"
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
                        "Be explicit — the agent has no prior knowledge."
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
            },
            "required": ["agent", "task"],
        }

    @property
    def kind(self) -> ToolKind:
        """Tool kind - READ is auto-approved."""
        return ToolKind.READ

    async def execute(  # type: ignore[override]
        self,
        agent: str = "",
        task: str = "",
        done_when: str | None = None,
        context: str | None = None,
        files: list[str] | None = None,
        background: str | None = None,
        requirements: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Stub execution - should be intercepted by Orchestrator.

        Args:
            agent: Target agent role.
            task: Task description.
            done_when: Explicit exit condition for the specialist.
            context: Optional free-form context.
            files: Optional list of relevant file paths.
            background: Optional summary of prior work.
            requirements: Optional acceptance criteria.
            **kwargs: Additional arguments.

        Returns:
            ToolResult indicating delegation was handled.
        """
        return ToolResult(
            content="Delegation handled by orchestrator",
            success=True
        )
