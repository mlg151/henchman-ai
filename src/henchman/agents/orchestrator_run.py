"""Run-time helpers for orchestrator execution.

Contains the prepare/finalize logic and async generator helpers
for :meth:`Orchestrator.run` and :meth:`Orchestrator.run_direct`.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from henchman.agents.ledger import TaskLedger
from henchman.core.events import AgentEvent, EventType
from henchman.core.run_accounting import budget_snapshot_payload
from henchman.providers.runtime_budget import RunBudgetScope

from .orchestrator_anchoring import completion_evidence
from .orchestrator_types import (
    CompletionStatus,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator, Iterator

    from henchman.agents.orchestrator import Orchestrator
    from henchman.core.agent import Agent


async def primary_actor_events(stream: AsyncIterator[AgentEvent]) -> AsyncGenerator[AgentEvent, None]:
    """Bind actor identity while producing/closing events, never in consumers."""
    from henchman.agents.subagents import subagent_actor

    try:
        while True:
            with subagent_actor("tech_lead"):
                try:
                    event = await anext(stream)
                except StopAsyncIteration:
                    return
            yield event
    finally:
        with subagent_actor("tech_lead"):
            close = getattr(stream, "aclose", None)
            if close is not None:
                await close()


@contextmanager
def claim_public_run(orch: Orchestrator) -> Iterator[None]:
    """Admit one public run before changing shared ledger or metrics state."""
    if orch._public_run_active:
        raise ValueError("An orchestrator run is already active.")
    orch._public_run_active = True
    try:
        yield
    finally:
        orch._public_run_active = False


def prepare_run(orch: Any, user_input: str) -> None:
    """Initialize state for a new orchestrator run.

    Args:
        orch: The orchestrator instance.
        user_input: The user's input text.

    Returns:
        None: This function initializes orchestrator state but returns nothing.
    """
    orch.ledger = TaskLedger(goal=user_input)
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
        events.append(
            AgentEvent(
                type=EventType.ERROR,
                data="Agent completed without performing any actions.",
                source_agent="orchestrator",
            ),
        )
    events.append(
        AgentEvent(
            type=EventType.AGENT_COMPLETED,
            data={"agent": role_label, "scope": "run", "status": status.value,
                  **completion_evidence(agent),
                  **({"budget": budget_snapshot_payload(orch.last_budget_scope.ledger.snapshot())}
                     if isinstance(getattr(orch, "last_budget_scope", None), RunBudgetScope) else {})},
            source_agent="orchestrator",
        ),
    )
    return events
