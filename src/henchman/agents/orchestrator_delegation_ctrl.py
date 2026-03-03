"""Delegation controller for the orchestrator module.

Manages the execution of delegation tool calls and result processing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
# Delegation controller — manages delegation tool execution
# ---------------------------------------------------------------------------


class DelegationController(OrchestratorComponent):
    """Manages delegation tool execution and result processing."""

    def __init__(self: DelegationController, orchestrator: Any) -> None:
        """Initialize the DelegationController.

        Args:
            orchestrator: The parent orchestrator instance.
        """
        super().__init__(orchestrator)
        self._result_content: str = ""
        self._had_error: bool = False
        self._status: str = ""

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
            DELEGATE_TASK_TOOL, tc_args, success=True,
        )

        ledger = self.orchestrator.ledger
        ledger_record = (
            ledger.add_delegation(agent=target, task=task) if ledger else None
        )

        yield create_delegation_event(agent, target, task)

        params = DelegationExecutionParams(
            target=target, task=task, depth=depth,
            tool_call=tool_call, agent=agent, ledger_record=ledger_record,
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
        """Execute delegation and yield result event."""
        async for sub_event in self._stream_delegation(params):
            yield sub_event

        result = self._result_content or "Delegation completed (no output)."
        if self._status == "no_work_done":
            result = (
                f"\u26a0\ufe0f Agent {params.target} ended without "
                f"making any tool calls.\n\n{result}"
            )

        update_ledger(
            self.orchestrator.ledger, params.ledger_record,
            result, had_error=self._had_error,
        )

        submitted = result
        ledger = self.orchestrator.ledger
        if ledger:
            submitted = f"{result}\n\n{ledger.render()}"

        params.agent.submit_tool_result(params.tool_call.id, submitted)
        yield create_tool_result_event(params.agent, params.tool_call, result)

    async def _stream_delegation(
        self: DelegationController,
        params: DelegationExecutionParams,
    ) -> AsyncIterator[AgentEvent]:
        """Stream events from the delegation runner."""
        brief = extract_brief_fields(params.tool_call.arguments)
        delegation_params = DelegationParams(
            target_role=params.target,
            task=params.task,
            brief=brief,
            depth=params.depth + 1,
        )
        self._result_content = ""
        self._had_error = False
        self._status = ""

        runner = self.orchestrator.delegation_runner
        async for sub_event in runner.run_delegation(delegation_params):
            if sub_event.type == EventType.AGENT_COMPLETED:
                data = sub_event.data
                self._result_content = data.get("summary", "Completed.")
                self._status = data.get("status", "completed")
            if sub_event.type == EventType.ERROR:
                self._had_error = True
            yield sub_event
