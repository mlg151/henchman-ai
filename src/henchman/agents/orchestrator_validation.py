"""Validation helpers for the orchestrator module.

Contains agent behavior validation logic extracted from components.
"""

from __future__ import annotations

from typing import Any

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
    """
    metrics.thinking_pattern_usage += 1
    numbered = [
        ln for ln in content.strip().split("\n")
        if ln.strip().startswith(("1.", "2.", "3.", "4.", "5."))
    ]
    if len(numbered) >= _MIN_LINES:
        metrics.thinking_quality_score = min(
            _MAX_SCORE, metrics.thinking_quality_score + _SCORE_INC,
        )


def handle_missing_thinking(agent: Any) -> AgentEvent:
    """Handle missing thinking pattern by adding reminder.

    Args:
        agent: The agent missing the thinking pattern.

    Returns:
        AgentEvent: An event indicating thinking pattern is required.
    """
    reminder = (
        "\n[Thinking Required] Your response must start with THINKING: "
        "followed by your reasoning process. Please revise."
    )
    agent.messages.append(Message(role="user", content=reminder))
    return AgentEvent(
        type=EventType.THINKING_REQUIRED,
        data="Thinking pattern missing in Tech Lead response",
        source_agent="orchestrator",
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
    agent.messages.append(Message(role="assistant", content=fail_msg))
    return AgentEvent(type=EventType.ERROR, data=fail_msg, source_agent=role_label)
