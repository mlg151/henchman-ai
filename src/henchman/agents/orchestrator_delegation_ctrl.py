"""Delegation controller for the orchestrator module.

Manages the execution of delegation tool calls and result processing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from henchman.core.events import AgentEvent, EventType

from .orchestrator_components import OrchestratorComponent
from .orchestrator_types import (
    DELEGATE_TASK_TOOL,
    RESULT_PREVIEW_LENGTH,
    DelegationExecutionParams,
    DelegationParams,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from henchman.core.agent import Agent
    from henchman.providers.base import ToolCall


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

    async def execute_delegation_tool(
        self: DelegationController,
        agent: Agent,
        tool_call: ToolCall,
        depth: int,
    ) -> AsyncIterator[AgentEvent]:
        """Execute a delegation tool call."""
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

        yield _create_delegation_event(agent, target, task)

        params = DelegationExecutionParams(
            target=target, task=task, depth=depth,
            tool_call=tool_call, agent=agent, ledger_record=ledger_record,
        )
        async for event in self._run_delegation(params):
            yield event

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

        _update_ledger(
            self.orchestrator.ledger, params.ledger_record,
            result, had_error=self._had_error,
        )

        submitted = result
        ledger = self.orchestrator.ledger
        if ledger:
            submitted = f"{result}\n\n{ledger.render()}"

        params.agent.submit_tool_result(params.tool_call.id, submitted)
        yield _create_tool_result_event(params.agent, params.tool_call, result)

    async def _stream_delegation(
        self: DelegationController,
        params: DelegationExecutionParams,
    ) -> AsyncIterator[AgentEvent]:
        """Stream events from the delegation runner."""
        brief = _extract_brief_fields(params.tool_call.arguments)
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


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

_BRIEF_FIELDS = (
    "done_when", "context", "files",
    "background", "requirements", "depends_on",
)


def _extract_brief_fields(arguments: dict[str, Any]) -> dict[str, Any]:
    """Extract delegation brief fields from tool arguments."""
    return {f: arguments.get(f) for f in _BRIEF_FIELDS}


def _create_delegation_event(
    agent: Agent,
    target: str,
    task: str,
) -> AgentEvent:
    """Create a delegation event."""
    return AgentEvent(
        type=EventType.AGENT_DELEGATED,
        data={
            "from": agent.identity.id if agent.identity else "unknown",
            "to": target,
            "task": task,
        },
        source_agent="orchestrator",
    )


def _create_tool_result_event(
    agent: Agent,
    tool_call: ToolCall,
    result_content: str,
) -> AgentEvent:
    """Create a tool result event."""
    return AgentEvent(
        type=EventType.TOOL_CALL_RESULT,
        data={
            "tool_call_id": tool_call.id,
            "tool_name": tool_call.name,
            "result": (result_content or "")[:RESULT_PREVIEW_LENGTH],
            "success": True,
        },
        source_agent=agent.identity.id if agent.identity else None,
    )


def _update_ledger(
    ledger: Any,
    record: Any,
    result: str,
    *,
    had_error: bool,
) -> None:
    """Update ledger with delegation outcome."""
    if not ledger or not record:
        return
    if had_error:
        ledger.fail_delegation(record, result)
    else:
        ledger.complete_delegation(record, result)
