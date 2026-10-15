"""Tool execution controller for the orchestrator module.

Handles dispatching tool calls to either the delegation controller
or the regular tool execution path.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from henchman.core.events import AgentEvent, EventType
from henchman.tools.base import ToolResult

from .orchestrator_components import OrchestratorComponent
from .orchestrator_delegation_ctrl import DelegationController
from .orchestrator_execution import closing_event_stream
from .orchestrator_metrics_ctrl import ToolMetricsController
from .orchestrator_types import DELEGATE_TASK_TOOL, RESULT_PREVIEW_LENGTH

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from henchman.core.agent import Agent
    from henchman.providers.base import ToolCall


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
        *,
        success: bool = True,
    ) -> None:
        """Delegate to metrics controller for backward compat.

        Args:
            tool_name: Name of the tool that was called.
            args: Dictionary of arguments passed to the tool.
            success: Whether the tool call was successful. Defaults to True.

        Returns:
            None: This method delegates to the metrics controller and returns nothing.
        """
        self._metrics_controller.update_tool_metrics(
            tool_name,
            args,
            success=success,
        )

    async def process_pending_tool_calls(
        self,
        agent: Agent,
        pending_tool_calls: list[ToolCall],
        depth: int,
        tool_errors: list[str],
    ) -> AsyncIterator[AgentEvent]:
        """Dispatch within the authenticated calling conversation's identity."""
        from henchman.agents.subagents import subagent_actor

        actor = agent.identity.id if agent.identity is not None else "tech_lead"
        with subagent_actor(actor):
            async with closing_event_stream(
                self._process_pending_tool_calls(agent, pending_tool_calls, depth, tool_errors)
            ) as events:
                async for event in events:
                    yield event

    async def _process_pending_tool_calls(
        self: ToolController,
        agent: Agent,
        pending_tool_calls: list[ToolCall],
        depth: int,
        tool_errors: list[str],
    ) -> AsyncIterator[AgentEvent]:
        """Process all pending tool calls from an agent.

        Args:
            agent: The agent making the tool calls.
            pending_tool_calls: List of tool calls to process.
            depth: Current recursion depth for delegation tracking.
            tool_errors: List to accumulate tool error messages.

        Yields:
            AgentEvent: Events generated during tool execution.
        """
        for tool_call in pending_tool_calls:
            if tool_call.name == DELEGATE_TASK_TOOL:
                authorized = await agent.tool_registry.authorize(
                    tool_call.name, tool_call.arguments,
                )
                if isinstance(authorized, ToolResult):
                    yield _report_tool_result(
                        agent, tool_call, authorized, tool_errors, self._metrics_controller,
                    )
                    continue
                stream = self._delegation_controller.execute_delegation_tool(
                    agent,
                    tool_call,
                    depth,
                )
            else:
                stream = _execute_regular_tool(
                    agent,
                    tool_call,
                    tool_errors,
                    self._metrics_controller,
                )
            async with closing_event_stream(stream) as events:
                async for event in events:
                    yield event


async def _execute_regular_tool(
    agent: Agent,
    tool_call: ToolCall,
    tool_errors: list[str],
    metrics: ToolMetricsController,
) -> AsyncIterator[AgentEvent]:
    """Execute a regular (non-delegation) tool call."""
    result = await agent.tool_registry.execute(
        tool_call.name,
        tool_call.arguments,
    )
    yield _report_tool_result(agent, tool_call, result, tool_errors, metrics)


def _report_tool_result(
    agent: Agent,
    tool_call: ToolCall,
    result: ToolResult,
    tool_errors: list[str],
    metrics: ToolMetricsController,
) -> AgentEvent:
    """Record execution or authorization outcomes with the same call identity."""
    tc_name = tool_call.name
    tc_id = tool_call.id

    agent.submit_tool_result(tc_id, result.content or "")

    if not result.success:
        metrics.track_tool_error(tool_errors, tc_name, result.content)

    metrics.update_tool_metrics(
        tc_name,
        tool_call.arguments,
        success=result.success,
    )

    return AgentEvent(
        type=EventType.TOOL_CALL_RESULT,
        data={
            "tool_call_id": tc_id,
            "tool_name": tc_name,
            "result": result.content or "",
            "preview": (result.content or "")[:RESULT_PREVIEW_LENGTH],
            "success": result.success,
        },
        source_agent=agent.identity.id if agent.identity else None,
    )
