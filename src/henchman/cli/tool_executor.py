"""Tool executor for REPL.

This module handles tool calls, confirmations, and results.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from henchman.cli.input import KeyMonitor
from henchman.core.agent import Agent
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import ToolCall
from henchman.tools.base import ConfirmationRequest

if TYPE_CHECKING:
    from typing import Any

    from rich.status import Status

    from henchman.cli.output_handler import OutputHandler
    from henchman.cli.tool_manager import ToolManager
    from henchman.providers.base import ModelProvider, ToolCall
    from henchman.tools.base import ConfirmationRequest

# Constants for improved readability and maintainability
MAX_RESULT_PREVIEW_LENGTH = 200
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
        self,
        output_handler: OutputHandler,
        tool_manager: ToolManager,
        provider: ModelProvider,
        base_tool_iterations: int = DEFAULT_BASE_ITERATIONS,
        max_tool_calls_per_turn: int = DEFAULT_MAX_TOOL_CALLS_PER_TURN,
    ) -> None:
        """Initialize the tool executor.

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

    def _should_stop_due_to_limits(self, agent: Agent) -> bool:
        """Check if processing should stop due to iteration or tool call limits.

        Args:
            agent: The agent to check limits for.

        Returns:
            True if processing should stop, False otherwise.
        """
        if getattr(agent, "unlimited_mode", False):
            return False

        turn = agent.turn
        adaptive_limit = turn.get_adaptive_limit(self.base_tool_iterations)

        if turn.is_at_limit(self.base_tool_iterations):
            self.output_handler.error(
                f"Reached iteration limit ({adaptive_limit}). "
                "Stopping to prevent infinite loop. Use /unlimited to bypass."
            )
            return True

        if turn.tool_count >= self.max_tool_calls_per_turn:
            self.output_handler.error(
                f"Reached tool call limit ({self.max_tool_calls_per_turn}). "
                "Stopping to prevent runaway execution."
            )
            return True

        # Warn if spinning
        if turn.is_spinning() and turn.iteration > 2:
            self.output_handler.warning(
                "⚠ Possible loop detected: same tool calls or results repeating. "
                f"Iteration {turn.iteration}/{adaptive_limit}"
            )

        return False

    def _handle_content_event(
        self,
        event: AgentEvent,
        is_own_event: bool,
        content_collector: list[str] | None,
        accumulated_content: list[str],
    ) -> None:
        """Handle a CONTENT event from the agent stream.

        Args:
            event: The content event.
            is_own_event: Whether this event belongs to the current agent.
            content_collector: Optional list to collect content for session.
            accumulated_content: List to accumulate content for session recording.
        """
        # Stream content to console
        self.output_handler.print_agent_content(event.data)
        # Only accumulate content if it belongs to the current agent
        if is_own_event:
            if content_collector is not None and event.data:
                content_collector.append(event.data)
            if event.data:
                accumulated_content.append(event.data)

    def _handle_thought_event(
        self,
        event: AgentEvent,
        is_thinking: bool,
        status_obj: Any | None = None,
    ) -> bool:
        """Handle a THOUGHT event from the agent stream.

        Args:
            event: The thought event.
            is_thinking: Current thinking state.
            status_obj: Optional status object to update (ignored - spinner removed).

        Returns:
            Updated thinking state.
        """
        if not is_thinking:
            # Use parentheses instead of brackets to avoid rich markup issues
            self.output_handler.print_newline()
            self.output_handler.thinking("(thinking) ")
            is_thinking = True

        self.output_handler.thinking(event.data)
        return is_thinking

    def _handle_context_compacted_event(self) -> None:
        """Handle a CONTEXT_COMPACTED event from the agent stream."""
        # Notify user that context was compacted
        self.output_handler.warning(
            "Context compacted: older messages summarized to fit model limits"
        )

    def _handle_tool_call_request_event(
        self,
        event: AgentEvent,
        is_own_event: bool,
        pending_tool_calls: list[ToolCall],
    ) -> None:
        """Handle a TOOL_CALL_REQUEST event from the agent stream.

        Args:
            event: The tool call request event.
            is_own_event: Whether this event belongs to the current agent.
            pending_tool_calls: List to collect tool calls for execution.
        """
        tool_call = event.data
        self.output_handler.muted(f"\n[tool] {tool_call.name}({tool_call.arguments})")

        # Only collect tool calls from the current agent
        if is_own_event:
            pending_tool_calls.append(tool_call)

    def _handle_tool_call_result_event(
        self,
        event: AgentEvent,
        is_own_event: bool,
        pending_tool_calls: list[ToolCall],
        handled_tool_call_ids: set[str],
        accumulated_content: list[str],
        last_agent_id: str | None,
        session_tool_calls_flushed: bool,
    ) -> bool:
        """Handle a TOOL_CALL_RESULT event from the agent stream.

        Args:
            event: The tool call result event.
            is_own_event: Whether this event belongs to the current agent.
            pending_tool_calls: List of pending tool calls.
            handled_tool_call_ids: Set of tool call IDs already handled.
            accumulated_content: List of accumulated content for session.
            last_agent_id: ID of the last agent that sent an event.
            session_tool_calls_flushed: Whether tool calls have been recorded to session.

        Returns:
            Updated session_tool_calls_flushed flag.
        """
        # Orchestrator already executed this tool — mark as handled
        result_data = event.data
        if not isinstance(result_data, dict):
            return session_tool_calls_flushed

        tc_id = result_data.get("tool_call_id", "")
        result_text = result_data.get("result", "")
        success = result_data.get("success", True)

        if success:
            self.output_handler.muted(f"[result] {result_text[:MAX_RESULT_PREVIEW_LENGTH]}...")
        else:
            self.output_handler.error(f"[error] {result_text[:MAX_RESULT_PREVIEW_LENGTH]}")

        # Only record results and flush assistant messages if it's our event
        if is_own_event:
            handled_tool_call_ids.add(tc_id)

            # Record to session: flush assistant tool_calls msg once,
            # then each tool result as it arrives.
            if not session_tool_calls_flushed and pending_tool_calls:
                tool_calls_dicts = [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    for tc in pending_tool_calls
                ]
                self.output_handler.session_manager.record_agent_message(
                    content="".join(accumulated_content) if accumulated_content else None,
                    tool_calls=tool_calls_dicts,
                    agent_id=last_agent_id,
                )
                accumulated_content.clear()
                session_tool_calls_flushed = True

            self.output_handler.session_manager.record_tool_result(tc_id, result_text)

        return session_tool_calls_flushed

    async def _execute_and_record_tool_call(
        self,
        tc: ToolCall,
        agent: Agent,
        responded_ids: set[str],
    ) -> None:
        """Execute a tool call and record the result.

        Args:
            tc: The tool call to execute.
            agent: The agent for turn tracking and result submission.
            responded_ids: Set to track which tool calls have been responded to.
        """
        self.output_handler.muted(f"\n[tool] {tc.name}({tc.arguments})")
        result = await self.tool_manager.registry.execute(tc.name, tc.arguments)

        # Record results
        responded_ids.add(tc.id)
        agent.turn.record_tool_call(
            tool_call_id=tc.id,
            tool_name=tc.name,
            arguments=tc.arguments,
            result=result,
        )
        agent.submit_tool_result(tc.id, result.content)
        self.output_handler.session_manager.record_tool_result(tc.id, result.content)

        # Show result
        if result.success:
            self.output_handler.muted(f"[result] {result.content[:MAX_RESULT_PREVIEW_LENGTH]}...")
        else:
            self.output_handler.error(f"[error] {result.error}")

    def _split_tools_by_confirmation_requirement(
        self, tool_calls: list[ToolCall]
    ) -> tuple[list[ToolCall], list[ToolCall]]:
        """Split tool calls into those that need confirmation and those that don't.

        Args:
            tool_calls: List of tool calls to split.

        Returns:
            Tuple of (parallel_tools, sequential_tools) where parallel_tools
            don't need confirmation and sequential_tools do.
        """
        to_parallel: list[ToolCall] = []
        to_sequential: list[ToolCall] = []

        for tc in tool_calls:
            tool = self.tool_manager.registry.get(tc.name)
            # Use same logic as ToolRegistry.execute for confirmation check
            if tool and (
                tc.name in self.tool_manager.registry._auto_approve_policies
                or tool.needs_confirmation(tc.arguments) is None
            ):
                to_parallel.append(tc)
            else:
                to_sequential.append(tc)

        return to_parallel, to_sequential

    def _ensure_all_tool_calls_have_response(
        self,
        tool_calls: list[ToolCall],
        responded_ids: set[str],
        agent: Agent,
    ) -> None:
        """Ensure all tool calls have a response, even if interrupted.

        Args:
            tool_calls: List of all tool calls that were requested.
            responded_ids: Set of tool call IDs that have been responded to.
            agent: The agent to submit cancellation results to.
        """
        for tool_call in tool_calls:
            if tool_call.id not in responded_ids:
                cancel_msg = "Tool execution was interrupted or cancelled."
                agent.submit_tool_result(tool_call.id, cancel_msg)
                self.output_handler.session_manager.record_tool_result(tool_call.id, cancel_msg)

    def _handle_agent_delegated_event(self, event: AgentEvent) -> None:
        """Handle an AGENT_DELEGATED event from the agent stream.

        Args:
            event: The agent delegated event.
        """
        from_agent = event.data.get("from", "unknown")
        to_agent = event.data.get("to", "unknown")
        task = event.data.get("task", "")
        self.output_handler.muted(
            f"\n[{from_agent}] Delegating to [bold cyan]{to_agent}[/]: {task}"
        )

    def _handle_agent_started_event(self, event: AgentEvent, status_obj: Status | None) -> None:
        """Handle an AGENT_STARTED event from the agent stream.

        Args:
            event: The agent started event.
            status_obj: Optional status object for updating status (ignored - spinner removed).
        """
        # No status updates - spinner functionality removed
        pass

    def _handle_agent_completed_event(self, event: AgentEvent) -> None:
        """Handle an AGENT_COMPLETED event from the agent stream.

        Args:
            event: The agent completed event.
        """
        agent_name = event.data.get("agent", "agent")
        self.output_handler.muted(f"[{agent_name}] completed work")

    def _handle_agent_message_event(self, event: AgentEvent) -> None:
        """Handle an AGENT_MESSAGE event from the agent stream.

        Args:
            event: The agent message event.
        """
        to_agent = event.data.get("to", "unknown")
        msg = event.data.get("message", "")
        self.output_handler.muted(f"\n[bold cyan]→ {to_agent}[/]: {msg}")

    def _handle_finished_event(
        self,
        is_thinking: bool,
        status_obj: Any | None = None,
    ) -> bool:
        """Handle a FINISHED event from the agent stream.

        Args:
            is_thinking: Current thinking state.
            status_obj: Optional status object to update.

        Returns:
            Updated thinking state (always False).
        """
        if is_thinking:
            self.output_handler.print_newline()
            is_thinking = False

        self.output_handler.print_newline()
        return is_thinking

    def _restart_status_spinner(self, status_obj: Any | None = None) -> None:
        """Restart the status spinner if it was stopped during thinking.

        No-op: spinner functionality removed per user request.

        Args:
            status_obj: Optional status object to update (ignored).
        """
        pass  # Spinner functionality removed

    def _handle_error_event(self, event: AgentEvent) -> None:
        """Handle an ERROR event from the agent stream.

        Args:
            event: The error event.
        """
        self.output_handler.error(str(event.data))

    async def _handle_post_stream_processing(
        self,
        pending_tool_calls: list[ToolCall],
        handled_tool_call_ids: set[str],
        accumulated_content: list[str],
        last_agent_id: str | None,
        session_tool_calls_flushed: bool,
        agent: Agent,
        content_collector: list[str] | None,
    ) -> None:
        """Handle session recording and tool execution after the event stream ends.

        Args:
            pending_tool_calls: List of pending tool calls.
            handled_tool_call_ids: Set of tool call IDs already handled.
            accumulated_content: List of accumulated content for session.
            last_agent_id: ID of the last agent that sent an event.
            session_tool_calls_flushed: Whether tool calls have been recorded to session.
            agent: The agent for turn tracking and result submission.
            content_collector: Optional list to collect content for session.
        """
        # Record assistant message to session
        # Skip if tool calls were already flushed inline by the orchestrator
        if not session_tool_calls_flushed:
            if pending_tool_calls:
                # Convert ToolCall objects to dicts for session storage
                tool_calls_dicts = [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    for tc in pending_tool_calls
                ]
                self.output_handler.session_manager.record_agent_message(
                    content="".join(accumulated_content) if accumulated_content else None,
                    tool_calls=tool_calls_dicts,
                    agent_id=last_agent_id,
                )
            elif accumulated_content:
                # Content-only response (no tool calls)
                self.output_handler.session_manager.record_agent_message(
                    content="".join(accumulated_content),
                    agent_id=last_agent_id,
                )
        elif session_tool_calls_flushed and accumulated_content:
            # Record post-tool-execution content as a separate assistant message
            self.output_handler.session_manager.record_agent_message(
                content="".join(accumulated_content),
                agent_id=last_agent_id,
            )

        # Execute only tool calls that were NOT already handled by the orchestrator
        unhandled_tool_calls = [
            tc for tc in pending_tool_calls if tc.id not in handled_tool_call_ids
        ]
        if unhandled_tool_calls:
            await self.execute_tool_calls(unhandled_tool_calls, agent, content_collector)

    async def process_agent_stream(
        self,
        event_stream: AsyncIterator[AgentEvent],
        agent: Agent,
        content_collector: list[str] | None = None,
        status_obj: Status | None = None,
    ) -> None:
        """Process an agent event stream, handling tool calls properly.

        This method collects ALL tool calls from a single response before
        executing them, which is required by the OpenAI API.

        Args:
            event_stream: Async iterator of agent events.
            agent: The agent for turn tracking and result submission.
            content_collector: Optional list to collect content for session.
            status_obj: Optional status object for updating status.
        """
        # Check loop limits before processing (unless unlimited mode)
        if self._should_stop_due_to_limits(agent):
            return

        pending_tool_calls: list[ToolCall] = []
        handled_tool_call_ids: set[str] = set()
        accumulated_content: list[str] = []
        last_agent_id: str | None = None
        # Track whether pending tool calls have been recorded to session
        # (for tool calls handled inline by the orchestrator)
        _session_tool_calls_flushed = False
        is_thinking = False

        async for event in event_stream:
            # Distinguish between events from the current agent and delegated sub-agents
            is_own_event: bool
            if event.source_agent is None:
                is_own_event = True
            elif agent.identity and agent.identity.id:
                is_own_event = event.source_agent == agent.identity.id
            else:
                is_own_event = False

            # Handle transition out of thinking
            if is_thinking and event.type != EventType.THOUGHT:
                self.output_handler.print_newline()
                is_thinking = False

            # Update status continuously
            if status_obj:
                # Need to get status message from output handler
                pass

            if event.source_agent:
                last_agent_id = event.source_agent

            if event.type == EventType.CONTENT:
                self._handle_content_event(
                    event, is_own_event, content_collector, accumulated_content
                )

            elif event.type == EventType.THOUGHT:
                is_thinking = self._handle_thought_event(event, is_thinking, status_obj)

            elif event.type == EventType.CONTEXT_COMPACTED:
                self._handle_context_compacted_event()

            elif event.type == EventType.TOOL_CALL_REQUEST:
                self._handle_tool_call_request_event(event, is_own_event, pending_tool_calls)

            elif event.type == EventType.TOOL_CALL_RESULT:
                _session_tool_calls_flushed = self._handle_tool_call_result_event(
                    event,
                    is_own_event,
                    pending_tool_calls,
                    handled_tool_call_ids,
                    accumulated_content,
                    last_agent_id,
                    _session_tool_calls_flushed,
                )

            elif event.type == EventType.AGENT_DELEGATED:
                self._handle_agent_delegated_event(event)

            elif event.type == EventType.AGENT_STARTED:
                self._handle_agent_started_event(event, status_obj)

            elif event.type == EventType.AGENT_COMPLETED:
                self._handle_agent_completed_event(event)

            elif event.type == EventType.AGENT_MESSAGE:
                self._handle_agent_message_event(event)

            elif event.type == EventType.FINISHED:
                is_thinking = self._handle_finished_event(is_thinking, status_obj)

            elif event.type == EventType.ERROR:
                self._handle_error_event(event)

        # After the stream ends, handle session recording and tool execution
        await self._handle_post_stream_processing(
            pending_tool_calls,
            handled_tool_call_ids,
            accumulated_content,
            last_agent_id,
            _session_tool_calls_flushed,
            agent,
            content_collector,
        )

    async def execute_tool_calls(
        self,
        tool_calls: list[ToolCall],
        agent: Agent,
        content_collector: list[str] | None = None,
    ) -> None:
        """Execute a batch of tool calls and continue the agent loop.

        Args:
            tool_calls: List of tool calls to execute.
            agent: The agent for turn tracking and result submission.
            content_collector: Optional list to collect content for session.
        """
        # Filter out invalid tool calls (for backwards compatibility)
        valid_tool_calls = [tc for tc in tool_calls if isinstance(tc, ToolCall)]
        if not valid_tool_calls:
            return

        # Increment iteration counter (one batch of tool calls = one iteration)
        agent.turn.increment_iteration()

        responded_ids: set[str] = set()

        # Split tool calls into those that need confirmation and those that don't
        # to allow parallel execution of "safe" tools.
        to_parallel, to_sequential = self._split_tools_by_confirmation_requirement(valid_tool_calls)

        try:
            # 1. Execute parallel group (tools not needing confirmation)
            if to_parallel:
                await asyncio.gather(
                    *(
                        self._execute_and_record_tool_call(tc, agent, responded_ids)
                        for tc in to_parallel
                    )
                )

            # 2. Execute sequential group (tools needing confirmation)
            if to_sequential:
                # Suspend key monitor while we might be showing confirmation prompts
                if self.current_monitor:
                    await self.current_monitor.suspend()

                try:
                    for tc in to_sequential:
                        await self._execute_and_record_tool_call(tc, agent, responded_ids)
                finally:
                    if self.current_monitor:
                        self.current_monitor.resume()
        finally:
            self._ensure_all_tool_calls_have_response(valid_tool_calls, responded_ids, agent)

        # Show turn status after tool execution
        self.output_handler.show_turn_status(agent, self.base_tool_iterations)

        # Add spacing after tool execution
        self.output_handler.print_newline()

        # Now that ALL results are submitted, continue the agent loop
        await self.process_agent_stream(
            agent.continue_with_tool_results(), agent, content_collector
        )

    async def handle_confirmation(self, request: ConfirmationRequest) -> bool:
        """Handle a tool confirmation request.

        Args:
            request: The confirmation request data.

        Returns:
            True if approved, False otherwise.
        """
        # Auto-approve is handled by tool_manager.handle_confirmation
        # This method only contains the interactive confirmation logic
        import json

        from rich.markup import escape

        # Escape tool name as it comes from user/tool definition
        tool_name = escape(request.tool_name)
        msg = f"Allow tool [bold cyan]{tool_name}[/] to "

        if request.tool_name == "shell":
            command = (
                request.params.get("command", "unknown command")
                if request.params
                else "unknown command"
            )
            # Escape command which can contain any characters
            msg += f"run command: [yellow]{escape(str(command))}[/]"
        elif request.tool_name == "write_file":
            path = request.params.get("path", "unknown path") if request.params else "unknown path"
            # Escape file path
            msg += f"write to file: [yellow]{escape(str(path))}[/]"
        elif request.tool_name == "edit_file":
            path = request.params.get("path", "unknown path") if request.params else "unknown path"
            # Escape file path
            msg += f"edit file: [yellow]{escape(str(path))}[/]"
        else:
            # Escape description
            description = escape(request.description)
            msg += f"execute: {description}"
            if request.params:
                # Escape params JSON
                params_str = json.dumps(request.params)
                msg += f"\nParams: [dim]{escape(params_str)}[/]"

        return await self.output_handler.renderer.confirm_tool_execution(msg)
