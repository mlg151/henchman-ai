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


def assess_agent_completion(orchestrator: Any, agent: Agent) -> CompletionStatus:
    """Assess whether an agent performed meaningful work.

    Args:
        orchestrator: The orchestrator instance managing the agent.
        agent: The agent to assess completion status for.

    Returns:
        CompletionStatus: The completion status of the agent (STALLED, NO_WORK_DONE, or COMPLETED).
    """
    tool_calls = getattr(orchestrator, "_last_loop_tool_call_count", 0)

    # Check for stall failure in new StallDetector or legacy attribute.
    # We use 'is True' to avoid MagicMock truthiness in tests.
    stalled = False
    stall_detector = getattr(agent, "_stall", None)
    if stall_detector is not None and getattr(stall_detector, "failure", False) is True:
        stalled = True

    # Fallback to legacy attribute if not already found to be stalled
    if not stalled and getattr(agent, "_stall_failure", False) is True:
        stalled = True

    if stalled:
        return CompletionStatus.STALLED
    if tool_calls == 0:
        return CompletionStatus.NO_WORK_DONE
    return CompletionStatus.COMPLETED
