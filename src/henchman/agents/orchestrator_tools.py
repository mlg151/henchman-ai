"""Tool execution controllers for the orchestrator.

Handles delegation tool calls and regular tool call processing.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from henchman.core.events import AgentEvent, EventType

from .orchestrator_components import OrchestratorComponent, ToolMetricsController
from .orchestrator_types import (
    DELEGATE_TASK_TOOL,
    RESULT_PREVIEW_LENGTH,
    DelegationExecutionParams,
    DelegationParams,
)

if TYPE_CHECKING:
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
        self._delegation_result_content: str = ""
        self._delegation_had_error: bool = False
        self._delegation_status: str = ""

    async def execute_delegation_tool(
        self: DelegationController,
        agent: Agent,
        tool_call: ToolCall,
        depth: int,
        tool_errors: list[str],
    ) -> AsyncIterator[AgentEvent]:
        """Execute a delegation tool call."""
        tc_args = tool_call.arguments
        target = tc_args.get("agent", "")
        task = tc_args.get("task", "")

        # Update delegation metrics
        self.metrics.delegation_count += 1
        if target in self.metrics.delegation_by_type:
            self.metrics.delegation_by_type[target] += 1

        # Update tool metrics
        self.metrics.update_tool_metrics(
            DELEGATE_TASK_TOOL, tc_args, True,
        )

        # Register delegation in ledger
        ledger_record = self._register_delegation_in_ledger(target, task)

        yield self._create_delegation_event(agent, target, task)

        # Execute delegation flow
        params = DelegationExecutionParams(
            target=target,
            task=task,
            depth=depth,
            tool_call=tool_call,
            agent=agent,
            ledger_record=ledger_record,
        )
        async for event in self._execute_delegation_flow(params):
            yield event

    async def _execute_delegation_flow(
        self: DelegationController,
        params: DelegationExecutionParams,
    ) -> AsyncIterator[AgentEvent]:
        """Execute the delegation flow and yield events.

        This handles the actual delegation execution, result collection,
        and final tool result event.
        """
        agent = params.agent
        tool_call = params.tool_call
        ledger_record = params.ledger_record

        # Execute delegation and collect results
        async for sub_event in self._execute_delegation(params):
            yield sub_event

        result_content, had_error, status = self._extract_delegation_results()

        # Process delegation results
        result_content = _process_delegation_result_content(
            result_content, status, params.target,
        )

        # Update ledger and submit tool result
        self._process_delegation_result(
            agent, tool_call, result_content, had_error, ledger_record,
        )

        # Yield tool result event
        yield _create_tool_result_event(
            agent, tool_call, result_content, success=True,
        )

    async def _execute_delegation(
        self: DelegationController,
        params: DelegationExecutionParams,
    ) -> AsyncIterator[AgentEvent]:
        """Execute delegation and yield events.

        Args:
            params: Delegation execution parameters.

        Yields:
            Agent events from the delegation execution.
        """
        delegation_brief = _extract_delegation_fields(params.tool_call.arguments)
        delegation_params = DelegationParams(
            target_role=params.target,
            task=params.task,
            brief=delegation_brief,
            depth=params.depth + 1,
        )

        # Track delegation results in instance variables
        self._delegation_result_content = ""
        self._delegation_had_error = False
        self._delegation_status = ""

        # Execute delegation and yield events
        runner = self.orchestrator.delegation_runner  # noqa: SLF001
        async for sub_event in runner.run_delegation(delegation_params):
            if sub_event.type == EventType.AGENT_COMPLETED:
                self._delegation_result_content = sub_event.data.get(
                    "summary", "Completed.",
                )
                self._delegation_status = sub_event.data.get(
                    "status", "completed",
                )
            if sub_event.type == EventType.ERROR:
                self._delegation_had_error = True
            yield sub_event

    def _extract_delegation_results(
        self: DelegationController,
    ) -> tuple[str, bool, str]:
        """Extract delegation results from instance variables.

        Returns:
            Tuple of (result_content, delegation_had_error, delegation_status).
        """
        return (
            self._delegation_result_content,
            self._delegation_had_error,
            self._delegation_status,
        )

    def _register_delegation_in_ledger(
        self: DelegationController,
        target: str,
        task: str,
    ) -> Any | None:
        """Register delegation in ledger if available."""
        ledger = self.orchestrator.ledger
        if ledger:
            return ledger.add_delegation(agent=target, task=task)
        return None

    def _create_delegation_event(
        self: DelegationController,
        agent: Agent,
        target: str,
        task: str,
    ) -> AgentEvent:
        """Create and return a delegation event."""
        return AgentEvent(
            type=EventType.AGENT_DELEGATED,
            data={
                "from": agent.identity.id if agent.identity else "unknown",
                "to": target,
                "task": task,
            },
            source_agent="orchestrator",
        )

    def _process_delegation_result(
        self: DelegationController,
        agent: Agent,
        tool_call: ToolCall,
        result_content: str,
        had_error: bool,
        ledger_record: Any | None,
    ) -> None:
        """Process the result of a delegation."""
        ledger = self.orchestrator.ledger
        # Update ledger with outcome
        if ledger and ledger_record:
            if had_error:
                ledger.fail_delegation(ledger_record, result_content)
            else:
                ledger.complete_delegation(ledger_record, result_content)

        # Append ledger snapshot so Tech Lead can re-orient
        submitted = result_content
        if ledger:
            submitted = f"{result_content}\n\n{ledger.render()}"

        agent.submit_tool_result(tool_call.id, submitted)


def _process_delegation_result_content(
    result_content: str,
    delegation_status: str,
    target: str,
) -> str:
    """Process delegation results and format appropriately.

    Args:
        result_content: Original result content.
        delegation_status: Status of the delegation.
        target: Target agent role.

    Returns:
        Processed result content.
    """
    if not result_content:
        result_content = "Delegation completed (no output)."

    if delegation_status == "no_work_done":
        result_content = (
            f"\u26a0\ufe0f Agent {target} ended without making any tool calls."
            f"\n\n{result_content}"
        )

    return result_content


def _extract_delegation_fields(arguments: dict[str, Any]) -> dict[str, Any]:
    """Extract delegation fields from tool arguments."""
    field_names = [
        "done_when",
        "context",
        "files",
        "background",
        "requirements",
        "depends_on",
    ]
    return {f: arguments.get(f) for f in field_names}


def _create_tool_result_event(
    agent: Agent,
    tool_call: ToolCall,
    result_content: str,
    *,
    success: bool = True,
) -> AgentEvent:
    """Create a tool result event."""
    return AgentEvent(
        type=EventType.TOOL_CALL_RESULT,
        data={
            "tool_call_id": tool_call.id,
            "tool_name": tool_call.name,
            "result": (result_content or "")[:RESULT_PREVIEW_LENGTH],
            "success": success,
        },
        source_agent=agent.identity.id if agent.identity else None,
    )


class ToolController(OrchestratorComponent):
    """Manages tool execution and result processing."""

    def __init__(self: ToolController, orchestrator: Any) -> None:
        """Initialize the ToolController.

        Args:
            orchestrator: The parent orchestrator instance.
        """
        super().__init__(orchestrator)
        self._delegation_controller = DelegationController(orchestrator)
        self._metrics_controller = ToolMetricsController(orchestrator)

    def update_tool_metrics(
        self: ToolController,
        tool_name: str,
        args: dict[str, Any],
        success: bool = True,
    ) -> None:
        """Delegate to metrics controller for backward compat."""
        self._metrics_controller.update_tool_metrics(
            tool_name, args, success=success,
        )

    async def process_pending_tool_calls(
        self: ToolController,
        agent: Agent,
        pending_tool_calls: list[ToolCall],
        depth: int,
        tool_errors: list[str],
    ) -> AsyncIterator[AgentEvent]:
        """Process all pending tool calls from an agent."""
        for tool_call in pending_tool_calls:
            if tool_call.name == DELEGATE_TASK_TOOL:
                async for event in self._delegation_controller.execute_delegation_tool(
                    agent, tool_call, depth, tool_errors,
                ):
                    yield event
            else:
                async for event in self._execute_regular_tool(
                    agent, tool_call, tool_errors,
                ):
                    yield event

    async def _execute_regular_tool(
        self: ToolController,
        agent: Agent,
        tool_call: ToolCall,
        tool_errors: list[str],
    ) -> AsyncIterator[AgentEvent]:
        """Execute a regular (non-delegation) tool call."""
        result = await agent.tool_registry.execute(
            tool_call.name, tool_call.arguments,
        )
        tc_name = tool_call.name
        tc_args = tool_call.arguments

        agent.submit_tool_result(tool_call.id, result.content or "")

        if not result.success:
            self._metrics_controller.track_tool_error(
                tool_errors, tc_name, result.content,
            )

        self._metrics_controller.update_tool_metrics(
            tc_name, tc_args, success=result.success,
        )

        yield AgentEvent(
            type=EventType.TOOL_CALL_RESULT,
            data={
                "tool_call_id": tool_call.id,
                "tool_name": tc_name,
                "result": (result.content or "")[:RESULT_PREVIEW_LENGTH],
                "success": result.success,
            },
            source_agent=agent.identity.id if agent.identity else None,
        )
