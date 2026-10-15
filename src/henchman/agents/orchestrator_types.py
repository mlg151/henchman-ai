"""Data types, enums, and constants for the orchestrator module."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, StrEnum
from typing import TYPE_CHECKING, Any

from .ledger import MAX_GOAL_PREVIEW_LENGTH

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from henchman.core.events import AgentEvent


class CompletionRequirement(StrEnum):
    """Evidence needed to accept execution; neither option verifies task correctness."""

    RESPONSE = "response"
    ACTIONS = "actions"


@dataclass
class AgentLoopParams:
    """Parameters for running an agent loop."""

    agent: Any = None
    target_role: str | None = None
    input_text: str = ""
    depth: int = 0
    max_turns: int = 0
    msg_start_index: int = 0
    brief: dict[str, Any] | None = None
    completion_requirement: CompletionRequirement = CompletionRequirement.ACTIONS


@dataclass
class DelegationParams:
    """Parameters for delegating a task to a specialist agent."""

    target_role: str
    task: str
    brief: dict[str, Any] | None = None
    depth: int = 0
    target_agent: Any = None
    full_task: str = ""
    msg_start: int = 0


@dataclass
class DelegationExecutionParams:
    """Parameters for executing a delegation flow.

    Encapsulates the repeated primitive parameter group used in
    ``_execute_delegation_flow`` and ``_execute_delegation`` methods.
    """

    target: str
    task: str
    depth: int
    tool_call: Any = None
    agent: Any = None
    ledger_record: Any = None


@dataclass
class LoopState:
    """Internal state for the agent execution loop."""

    tool_call_count: int = 0
    tool_round_count: int = 0
    successful_tool_call_count: int = 0
    tool_errors: list[str] = field(default_factory=list)
    wrapup_warned: bool = False
    colon_stall_retries: int = 0
    timed_out: bool = False
    failed: bool = False
    response_complete: bool = False
    completion_requirement: CompletionRequirement = CompletionRequirement.ACTIONS


@dataclass
class NoPendingToolsResult:
    """Result of handling no pending tools."""

    events_to_yield: list[AgentEvent] = field(default_factory=list)
    colon_stall_detected: bool = False
    colon_stall_result: tuple[AsyncIterator[AgentEvent], int] | None = None


class CompletionStatus(Enum):
    """Status of an agent's work upon completion.

    Used in ``AGENT_COMPLETED`` event data to distinguish genuine
    completion from cases where the agent ended without doing work.
    """

    COMPLETED = "completed"
    """Execution included successful tools; task correctness remains unverified."""

    RESPONDED = "responded"
    """Agent delivered a normal response without tools; no task verification is implied."""

    NO_WORK_DONE = "no_work_done"
    """Agent did not supply the required response or successful action evidence."""

    STALLED = "stalled"
    """Agent announced intent repeatedly but never acted."""

    TIMED_OUT = "timed_out"
    """Agent hit the turn limit before finishing."""

    FAILED = "failed"
    """Agent execution failed or the provider ended with a non-success reason."""


# ---------------------------------------------------------------------------
# Public configuration constants
# ---------------------------------------------------------------------------

MAX_USER_INPUT_LENGTH = MAX_GOAL_PREVIEW_LENGTH
"""Compatibility alias for ledger goal previews; canonical user input is retained."""

MAX_ERROR_MESSAGE_LENGTH = 200
"""Maximum length for error message truncation."""

MAX_SUMMARY_LENGTH = 200
"""Maximum length for summary text truncation."""

MAX_STALL_NUDGES = 10
"""Maximum number of stall nudges before marking as stalled."""

RECENT_TOOLS_TO_SHOW = 10
"""Number of recent tool calls to show in timeout summaries."""

MAX_TOOL_CALL_DISPLAY_LENGTH = 120
"""Maximum length for displaying tool call names in summaries."""

MAX_NARRATION_DISPLAY_LENGTH = 300
"""Maximum length for displaying narration in timeout summaries."""

MAX_TOOL_ARGUMENTS_TO_DISPLAY = 2
"""Maximum number of tool arguments to show in summaries."""

# ---------------------------------------------------------------------------
# Private configuration constants
# ---------------------------------------------------------------------------

ROLE_ANCHOR_INTERVAL = 8
"""Interval (in tool calls) for role anchoring reminders."""

WRAPUP_WARNING_OFFSET = 3
"""Turns before limit to inject wrap-up warning."""

MIN_THINKING_LINES = 3
"""Minimum numbered lines for quality thinking pattern."""

THINKING_QUALITY_INCREMENT = 5
"""Points added for quality thinking pattern."""

MAX_THINKING_SCORE = 100
"""Maximum thinking quality score."""

TOOL_ERROR_MAX_LENGTH = 200
"""Max length for tool error messages in summaries."""

RESULT_PREVIEW_LENGTH = 500
"""Length of tool result preview in events."""

MAX_COLON_STALL_RETRIES = 3
"""Max retries for colon-ending stall nudge."""

COLON_STALL_MIN_LENGTH = 20
"""Minimum response length for colon-stall check."""

COLON_STALL_NUDGE = (
    "STOP. You ended your response with a colon \u2014 you announced what you "
    "were about to do but then stopped without doing it. Do NOT narrate or "
    "describe your plan. Actually perform the work NOW by calling the "
    "appropriate tool. If you cannot act, explain why."
)
"""Colon-stall nudge message sent when an agent ends its response with ':'."""

DELEGATE_TASK_TOOL = "delegate_task"
"""Name of the delegate_task tool."""
