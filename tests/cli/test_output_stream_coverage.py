"""Tests for output_handler.py, stream_event_handlers.py, and tool_executor.py."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.cli.stream_event_handlers import (
    StreamState,
    _display_tool_result,
    _escape,
    _handle_agent_completed,
    _handle_agent_routing,
    _handle_context_compacted,
    _handle_thought,
    _handle_tool_call_request,
    _handle_tool_call_result,
    build_confirmation_message,
    determine_event_ownership,
    dispatch_event,
    update_processing_state,
)
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import ToolCall
from henchman.tools.base import ConfirmationRequest

# ---------------------------------------------------------------------------
# stream_event_handlers tests
# ---------------------------------------------------------------------------


class TestStreamEventHandlers:
    """Tests for stream event handler functions."""

    def _make_output_handler(self) -> MagicMock:
        """Create a mock output handler."""
        oh = MagicMock()
        oh.session_manager = MagicMock()
        oh.session_manager.record_tool_result = MagicMock()
        oh.session_manager.record_agent_message = MagicMock()
        return oh

    def _make_agent(self) -> MagicMock:
        """Create a mock agent."""
        agent = MagicMock()
        agent.identity = None
        return agent

    def test_escape_markup(self) -> None:
        """Test _escape escapes markup characters."""
        result = _escape("[bold]text[/bold]")
        assert "[bold]" not in result or "\\[bold]" in result

    def test_determine_event_ownership_no_source(self) -> None:
        """Test determine_event_ownership returns True when no source_agent."""
        event = AgentEvent(type=EventType.CONTENT, data="hello", source_agent=None)
        agent = self._make_agent()
        assert determine_event_ownership(event, agent) is True

    def test_determine_event_ownership_with_matching_source(self) -> None:
        """Test determine_event_ownership with matching source agent."""
        event = AgentEvent(type=EventType.CONTENT, data="hello", source_agent="agent-1")
        agent = self._make_agent()
        identity = MagicMock()
        identity.id = "agent-1"
        agent.identity = identity
        assert determine_event_ownership(event, agent) is True

    def test_determine_event_ownership_with_non_matching_source(self) -> None:
        """Test determine_event_ownership with non-matching source agent."""
        event = AgentEvent(type=EventType.CONTENT, data="hello", source_agent="agent-2")
        agent = self._make_agent()
        identity = MagicMock()
        identity.id = "agent-1"
        agent.identity = identity
        assert determine_event_ownership(event, agent) is False

    def test_determine_event_ownership_no_identity(self) -> None:
        """Test determine_event_ownership with no identity returns False."""
        event = AgentEvent(type=EventType.CONTENT, data="hello", source_agent="agent-1")
        agent = self._make_agent()
        agent.identity = None
        assert determine_event_ownership(event, agent) is False

    def test_update_processing_state_exits_thinking(self) -> None:
        """Test update_processing_state exits thinking mode for non-THOUGHT event."""
        oh = self._make_output_handler()
        state = StreamState()
        state.is_thinking = True
        event = AgentEvent(type=EventType.CONTENT, data="hello")
        agent = self._make_agent()
        update_processing_state(oh, state, event, agent)
        assert state.is_thinking is False
        oh.print_newline.assert_called_once()

    def test_update_processing_state_stays_thinking(self) -> None:
        """Test update_processing_state stays thinking for THOUGHT event."""
        oh = self._make_output_handler()
        state = StreamState()
        state.is_thinking = True
        event = AgentEvent(type=EventType.THOUGHT, data="thinking...")
        agent = self._make_agent()
        update_processing_state(oh, state, event, agent)
        assert state.is_thinking is True

    def test_display_tool_result_success(self) -> None:
        """Test _display_tool_result with success."""
        oh = self._make_output_handler()
        _display_tool_result(oh, "Result text", True)
        oh.muted.assert_called()

    def test_display_tool_result_failure(self) -> None:
        """Test _display_tool_result with failure."""
        oh = self._make_output_handler()
        _display_tool_result(oh, "Error text", False)
        oh.error.assert_called()

    def test_handle_thought_first(self) -> None:
        """Test _handle_thought starts thinking mode."""
        oh = self._make_output_handler()
        state = StreamState()
        event = AgentEvent(type=EventType.THOUGHT, data="thinking...")
        _handle_thought(oh, event, state)
        assert state.is_thinking is True
        oh.thinking.assert_called()

    def test_handle_thought_continues(self) -> None:
        """Test _handle_thought in already-thinking state."""
        oh = self._make_output_handler()
        state = StreamState()
        state.is_thinking = True
        event = AgentEvent(type=EventType.THOUGHT, data="more thinking...")
        _handle_thought(oh, event, state)
        oh.thinking.assert_called_with("more thinking...")

    def test_handle_context_compacted(self) -> None:
        """Test _handle_context_compacted shows warning."""
        oh = self._make_output_handler()
        _handle_context_compacted(oh)
        oh.warning.assert_called()

    def test_handle_tool_call_request_own_event(self) -> None:
        """Test _handle_tool_call_request appends to pending for own event."""
        oh = self._make_output_handler()
        state = StreamState()
        state.is_own_event = True
        tc = ToolCall(id="tc-1", name="read_file", arguments={"path": "/tmp/test.txt"})
        event = AgentEvent(type=EventType.TOOL_CALL_REQUEST, data=tc)
        _handle_tool_call_request(oh, event, state)
        assert len(state.pending_tool_calls) == 1

    def test_handle_tool_call_request_not_own_event(self) -> None:
        """Test _handle_tool_call_request does not append for non-own event."""
        oh = self._make_output_handler()
        state = StreamState()
        state.is_own_event = False
        tc = ToolCall(id="tc-1", name="read_file", arguments={})
        event = AgentEvent(type=EventType.TOOL_CALL_REQUEST, data=tc)
        _handle_tool_call_request(oh, event, state)
        assert len(state.pending_tool_calls) == 0

    def test_handle_tool_call_result_not_dict(self) -> None:
        """Test _handle_tool_call_result with non-dict data."""
        oh = self._make_output_handler()
        state = StreamState()
        event = AgentEvent(type=EventType.TOOL_CALL_RESULT, data="not a dict")
        _handle_tool_call_result(oh, event, state)
        # Should return without error

    def test_handle_tool_call_result_dict(self) -> None:
        """Test _handle_tool_call_result with dict data."""
        oh = self._make_output_handler()
        state = StreamState()
        state.is_own_event = True
        event = AgentEvent(
            type=EventType.TOOL_CALL_RESULT,
            data={"tool_call_id": "tc-1", "result": "done", "success": True},
        )
        _handle_tool_call_result(oh, event, state)
        oh.session_manager.record_tool_result.assert_called_with("tc-1", "done")

    def test_handle_agent_routing_delegated(self) -> None:
        """Test _handle_agent_routing for AGENT_DELEGATED event."""
        oh = self._make_output_handler()
        event = AgentEvent(
            type=EventType.AGENT_DELEGATED,
            data={"from": "orchestrator", "to": "engineer", "task": "write code"},
        )
        _handle_agent_routing(oh, event)
        oh.muted.assert_called()

    def test_handle_agent_routing_message(self) -> None:
        """Test _handle_agent_routing for AGENT_MESSAGE event."""
        oh = self._make_output_handler()
        event = AgentEvent(
            type=EventType.AGENT_MESSAGE,
            data={"to": "engineer", "message": "here is the task"},
        )
        _handle_agent_routing(oh, event)
        oh.muted.assert_called()

    def test_handle_agent_completed(self) -> None:
        """Test _handle_agent_completed shows agent completion info."""
        oh = self._make_output_handler()
        event = AgentEvent(
            type=EventType.AGENT_COMPLETED,
            data={"agent": "engineer", "summary": "done"},
        )
        _handle_agent_completed(oh, event)
        oh.muted.assert_called()

    def test_build_confirmation_message_shell(self) -> None:
        """Test build_confirmation_message for shell command."""
        request = ConfirmationRequest(
            tool_name="shell",
            params={"command": "ls -la"},
            description="Run shell command",
        )
        msg = build_confirmation_message(request)
        assert "shell" in msg
        assert "ls -la" in msg

    def test_build_confirmation_message_write_file(self) -> None:
        """Test build_confirmation_message for write_file."""
        request = ConfirmationRequest(
            tool_name="write_file",
            params={"path": "/tmp/test.txt"},
            description="Write to file",
        )
        msg = build_confirmation_message(request)
        assert "/tmp/test.txt" in msg

    def test_build_confirmation_message_edit_file(self) -> None:
        """Test build_confirmation_message for edit_file."""
        request = ConfirmationRequest(
            tool_name="edit_file",
            params={"path": "/tmp/test.py"},
            description="Edit file",
        )
        msg = build_confirmation_message(request)
        assert "/tmp/test.py" in msg

    def test_build_confirmation_message_other(self) -> None:
        """Test build_confirmation_message for unknown tool."""
        request = ConfirmationRequest(
            tool_name="custom_tool",
            params={"arg": "value"},
            description="Do something custom",
        )
        msg = build_confirmation_message(request)
        assert "custom_tool" in msg

    def test_build_confirmation_message_no_params(self) -> None:
        """Test build_confirmation_message with no params."""
        request = ConfirmationRequest(
            tool_name="custom_tool",
            params=None,
            description="Do something",
        )
        msg = build_confirmation_message(request)
        assert "custom_tool" in msg

    def test_dispatch_event_content(self) -> None:
        """Test dispatch_event for CONTENT event."""
        oh = self._make_output_handler()
        state = StreamState()
        agent = self._make_agent()
        event = AgentEvent(type=EventType.CONTENT, data="hello world")
        dispatch_event(oh, event, state, agent, [])
        oh.print_agent_content.assert_called_with("hello world")

    def test_dispatch_event_error(self) -> None:
        """Test dispatch_event for ERROR event."""
        oh = self._make_output_handler()
        state = StreamState()
        agent = self._make_agent()
        event = AgentEvent(type=EventType.ERROR, data="something went wrong")
        dispatch_event(oh, event, state, agent, None)
        oh.error.assert_called()

    def test_dispatch_event_finished(self) -> None:
        """Test dispatch_event for FINISHED event."""
        oh = self._make_output_handler()
        state = StreamState()
        agent = self._make_agent()
        event = AgentEvent(type=EventType.FINISHED, data=None)
        dispatch_event(oh, event, state, agent, None)
        # FINISHED is handled gracefully


# ---------------------------------------------------------------------------
# output_handler.py tests
# ---------------------------------------------------------------------------


class TestOutputHandlerCoverage:
    """Coverage tests for output_handler.py missing lines."""

    def _make_output_handler(self):
        """Create an OutputHandler with mocked dependencies."""
        from henchman.cli.output_handler import OutputHandler

        renderer = MagicMock()
        tool_manager = MagicMock()
        session_manager = MagicMock()
        provider = MagicMock()
        provider.__class__.__name__ = "DeepSeekProvider"
        provider.default_model = "deepseek-chat"

        return OutputHandler(
            renderer=renderer,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
        )

    def test_getattr_delegates_to_renderer(self) -> None:
        """Test __getattr__ delegates unknown attributes to renderer."""
        oh = self._make_output_handler()
        oh.renderer.some_method = MagicMock(return_value="result")
        result = oh.some_method
        assert result is not None

    def test_getattr_raises_for_missing(self) -> None:
        """Test __getattr__ raises AttributeError for truly missing attributes."""
        oh = self._make_output_handler()
        del oh.renderer.nonexistent_method
        with pytest.raises(AttributeError):
            _ = oh.nonexistent_method

    def test_get_toolbar_status_basic(self) -> None:
        """Test get_toolbar_status returns status list."""
        oh = self._make_output_handler()
        status = oh.get_toolbar_status()
        assert isinstance(status, list)

    def test_get_toolbar_status_with_agent(self) -> None:
        """Test get_toolbar_status with agent."""
        oh = self._make_output_handler()
        agent = MagicMock()
        agent.get_messages_for_api.return_value = []
        with patch("henchman.utils.tokens.TokenCounter") as mock_counter:
            mock_counter.count_messages.return_value = 1000
            status = oh.get_toolbar_status(agent)
        assert isinstance(status, list)

    def test_add_provider_status(self) -> None:
        """Test _add_provider_status adds provider info."""
        oh = self._make_output_handler()
        status = []
        oh._add_provider_status(status)
        assert len(status) > 0

    def test_add_tool_status(self) -> None:
        """Test _add_tool_status adds tool count."""
        oh = self._make_output_handler()
        oh.tool_manager.registry.list_tools.return_value = [MagicMock(), MagicMock()]
        status = []
        oh._add_tool_status(status)
        assert any("Tools" in s[1] for s in status)

    def test_add_mcp_status_no_mcp(self) -> None:
        """Test _add_mcp_status with no MCP manager."""
        oh = self._make_output_handler()
        oh.mcp_manager = None
        status = []
        oh._add_mcp_status(status)
        assert len(status) == 0

    def test_add_mcp_status_with_mcp(self) -> None:
        """Test _add_mcp_status with connected MCP clients."""
        oh = self._make_output_handler()
        client1 = MagicMock()
        client1.is_connected = True
        oh.mcp_manager = MagicMock()
        oh.mcp_manager.clients = {"server1": client1}
        status = []
        oh._add_mcp_status(status)
        assert any("MCP" in s[1] for s in status)

    def test_count_connected_mcp_clients(self) -> None:
        """Test _count_connected_mcp_clients counts connected clients."""
        oh = self._make_output_handler()
        client1 = MagicMock()
        client1.is_connected = True
        client2 = MagicMock()
        client2.is_connected = False
        oh.mcp_manager = MagicMock()
        oh.mcp_manager.clients = {"s1": client1, "s2": client2}
        count = oh._count_connected_mcp_clients()
        assert count == 1

    def test_count_connected_no_mcp(self) -> None:
        """Test _count_connected_mcp_clients with no MCP manager."""
        oh = self._make_output_handler()
        oh.mcp_manager = None
        count = oh._count_connected_mcp_clients()
        assert count == 0

    def test_get_max_tokens_from_model(self) -> None:
        """Test _get_max_tokens from model."""
        oh = self._make_output_handler()
        with patch("henchman.utils.tokens.get_model_limit", return_value=128000):
            result = oh._get_max_tokens()
        assert result == 128000

    def test_get_max_tokens_no_settings(self) -> None:
        """Test _get_max_tokens with no settings."""
        oh = self._make_output_handler()
        oh.provider = MagicMock()
        oh.provider.default_model = None
        oh.settings = None
        with patch("henchman.utils.tokens.get_model_limit", return_value=0):
            result = oh._get_max_tokens()
        assert result == 0

    def test_start_background_indexing(self) -> None:
        """Test start_background_indexing with RAG system."""
        oh = self._make_output_handler()
        rag = MagicMock()
        rag.index_async = AsyncMock()
        oh.rag_system = rag

        async def _run():
            with patch.object(oh, "_safe_create_task") as mock_task:
                oh.start_background_indexing()
                mock_task.assert_called_once()

        asyncio.run(_run())

    def test_start_background_indexing_no_rag(self) -> None:
        """Test start_background_indexing without RAG system."""
        oh = self._make_output_handler()
        oh.rag_system = None
        oh.start_background_indexing()  # Should not raise

    def test_add_rag_status_no_rag(self) -> None:
        """Test _add_rag_status with no RAG system."""
        oh = self._make_output_handler()
        oh.rag_system = None
        status = []
        oh._add_rag_status(status)
        assert len(status) == 0


# ---------------------------------------------------------------------------
# tool_executor.py tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
class TestToolExecutorCoverage:
    """Coverage tests for tool_executor.py."""

    def _make_executor(self):
        """Create a ToolExecutor with mocked dependencies."""
        from henchman.cli.tool_executor import ToolExecutor

        output_handler = MagicMock()
        output_handler.session_manager = MagicMock()
        output_handler.session_manager.record_tool_result = MagicMock()
        tool_manager = MagicMock()
        provider = MagicMock()
        return ToolExecutor(
            output_handler=output_handler,
            tool_manager=tool_manager,
            provider=provider,
        )

    def _make_agent(self, unlimited: bool = False) -> MagicMock:
        """Create a mock agent."""
        agent = MagicMock()
        agent.unlimited_mode = unlimited
        agent.turn = MagicMock()
        agent.turn.is_at_limit.return_value = False
        agent.turn.tool_count = 0
        agent.turn.is_spinning.return_value = False
        agent.turn.get_adaptive_limit.return_value = 25
        agent.turn.iteration = 0
        return agent

    def test_should_stop_due_to_limits_false_normal(self) -> None:
        """Test _should_stop_due_to_limits returns False for normal operation."""
        executor = self._make_executor()
        agent = self._make_agent()
        assert executor._should_stop_due_to_limits(agent) is False

    def test_should_stop_due_to_limits_unlimited_mode(self) -> None:
        """Test _should_stop_due_to_limits returns False in unlimited mode."""
        executor = self._make_executor()
        agent = self._make_agent(unlimited=True)
        agent.turn.is_at_limit.return_value = True
        assert executor._should_stop_due_to_limits(agent) is False

    def test_should_stop_due_to_limits_iteration_limit(self) -> None:
        """Test _should_stop_due_to_limits returns True when at iteration limit."""
        executor = self._make_executor()
        agent = self._make_agent()
        agent.turn.is_at_limit.return_value = True
        assert executor._should_stop_due_to_limits(agent) is True
        executor.output_handler.error.assert_called()

    def test_should_stop_due_to_limits_tool_count(self) -> None:
        """Test _should_stop_due_to_limits returns True when tool count exceeded."""
        executor = self._make_executor()
        agent = self._make_agent()
        agent.turn.tool_count = 200
        assert executor._should_stop_due_to_limits(agent) is True

    def test_should_stop_due_to_limits_spinning(self) -> None:
        """Test _should_stop_due_to_limits warns but not stops when spinning."""
        executor = self._make_executor()
        agent = self._make_agent()
        agent.turn.is_spinning.return_value = True
        agent.turn.iteration = 5
        result = executor._should_stop_due_to_limits(agent)
        assert result is False
        executor.output_handler.warning.assert_called()

    async def test_handle_confirmation_approved(self) -> None:
        """Test handle_confirmation when approved."""
        executor = self._make_executor()
        executor.output_handler.renderer.confirm_tool_execution = AsyncMock(return_value=True)
        request = ConfirmationRequest(
            tool_name="shell",
            params={"command": "ls"},
            description="Run shell",
        )
        result = await executor.handle_confirmation(request)
        assert result is True

    async def test_handle_confirmation_denied(self) -> None:
        """Test handle_confirmation when denied."""
        executor = self._make_executor()
        executor.output_handler.renderer.confirm_tool_execution = AsyncMock(return_value=False)
        request = ConfirmationRequest(
            tool_name="write_file",
            params={"path": "/tmp/test.txt"},
            description="Write file",
        )
        result = await executor.handle_confirmation(request)
        assert result is False

    def test_ensure_all_tool_calls_have_response(self) -> None:
        """Test _ensure_all_tool_calls_have_response submits cancel for unresponded."""
        executor = self._make_executor()
        agent = self._make_agent()
        tc1 = ToolCall(id="tc-1", name="read_file", arguments={})
        tc2 = ToolCall(id="tc-2", name="write_file", arguments={})
        responded_ids = {"tc-1"}  # tc-2 not responded
        executor._ensure_all_tool_calls_have_response([tc1, tc2], responded_ids, agent)
        agent.submit_tool_result.assert_called_once_with("tc-2", "Tool execution was interrupted or cancelled.")

    def test_split_tools_by_confirmation(self) -> None:
        """Test _split_tools_by_confirmation_requirement categorizes tools."""
        executor = self._make_executor()
        tc_auto = ToolCall(id="tc-1", name="read_file", arguments={})
        tc_confirm = ToolCall(id="tc-2", name="shell", arguments={"command": "ls"})

        # Tool "read_file" is in auto-approve, "shell" needs confirmation
        read_tool = MagicMock()
        read_tool.needs_confirmation = MagicMock(return_value=None)  # Auto-approve
        shell_tool = MagicMock()
        shell_tool.needs_confirmation = MagicMock(return_value=True)  # Needs confirm

        executor.tool_manager.registry.get.side_effect = lambda name: {
            "read_file": read_tool,
            "shell": shell_tool,
        }.get(name)
        executor.tool_manager.registry._auto_approve_policies = {"read_file"}

        to_parallel, to_sequential = executor._split_tools_by_confirmation_requirement(
            [tc_auto, tc_confirm]
        )
        assert tc_auto in to_parallel
        assert tc_confirm in to_sequential

    async def test_execute_and_record_tool_call_success(self) -> None:
        """Test _execute_and_record_tool_call on success."""
        executor = self._make_executor()
        agent = self._make_agent()
        result = MagicMock()
        result.content = "file content"
        result.success = True
        result.error = None
        executor.tool_manager.registry.execute = AsyncMock(return_value=result)
        tc = ToolCall(id="tc-1", name="read_file", arguments={"path": "/tmp/f.txt"})
        responded_ids: set[str] = set()
        await executor._execute_and_record_tool_call(tc, agent, responded_ids)
        assert "tc-1" in responded_ids

    async def test_execute_and_record_tool_call_failure(self) -> None:
        """Test _execute_and_record_tool_call on failure."""
        executor = self._make_executor()
        agent = self._make_agent()
        result = MagicMock()
        result.content = ""
        result.success = False
        result.error = "Permission denied"
        executor.tool_manager.registry.execute = AsyncMock(return_value=result)
        tc = ToolCall(id="tc-1", name="write_file", arguments={})
        responded_ids: set[str] = set()
        await executor._execute_and_record_tool_call(tc, agent, responded_ids)
        executor.output_handler.error.assert_called()

    async def test_process_agent_stream_stop_due_to_limits(self) -> None:
        """Test process_agent_stream stops when limits reached."""
        executor = self._make_executor()
        agent = self._make_agent()
        agent.turn.is_at_limit.return_value = True

        async def _empty_stream():
            return
            yield  # noqa: unreachable

        await executor.process_agent_stream(_empty_stream(), agent)
        executor.output_handler.error.assert_called()

    async def test_process_agent_stream_does_not_reannounce_tool_requests(self) -> None:
        """Tool requests shown during streaming should not be echoed again on execution."""
        executor = self._make_executor()
        agent = self._make_agent()
        tool_call = ToolCall(id="tc-1", name="shell", arguments={"command": "echo hi"})

        result = MagicMock()
        result.content = "hi"
        result.success = True
        result.error = None
        executor.tool_manager.registry.execute = AsyncMock(return_value=result)

        async def _continue_stream():
            if False:
                yield

        agent.continue_with_tool_results.return_value = _continue_stream()

        async def _event_stream():
            yield AgentEvent(type=EventType.TOOL_CALL_REQUEST, data=tool_call)
            yield AgentEvent(type=EventType.FINISHED)

        await executor.process_agent_stream(_event_stream(), agent)

        muted_messages = [call.args[0] for call in executor.output_handler.muted.call_args_list]
        tool_messages = [message for message in muted_messages if "[tool]" in message]
        result_messages = [message for message in muted_messages if "[result]" in message]

        assert len(tool_messages) == 1
        assert "shell" in tool_messages[0]
        assert len(result_messages) == 1

    async def test_execute_tool_calls_empty(self) -> None:
        """Test execute_tool_calls with empty list."""
        executor = self._make_executor()
        agent = self._make_agent()
        await executor.execute_tool_calls([], agent)
        # Should do nothing

    async def test_execute_tool_calls_invalid_items(self) -> None:
        """Test execute_tool_calls filters non-ToolCall items."""
        executor = self._make_executor()
        agent = self._make_agent()
        await executor.execute_tool_calls(["not-a-tool-call", None], agent)
        # Should do nothing
