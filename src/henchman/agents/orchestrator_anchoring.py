"""Role anchoring and completion assessment helpers.

Provides periodic role-identity reminders during long agent loops
and evaluates whether an agent performed meaningful work.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from henchman.providers.base import Message

from .orchestrator_types import ROLE_ANCHOR_INTERVAL, CompletionStatus

if TYPE_CHECKING:
    from henchman.core.agent import Agent


def inject_role_anchor(
    orchestrator: Any,
    agent: Agent,
    tool_call_count: int,
) -> None:
    """Inject periodic role anchoring reminder if needed.

    Args:
        orchestrator: The orchestrator instance managing the agent.
        agent: The agent to inject the role anchor message to.
        tool_call_count: Current count of tool calls in the loop.

    Returns:
        None: The function modifies the agent's messages in-place.
    """
    if tool_call_count <= 0 or tool_call_count % ROLE_ANCHOR_INTERVAL != 0:
        return
    if not agent.identity:
        return
    role_id = agent.identity.role or agent.identity.id
    mission_note = ""
    ledger = orchestrator.ledger
    if ledger:
        recap = ledger.mission_recap()
        if recap:
            mission_note = f" Mission: {recap}"
    anchor_msg = (
        f"[Role Anchor] You are the {role_id.upper()}. "
        f"Stay focused on your assigned responsibilities. "
        f"Do not overstep your role boundaries.{mission_note}"
    )
    agent.messages.append(Message(role="user", content=anchor_msg))


def _parse_tool_call_count(raw_value: Any) -> int:
    """Parse raw tool call count into an integer, raising TypeError if invalid."""
    if raw_value is None:
        return 0
    if isinstance(raw_value, bool):
        return 1 if raw_value else 0
    if isinstance(raw_value, (int, float)):
        return max(0, int(raw_value))
    if isinstance(raw_value, str):
        stripped = raw_value.strip()
        if not stripped:
            return 0
        try:
            return max(0, int(stripped))
        except (ValueError, TypeError) as err:
            raise TypeError(
                f"_last_loop_tool_call_count must be integer, got string '{raw_value}'",
            ) from err
    raise TypeError(
        f"_last_loop_tool_call_count must be integer, got {type(raw_value).__name__}",
    )


def assess_agent_completion(orchestrator: Any, agent: Agent) -> CompletionStatus:
    """Assess whether an agent performed meaningful work.

    Args:
        orchestrator: The orchestrator instance managing the agent.
        agent: The agent to assess completion status for.

    Returns:
        CompletionStatus: The completion status of the agent
            (STALLED, NO_WORK_DONE, TIMED_OUT, or COMPLETED).
    """
    raw_tool_calls = getattr(orchestrator, "_last_loop_tool_call_count", 0)
    tool_calls = _parse_tool_call_count(raw_tool_calls)
    raw_success = getattr(orchestrator, "_last_loop_success_count", 0)
    success_calls = _parse_tool_call_count(raw_success)
    timed_out = getattr(orchestrator, "_last_loop_timed_out", False)

    stalled = False

    stall_detector = getattr(agent, "_stall", None)
    if stall_detector is not None and _is_truthy_failure(getattr(stall_detector, "failure", None)):
        stalled = True

    if not stalled and _is_truthy_failure(getattr(agent, "_stall_failure", None)):
        stalled = True

    if stalled:
        return CompletionStatus.STALLED
    if timed_out:
        return CompletionStatus.TIMED_OUT
    if success_calls == 0:
        return CompletionStatus.NO_WORK_DONE
    return CompletionStatus.COMPLETED


def _is_truthy_failure(value: Any) -> bool:
    """Check if a failure value indicates a stall.

    Args:
        value: The failure value to check (typically a bool or None).

    Returns:
        True if the value is truthy (indicating a stall failure).
    """
    if value is None:
        return False
    return bool(value)


# ---------------------------------------------------------------------------
# Semantic completion enrichment
# ---------------------------------------------------------------------------

_FAILURE_STATUS_TOKENS: frozenset[str] = frozenset(
    {"failed", "blocked", "error", "incomplete", "failure"},
)
"""Lowercase status tokens that indicate the specialist did not succeed."""


def _enrich_completion_from_report(
    base_status: CompletionStatus,
    parsed: dict[str, str],
) -> CompletionStatus:
    """Refine a completion status using structured completion-report fields.

    Specialists are prompted to emit a structured completion report with
    fields such as ``STATUS`` and ``BLOCKERS``.  This function downgrades
    a ``COMPLETED`` base status when those fields signal failure, and
    passes through definitive failure statuses (``STALLED``,
    ``NO_WORK_DONE``, ``TIMED_OUT``) unchanged.

    Args:
        base_status: The coarse status derived from tool-call counts / stall
            detection (output of ``assess_agent_completion``).
        parsed: Dict extracted from the agent's completion report by
            ``_parse_completion_report`` in ``delegation.py``.

    Returns:
        The refined ``CompletionStatus``.
    """
    if base_status in (
        CompletionStatus.STALLED,
        CompletionStatus.NO_WORK_DONE,
        CompletionStatus.TIMED_OUT,
    ):
        return base_status

    structured_status = parsed.get("status", "").strip().lower()
    blockers = parsed.get("blockers", "").strip()

    if structured_status in _FAILURE_STATUS_TOKENS or blockers:
        return CompletionStatus.NO_WORK_DONE

    return base_status
