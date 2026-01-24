"""Ask user for input tool.

This tool allows the agent to ask the user for input during execution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from henchman.tools.base import Tool, ToolKind, ToolResult

if TYPE_CHECKING:
    from henchman.tools.base import ConfirmationRequest


class AskUserTool(Tool):
    """Tool for asking the user for input.

    This tool allows the agent to request user input during execution,
    which is useful for clarifying ambiguous requests or getting
    additional information.

    Example:
        >>> tool = AskUserTool()
        >>> result = await tool.execute(question="What is your name?")
    """

    @property
    def name(self) -> str:
        """Return the tool name."""
        return "ask_user"

    @property
    def description(self) -> str:
        """Return the tool description."""
        return "Ask the user a question and wait for their response"

    @property
    def parameters(self) -> dict[str, object]:
        """Return the tool parameters schema."""
        return {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to ask the user",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (0 for no timeout)",
                    "default": 0,
                },
            },
            "required": ["question"],
        }

    @property
    def kind(self) -> ToolKind:
        """Return the tool kind."""
        return ToolKind.READ  # Always auto-approved since it's just asking

    def needs_confirmation(self, params: dict[str, object]) -> ConfirmationRequest | None:
        """Check if this tool needs confirmation.

        Args:
            params: The tool parameters.

        Returns:
            None, since asking questions doesn't need confirmation.
        """
        return None  # Never needs confirmation

    async def execute(self, **params: object) -> ToolResult:
        """Execute the ask_user tool.

        Args:
            **params: Tool parameters including 'question' and optional 'timeout'.

        Returns:
            A ToolResult containing the user's response.

        Raises:
            TimeoutError: If timeout is reached before user responds.
        """
        # Extract parameters
        question = str(params.get("question", ""))
        # timeout parameter is extracted but not used in placeholder implementation

        # In interactive mode, this would prompt the user
        # For now, we'll simulate it by returning a placeholder
        # The actual implementation would need to integrate with the REPL
        return ToolResult(
            content="[User input would be collected here in interactive mode]",
            display=f"🤔 Question: {question}\n💬 (User input would be collected here)",
            success=True,
        )
