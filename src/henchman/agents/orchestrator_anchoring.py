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
    orchestrator: Any, agent: Agent, tool_call_count: int,
) -> None:
    """Inject periodic role anchoring reminder if needed."""
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
    """Assess whether an agent performed meaningful work."""
    tool_calls = getattr(orchestrator, "_last_loop_tool_call_count", 0)
    stalled = getattr(agent, "_stall_failure", False)
    if stalled:
        return CompletionStatus.STALLED
    if tool_calls == 0:
        return CompletionStatus.NO_WORK_DONE
    return CompletionStatus.COMPLETED
