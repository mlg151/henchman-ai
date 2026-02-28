"""Turn enforcement for the orchestrator module.

Handles turn limit warnings and timeouts for specialist agents.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import Message

from .orchestrator_timeout import TimeoutSummaryBuilder
from .orchestrator_types import WRAPUP_WARNING_OFFSET

if TYPE_CHECKING:
    from henchman.core.agent import Agent


@dataclass
class TurnEnforcementParams:
    """Parameters for enforcing turn limits."""

    agent: Agent
    max_turns: int
    tool_call_count: int
    msg_start_index: int
    wrapup_warned: bool

    def enforce_limits(
        self: TurnEnforcementParams,
    ) -> tuple[bool, bool, AgentEvent | None]:
        """Enforce turn limits with warnings and hard stops.

        Returns:
            Tuple of (should_break, new_wrapup_warned, error_event).
        """
        if self.max_turns <= 0:
            return False, self.wrapup_warned, None

        remaining = self.max_turns - self.tool_call_count

        if remaining <= 0:
            return _handle_limit_reached(
                self.agent, self.max_turns,
                self.msg_start_index, self.wrapup_warned,
            )

        if not self.wrapup_warned and remaining <= WRAPUP_WARNING_OFFSET:
            _send_wrapup_warning(self.agent, remaining)
            return False, True, None

        return False, self.wrapup_warned, None


def _handle_limit_reached(
    agent: Agent,
    max_turns: int,
    msg_start_index: int,
    wrapup_warned: bool,  # noqa: FBT001
) -> tuple[bool, bool, AgentEvent]:
    """Handle case when turn limit has been reached."""
    progress = TimeoutSummaryBuilder.build_summary(agent, msg_start_index)
    timeout_msg = (
        "[TURN LIMIT REACHED] You have used all available "
        "turns. Here is a summary of your progress so far:\n\n"
        f"{progress}\n\n"
        "The Tech Lead will decide how to proceed."
    )
    agent.messages.append(Message(role="assistant", content=timeout_msg))

    role_label = agent.identity.role if agent.identity else "agent"
    error_event = AgentEvent(
        type=EventType.ERROR,
        data=f"Turn limit ({max_turns}) reached for {role_label}",
        source_agent="orchestrator",
    )
    return True, wrapup_warned, error_event


def _send_wrapup_warning(agent: Agent, remaining: int) -> None:
    """Send a wrap-up warning to the agent."""
    warn_msg = (
        f"[WRAP-UP WARNING] You have {remaining} tool-call "
        f"turn(s) remaining. Prioritise:\n"
        f"1. Run any final verification (tests, lint).\n"
        f"2. Write a completion report using the "
        f"DELEGATION_SUMMARY_SCHEMA format.\n"
        f"3. List BLOCKERS if you cannot finish in time."
    )
    agent.messages.append(Message(role="user", content=warn_msg))
