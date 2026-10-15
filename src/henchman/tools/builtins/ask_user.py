"""Ask user for input tool.

This tool allows the agent to ask the user for input during execution.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from henchman.tools.base import Tool, ToolKind, ToolResult

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from henchman.tools.base import ConfirmationRequest


def _unanswered(question: str, reason: str) -> ToolResult:
    """Preserve the question while explicitly reporting that no answer exists."""
    content = f"Question: {question}\n{reason}"
    return ToolResult(content=content, display=content, success=False, error=reason)


class AskUserTool(Tool):
    """Tool for asking the user for input.

    This tool allows the agent to request user input during execution,
    which is useful for clarifying ambiguous requests or getting
    additional information.

    A runtime must supply an async input handler before questions can be answered.
    An unbound instance reports unavailable input, including in headless execution.
    """

    def __init__(
        self,
        question_handler: Callable[[str], Awaitable[str | None]] | None = None,
    ) -> None:
        """Bind an optional input channel; None from a handler means unanswered."""
        self._question_handler = question_handler

    @property
    def name(self: AskUserTool) -> str:
        """Return the tool name."""
        return "ask_user"

    @property
    def description(self: AskUserTool) -> str:
        """Return the tool description."""
        return "Ask the user a question through a configured input handler and wait for their response"

    @property
    def parameters(self: AskUserTool) -> dict[str, object]:
        """Return the tool parameters schema."""
        return {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to ask the user",
                    "minLength": 1,
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (0 for no timeout)",
                    "default": 0,
                    "minimum": 0,
                },
            },
            "required": ["question"],
        }

    @property
    def kind(self: AskUserTool) -> ToolKind:
        """Return the tool kind."""
        return ToolKind.READ  # Always auto-approved since it's just asking

    def needs_confirmation(
        self: AskUserTool, params: dict[str, object],
    ) -> ConfirmationRequest | None:
        """Check if this tool needs confirmation.

        Args:
            params: The tool parameters.

        Returns:
            None, since asking questions doesn't need confirmation.
        """
        return None  # Never needs confirmation

    async def execute(self: AskUserTool, **params: object) -> ToolResult:
        """Execute the ask_user tool.

        Args:
            params: Tool parameters passed as keyword arguments.
                Expected parameters:
                    question (str): The question to ask the user.
                    timeout (int, optional): Timeout in seconds (0 for no timeout).
                        Defaults to 0.

        Returns:
            The actual answer, or an explicit failure when no answer is available.
            Caller cancellation propagates to the input handler.
        """
        question = params.get("question", "")
        if not isinstance(question, str) or not question.strip():
            return _unanswered("", "question must be a nonempty string")
        timeout = params.get("timeout", 0)
        if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout < 0:
            return _unanswered(question, "timeout must be a nonnegative integer")
        if self._question_handler is None:
            return _unanswered(question, "No user input handler is configured; no answer was received")
        try:
            answer = await asyncio.wait_for(
                self._question_handler(question), timeout=timeout or None,
            )
        except TimeoutError:
            return _unanswered(question, f"User input timed out after {timeout}s; no answer was received")
        except Exception as exc:
            return _unanswered(question, f"User input failed: {exc}")
        if not isinstance(answer, str) or not answer.strip():
            return _unanswered(question, "No user answer was received")
        return ToolResult(
            content=answer,
            display=f"Question: {question}\nAnswer: {answer}",
            success=True,
        )
