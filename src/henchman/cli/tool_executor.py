"""Tool executor for REPL.

This module handles tool calls, confirmations, and results.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from rich.markup import escape as _escape

from henchman.cli.stream_event_handlers import (
    MAX_RESULT_PREVIEW_LENGTH,
    StreamState,
    build_confirmation_message,
    dispatch_event,
    handle_post_stream_processing,
)
from henchman.core.events import EventType
from henchman.providers.base import ToolCall

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from rich.status import Status

    from henchman.cli.input import KeyMonitor
    from henchman.cli.output_handler import OutputHandler
    from henchman.cli.tool_manager import ToolManager
    from henchman.core.agent import Agent
    from henchman.core.events import AgentEvent
    from henchman.providers.base import ModelProvider
    from henchman.tools.base import ConfirmationRequest
    from henchman.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

DEFAULT_BASE_ITERATIONS = 25
DEFAULT_MAX_TOOL_CALLS_PER_TURN = 100


class ToolExecutor:
    """Handles tool execution for the REPL.

    Responsibilities:
    - Execute tool calls
    - Handle tool confirmations
    - Process tool results
    - Manage tool execution flow
    """

    def __init__(
        self: ToolExecutor,
        output_handler: OutputHandler,
        tool_manager: ToolManager,
        provider: ModelProvider,
        base_tool_iterations: int = DEFAULT_BASE_ITERATIONS,
        max_tool_calls_per_turn: int = DEFAULT_MAX_TOOL_CALLS_PER_TURN,
    ) -> None:
        """Initialise the tool executor.

        Args:
            output_handler: Output handler for displaying results.
            tool_manager: Tool manager for tool execution.
            provider: Model provider for agent context.
            base_tool_iterations: Base limit for tool iterations per turn.
            max_tool_calls_per_turn: Maximum tool calls allowed per turn.
        """
        self.output_handler = output_handler
        self.tool_manager = tool_manager
        self.provider = provider
        self.base_tool_iterations = base_tool_iterations
        self.max_tool_calls_per_turn = max_tool_calls_per_turn
        self.current_monitor: KeyMonitor | None = None

    def _should_stop_due_to_limits(self: ToolExecutor, agent: Agent) -> bool:
        """Return True when iteration or tool-call limits have been reached."""
        if getattr(agent, "unlimited_mode", False):
            return False

        turn = agent.turn
        adaptive_limit = turn.get_adaptive_limit(self.base_tool_iterations)

        if turn.is_at_limit(self.base_tool_iterations):
            self.output_handler.error(
                f"Reached iteration limit ({adaptive_limit}). "
                "Stopping to prevent infinite loop. Use /unlimited to bypass.",
            )
            return True

        if turn.tool_count >= self.max_tool_calls_per_turn:
            self.output_handler.error(
                f"Reached tool call limit ({self.max_tool_calls_per_turn}). "
                "Stopping to prevent runaway execution.",
            )
            return True

        spin_detection_threshold = 2
        if turn.is_spinning() and turn.iteration > spin_detection_threshold:
            self.output_handler.warning(
                "⚠ Possible loop detected: same tool calls or results repeating. "
                f"Iteration {turn.iteration}/{adaptive_limit}",
            )

        return False

    async def _execute_and_record_tool_call(
        self: ToolExecutor,
        tc: ToolCall,
        agent: Agent,
        responded_ids: set[str],
        *,
        announce_request: bool = True,
    ) -> None:
        """Execute *tc*, record the result, and mark it as responded."""
        tc_id, tc_name, tc_args = tc.id, tc.name, tc.arguments
        if announce_request:
            self.output_handler.muted(
                f"\n\\[tool] {_escape(tc_name)}({_escape(str(tc_args))})",
            )
        result = await agent.tool_registry.execute(tc_name, tc_args)
        responded_ids.add(tc_id)
        agent.turn.record_tool_call(
            tool_call_id=tc_id,
            tool_name=tc_name,
            arguments=tc_args,
            result=result,
        )
        agent.submit_tool_result(tc_id, result.content)
        self.output_handler.session_manager.record_tool_result(tc_id, result.content)
        if result.success:
            self.output_handler.muted(
                f"\\[result] {_escape(result.content[:MAX_RESULT_PREVIEW_LENGTH])}...",
            )
        else:
            self.output_handler.error(f"\\[error] {_escape(result.error or '')}")

    def _split_tools_by_confirmation_requirement(
        self: ToolExecutor,
        tool_calls: list[ToolCall],
        registry: ToolRegistry,
    ) -> tuple[list[ToolCall], list[ToolCall]]:
        """Split *tool_calls* into (parallel, sequential) based on confirmation needs."""
        to_parallel: list[ToolCall] = []
        to_sequential: list[ToolCall] = []
        for tc in tool_calls:
            tc_name, tc_args = tc.name, tc.arguments
            tool = registry.get(tc_name)
            if tool and (
                registry.is_auto_approved(tc_name)
                or tool.needs_confirmation(tc_args) is None
            ):
                to_parallel.append(tc)
            else:
                to_sequential.append(tc)
        return to_parallel, to_sequential

    def _ensure_all_tool_calls_have_response(
        self: ToolExecutor,
        tool_calls: list[ToolCall],
        responded_ids: set[str],
        agent: Agent,
    ) -> None:
        """Submit a cancellation result for any tool call that has no response yet."""
        for tool_call in tool_calls:
            tc_id = tool_call.id
            if tc_id not in responded_ids:
                cancel_msg = "Tool execution was interrupted or cancelled."
                agent.submit_tool_result(tc_id, cancel_msg)
                self.output_handler.session_manager.record_tool_result(
                    tc_id,
                    cancel_msg,
                )

    async def process_agent_stream(
        self: ToolExecutor,
        event_stream: AsyncIterator[AgentEvent],
        agent: Agent,
        content_collector: list[str] | None = None,
        status_obj: Status | None = None,
    ) -> None:
        """Process an agent event stream, handling tool calls properly.

        Collects ALL tool calls from a single response before executing them,
        as required by the OpenAI API.

        Args:
            event_stream: Async iterator of agent events.
            agent: The agent for turn tracking and result submission.
            content_collector: Optional list to collect content for session.
            status_obj: Accepted for API compatibility; spinner was removed.

        Returns:
            None
        """
        if self._should_stop_due_to_limits(agent):
            return

        state = StreamState()
        primary_error: BaseException | None = None
        try:
            async for event in event_stream:
                dispatch_event(
                    self.output_handler,
                    event,
                    state,
                    agent,
                    content_collector,
                )
                if event.type == EventType.ERROR and state.is_own_event:
                    state.interrupted = True
                    break
        except BaseException as exc:
            primary_error = exc
            state.interrupted = True
            await handle_post_stream_processing(
                self.output_handler, state, agent, content_collector, self.execute_tool_calls,
            )
            raise
        finally:
            close = getattr(event_stream, "aclose", None)
            if close is not None:
                try:
                    await close()
                except Exception:
                    if primary_error is None and not state.interrupted:
                        raise
                    logger.warning("Agent stream cleanup failed after interruption", exc_info=True)

        await handle_post_stream_processing(
            self.output_handler,
            state,
            agent,
            content_collector,
            self.execute_tool_calls,
        )

    async def _run_sequential_tool_calls(
        self: ToolExecutor,
        tool_calls: list[ToolCall],
        agent: Agent,
        responded_ids: set[str],
        announced_tool_call_ids: set[str] | None = None,
    ) -> None:
        """Execute *tool_calls* one-by-one, suspending the key monitor."""
        announced_ids = announced_tool_call_ids or set()
        if self.current_monitor:
            await self.current_monitor.suspend()
        try:
            for tc in tool_calls:
                await self._execute_and_record_tool_call(
                    tc,
                    agent,
                    responded_ids,
                    announce_request=tc.id not in announced_ids,
                )
        finally:
            if self.current_monitor:
                self.current_monitor.resume()

    async def execute_tool_calls(
        self: ToolExecutor,
        tool_calls: list[ToolCall],
        agent: Agent,
        content_collector: list[str] | None = None,
        *,
        announced_tool_call_ids: set[str] | None = None,
    ) -> None:
        """Execute *tool_calls* and continue the agent loop.

        Args:
            tool_calls: List of tool calls to execute.
            agent: The agent for turn tracking and result submission.
            content_collector: Optional list to collect content for session.
            announced_tool_call_ids: Optional set of tool call IDs that have already
                been announced to the user. Tool calls with IDs in this set will not
                show the "[tool]" announcement prefix when executed.

        Returns:
            None
        """
        valid_tool_calls = [tc for tc in tool_calls if isinstance(tc, ToolCall)]
        if not valid_tool_calls:
            return

        announced_ids = announced_tool_call_ids or set()
        agent.turn.increment_iteration()
        responded_ids: set[str] = set()
        to_parallel, to_sequential = self._split_tools_by_confirmation_requirement(
            valid_tool_calls, agent.tool_registry,
        )
        try:
            if to_parallel:
                results = await asyncio.gather(
                    *[
                        self._execute_and_record_tool_call(
                            tc,
                            agent,
                            responded_ids,
                            announce_request=tc.id not in announced_ids,
                        )
                        for tc in to_parallel
                    ],
                    return_exceptions=True,
                )
                # Log any exceptions from individual parallel tool calls
                for tc, result in zip(to_parallel, results, strict=True):
                    if isinstance(result, BaseException):
                        logger.warning(
                            "Parallel tool call %s (%s) failed: %s",
                            tc.id,
                            tc.name,
                            result,
                        )
            if to_sequential:
                await self._run_sequential_tool_calls(
                    to_sequential,
                    agent,
                    responded_ids,
                    announced_ids,
                )
        finally:
            self._ensure_all_tool_calls_have_response(
                valid_tool_calls,
                responded_ids,
                agent,
            )

        self.output_handler.show_turn_status(agent, self.base_tool_iterations)
        self.output_handler.print_newline()
        await self.process_agent_stream(
            agent.continue_with_tool_results(),
            agent,
            content_collector,
        )

    async def handle_confirmation(
        self: ToolExecutor,
        request: ConfirmationRequest,
    ) -> bool:
        """Handle a tool confirmation request interactively.

        Args:
            request: The confirmation request data.

        Returns:
            True if approved, False otherwise.
        """
        msg = build_confirmation_message(request)
        return await self.output_handler.renderer.confirm_tool_execution(msg)
