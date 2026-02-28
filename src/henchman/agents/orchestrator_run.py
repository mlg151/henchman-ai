"""Run-time helpers for orchestrator execution.

Contains the prepare/finalize logic and async generator helpers
for :meth:`Orchestrator.run` and :meth:`Orchestrator.run_direct`.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from henchman.agents.ledger import TaskLedger
from henchman.core.events import AgentEvent, EventType

from .orchestrator_types import (
    MAX_USER_INPUT_LENGTH,
    CompletionStatus,
)

if TYPE_CHECKING:
    from henchman.core.agent import Agent


def prepare_run(orch: Any, user_input: str) -> None:
    """Initialize state for a new orchestrator run.

    Args:
        orch: The orchestrator instance.
        user_input: The user's input text.
    """
    orch.ledger = TaskLedger(goal=user_input[:MAX_USER_INPUT_LENGTH])
    orch.delegation_runner.ledger = orch.ledger
    orch.metrics.reset_for_run()
    orch.metrics.performance.task_start_time = time.time()


def finalize_run(
    orch: Any,
    agent: Agent,
    role_label: str,
) -> list[AgentEvent]:
    """Calculate metrics and produce final events.

    Args:
        orch: The orchestrator instance.
        agent: The agent that just finished.
        role_label: Label for the agent role (e.g. ``"tech_lead"``).

    Returns:
        List of final events including completion status.
    """
    orch.metrics.performance.task_end_time = time.time()
    orch.metrics.calculate_final_metrics()
    status = orch.execution_controller.assess_completion(agent)
    orch.last_completion_status = status
    events: list[AgentEvent] = []
    if status == CompletionStatus.NO_WORK_DONE:
        events.append(AgentEvent(
            type=EventType.ERROR,
            data="Agent completed without performing any actions.",
            source_agent="orchestrator",
        ))
    events.append(AgentEvent(
        type=EventType.AGENT_COMPLETED,
        data={"agent": role_label, "status": status.value},
        source_agent="orchestrator",
    ))
    return events
