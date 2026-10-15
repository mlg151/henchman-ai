"""Validation helpers for the orchestrator module.

Contains agent behavior validation logic extracted from components.
"""

from __future__ import annotations

from typing import Any

from henchman.core.agent_streaming import record_message
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import Message

_MIN_LINES = 3
_MAX_SCORE = 100
_SCORE_INC = 5


# ---------------------------------------------------------------------------
# Thinking-pattern validation
# ---------------------------------------------------------------------------


def should_check_thinking(orchestrator: Any, agent: Any) -> bool:
    """Determine if thinking pattern should be checked for this agent.

    Args:
        orchestrator: The orchestrator instance.
        agent: The agent to check.

    Returns:
        bool: True if thinking pattern should be checked for this agent.
    """
    return (
        agent is orchestrator.tech_lead
        and bool(agent.messages)
        and agent.messages[-1].role == "assistant"
    )


def handle_valid_thinking(metrics: Any, content: str) -> None:
    """Handle valid thinking pattern and update metrics.

    Args:
        metrics: The metrics object to update.
        content: The thinking content to analyze.

    Returns:
        None: This function updates metrics in-place and returns nothing.
    """
    metrics.thinking_pattern_usage += 1
    numbered = [
        ln
        for ln in content.strip().split("\n")
        if ln.strip().startswith(("1.", "2.", "3.", "4.", "5."))
    ]
    if len(numbered) >= _MIN_LINES:
        metrics.thinking_quality_score = min(
            _MAX_SCORE,
            metrics.thinking_quality_score + _SCORE_INC,
        )



# ---------------------------------------------------------------------------
# Stall detection
# ---------------------------------------------------------------------------


def check_stall_failure(orchestrator: Any, agent: Any) -> AgentEvent | None:
    """Check if agent has stalled and report failure.

    Args:
        orchestrator: The orchestrator instance.
        agent: The agent to check for stall failure.

    Returns:
        AgentEvent | None: An error event if stall failure detected, None otherwise.
    """
    _stall = getattr(agent, "_stall", None)
    if agent is orchestrator.tech_lead or not getattr(_stall, "failure", False):
        return None
    role_label = agent.identity.role if agent.identity else "agent"
    nudges = getattr(_stall, "nudge_count", 0)
    fail_msg = (
        f"STALL FAILURE: {role_label} announced intent but never used "
        f"tools after {nudges} nudges. The task was NOT completed."
    )
    record_message(
        agent.messages, Message(role="assistant", content=fail_msg),
        getattr(agent, "current_turn_messages", None),
    )
    return AgentEvent(type=EventType.ERROR, data=fail_msg, source_agent=role_label)
