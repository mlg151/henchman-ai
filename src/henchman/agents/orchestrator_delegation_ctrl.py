"""Delegation controller for the orchestrator module.

Manages the execution of delegation tool calls and result processing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from henchman.core.events import AgentEvent, EventType

from .orchestrator_components import OrchestratorComponent
from .orchestrator_events import (
    create_delegation_event,
    create_tool_result_event,
    extract_brief_fields,
    update_ledger,
)
from .orchestrator_types import (
    DELEGATE_TASK_TOOL,
    DelegationExecutionParams,
    DelegationParams,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from henchman.core.agent import Agent
    from henchman.providers.base import ToolCall


# ---------------------------------------------------------------------------
# Per-delegation state accumulator
# ---------------------------------------------------------------------------


@dataclass
class _StreamState:
    """Mutable accumulator for a single delegation's streaming results.

    Using a per-call dataclass instead of instance fields makes
    DelegationController safe for concurrent / re-entrant use.

    Attributes:
        result_content: The summary text from the AGENT_COMPLETED event.
        had_error: True if any ERROR event was emitted during the delegation.
        status: The status string from the AGENT_COMPLETED event.
    """

    result_content: str = field(default="")
    had_error: bool = field(default=False)
    status: str = field(default="")


# ---------------------------------------------------------------------------
# Delegation controller — manages delegation tool execution
# ---------------------------------------------------------------------------


class DelegationController(OrchestratorComponent):
    """Manages delegation tool execution and result processing."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute_delegation_tool(
        self: DelegationController,
        agent: Agent,
        tool_call: ToolCall,
        depth: int,
    ) -> AsyncIterator[AgentEvent]:
        """Execute a delegation tool call.

        Records metrics, creates a ledger entry, then streams the
        delegated agent run back to the caller.

        Args:
            agent: The agent that initiated the delegation.
            tool_call: The tool call containing delegation parameters.
            depth: The current delegation depth (for recursion tracking).

        Yields:
            AgentEvent: Stream of events from the delegated agent execution.
        """
        tc_args = tool_call.arguments
        target = tc_args.get("agent", "")
        task = tc_args.get("task", "")

        self.metrics.delegation_count += 1
        if target in self.metrics.delegation_by_type:
            self.metrics.delegation_by_type[target] += 1
        self.metrics.update_tool_metrics(
            DELEGATE_TASK_TOOL,
            tc_args,
            success=True,
        )

        ledger = self.orchestrator.ledger
        ledger_record = ledger.add_delegation(agent=target, task=task) if ledger else None

        yield create_delegation_event(agent, target, task)

        params = DelegationExecutionParams(
            target=target,
            task=task,
            depth=depth,
            tool_call=tool_call,
            agent=agent,
            ledger_record=ledger_record,
        )
        async for event in self._run_delegation(params):
            yield event

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_delegation(
        self: DelegationController,
        params: DelegationExecutionParams,
    ) -> AsyncIterator[AgentEvent]:
        """Execute delegation and yield result event.

        Args:
            params: Execution parameters for this delegation.

        Yields:
            AgentEvent: Events from the delegated agent, followed by a
                tool-result event once the delegation completes.
        """
        max_retries = self.orchestrator.settings.agents.max_delegation_retries
        final_state = _StreamState()

        target = params.target
        task = params.task
        agent = params.agent
        tool_call = params.tool_call

        for attempt in range(max_retries + 1):
            state = _StreamState()
            async for sub_event in self._stream_delegation(params, state):
                yield sub_event

            result = state.result_content or "Delegation completed (no output)."
            if state.status == "no_work_done":
                result = (
                    f"\u26a0\ufe0f Agent {target} ended without "
                    f"making any tool calls.\n\n{result}"
                )

            # Update ledger now so _inject_failure_context can see it on retry
            update_ledger(
                self.orchestrator.ledger,
                params.ledger_record,
                result,
                had_error=state.had_error,
            )
            final_state = state

            if not state.had_error or attempt >= max_retries:
                break

            # Create a fresh ledger record for the next attempt
            ledger = self.orchestrator.ledger
            if ledger:
                params.ledger_record = ledger.add_delegation(
                    agent=target, task=task
                )

        final_result = final_state.result_content or "Delegation completed (no output)."
        if final_state.status == "no_work_done":
            final_result = (
                f"\u26a0\ufe0f Agent {target} ended without "
                f"making any tool calls.\n\n{final_result}"
            )

        submitted = final_result
        ledger = self.orchestrator.ledger
        if ledger:
            submitted = f"{final_result}\n\n{ledger.render()}"

        agent.submit_tool_result(tool_call.id, submitted)
        yield create_tool_result_event(agent, tool_call, final_result)

    async def _stream_delegation(
        self: DelegationController,
        params: DelegationExecutionParams,
        state: _StreamState,
    ) -> AsyncIterator[AgentEvent]:
        """Stream events from the delegation runner into *state*.

        Args:
            params: Execution parameters for this delegation.
            state: Mutable accumulator that captures completion data
                and error flags as events arrive.

        Yields:
            AgentEvent: Raw events from the specialist agent.
        """
        brief = extract_brief_fields(params.tool_call.arguments)
        delegation_params = DelegationParams(
            target_role=params.target,
            task=params.task,
            brief=brief,
            depth=params.depth + 1,
        )

        runner = self.orchestrator.delegation_runner
        async for sub_event in runner.run_delegation(delegation_params):
            if sub_event.type == EventType.AGENT_COMPLETED:
                data = sub_event.data
                state.result_content = data.get("summary", "Completed.")
                state.status = data.get("status", "completed")
            if sub_event.type == EventType.ERROR:
                state.had_error = True
            yield sub_event
