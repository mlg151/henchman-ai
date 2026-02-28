"""Tool execution controller for the orchestrator module.

Handles dispatching tool calls to either the delegation controller
or the regular tool execution path.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from henchman.core.events import AgentEvent, EventType

from .orchestrator_components import OrchestratorComponent, ToolMetricsController
from .orchestrator_delegation_ctrl import DelegationController
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
                    agent, tool_call, depth,
                ):
                    yield event
            else:
                async for event in _execute_regular_tool(
                    agent, tool_call, tool_errors, self._metrics_controller,
                ):
                    yield event


async def _execute_regular_tool(
    agent: Agent,
    tool_call: ToolCall,
    tool_errors: list[str],
    metrics: ToolMetricsController,
) -> AsyncIterator[AgentEvent]:
    """Execute a regular (non-delegation) tool call."""
    result = await agent.tool_registry.execute(
        tool_call.name, tool_call.arguments,
    )
    tc_name = tool_call.name
    tc_id = tool_call.id

    agent.submit_tool_result(tc_id, result.content or "")

    if not result.success:
        metrics.track_tool_error(tool_errors, tc_name, result.content)

    metrics.update_tool_metrics(
        tc_name, tool_call.arguments, success=result.success,
    )

    yield AgentEvent(
        type=EventType.TOOL_CALL_RESULT,
        data={
            "tool_call_id": tc_id,
            "tool_name": tc_name,
            "result": (result.content or "")[:RESULT_PREVIEW_LENGTH],
            "success": result.success,
        },
        source_agent=agent.identity.id if agent.identity else None,
    )
