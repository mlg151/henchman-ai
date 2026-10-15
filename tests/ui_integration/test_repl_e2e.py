"""
End-to-end integration tests for REPL flows.

Tests that verify complete user flows including:
- Tool execution and result handling
- Multi-turn conversations
- Error handling
"""

from functools import partial
from unittest.mock import Mock

import pytest
from prompt_toolkit import PromptSession
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from rich.console import Console

from henchman.cli.repl import Repl, ReplConfig
from henchman.providers.base import FinishReason, ModelProvider, StreamChunk, ToolCall


class TestReplE2E:
    @pytest.fixture
    def mock_provider(self):
        provider = Mock(spec=ModelProvider)
        provider.name = "mock"
        provider.required_tool_names = partial(ModelProvider.required_tool_names, provider)
        provider.estimate_input_tokens = partial(ModelProvider.estimate_input_tokens, provider)
        provider.prepare_output_budget = partial(ModelProvider.prepare_output_budget, provider)
        # Ensure chat_completion_stream is setup to accept calls
        return provider

    @pytest.fixture
    def repl(self, mock_provider):
        console = Console(record=True)
        config = ReplConfig()
        repl = Repl(provider=mock_provider, console=console, config=config)
        repl.config.auto_save = False
        repl.agent.set_context_limit(96_000, context_window=128_000)
        # Manually initialize session manager and session as we skip repl.run()
        from henchman.cli.session_manager import ReplSessionManager
        from henchman.core.session import SessionManager

        manager = SessionManager()
        repl.session_manager = ReplSessionManager(session_manager=manager, auto_save=False)
        session = manager.create_session(project_hash="test_hash")
        repl.set_session(session)

        # Also update the output_handler's session_manager reference
        repl.output_handler.session_manager = repl.session_manager
        repl.tool_executor.output_handler = repl.output_handler

        # Patch _run_agent_with_monitor to bypass KeyMonitor (no stdin in tests)
        original_tool_executor = repl.tool_executor

        async def _simple_run_agent_with_monitor(
            event_stream, agent, assistant_content, _status_msg
        ):
            """Simplified version that skips KeyMonitor for testing."""
            await original_tool_executor.process_agent_stream(
                event_stream, agent, assistant_content, None
            )

        repl._run_agent_with_monitor = _simple_run_agent_with_monitor
        return repl

    async def test_tool_execution_flow(self, repl, mock_provider):
        """Test the full flow of a tool execution:
        User Input -> Agent Tool Call -> REPL executes Tool -> Result to Agent -> Agent continues
        """
        tool_call = ToolCall(id="call_123", name="ask_user", arguments={"question": "How are you?"})

        # We need an async iterator that yields StreamChunks
        # First call: Tool Call
        async def stream_tool_call(*_, **__):
            yield StreamChunk(tool_calls=[tool_call], finish_reason=FinishReason.TOOL_CALLS)

        # Second call: Final Response
        async def stream_response(*_, **__):
            yield StreamChunk(content="I asked the user.", finish_reason=FinishReason.STOP)

        # Side effect to return different async iterators
        call_count = 0

        def side_effect(*_, **__):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return stream_tool_call()
            else:
                return stream_response()

        mock_provider.chat_completion_stream.side_effect = side_effect

        # A real terminal input channel supplies the tool answer.
        with create_pipe_input() as pipe:
            repl.input_handler.prompt_session = PromptSession(input=pipe, output=DummyOutput())
            pipe.send_text("Doing well!\n")
            await repl._run_agent("Please ask me a question")

        # Verify tool was executed (output contains ask_user info)
        output = repl.console.export_text()
        assert "Doing well!" in output
        assert "User input would be collected here" not in output
        # REPL uses [result] format for tool results
        assert "[result]" in output or "ask_user" in output

        # Verify provider called twice
        assert mock_provider.chat_completion_stream.call_count == 2

        # Verify session - user message is recorded
        # Note: content from tool call continuation is rendered but not separately recorded
        assert len(repl.session_manager.current.messages) >= 1
        assert repl.session_manager.current.messages[0].role == "user"
        tool_results = [m for m in repl.session_manager.current.messages if m.role == "tool"]
        assert any(m.content == "Doing well!" for m in tool_results)

    async def test_multi_turn_conversation(self, repl, mock_provider):
        """Test that context is maintained across multiple turns."""

        # Turn 1
        async def turn1(*_, **__):
            yield StreamChunk(content="Hello there!", finish_reason=FinishReason.STOP)

        # Turn 2
        async def turn2(*_, **__):
            yield StreamChunk(content="I am doing well.", finish_reason=FinishReason.STOP)

        call_count = 0

        def side_effect(*_, **__):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return turn1()
            else:
                return turn2()

        mock_provider.chat_completion_stream.side_effect = side_effect

        # Run 1
        await repl._run_agent("Hi")
        assert len(repl.session_manager.current.messages) == 2

        # Run 2
        await repl._run_agent("How are you?")
        assert len(repl.session_manager.current.messages) == 4

        # Verify Agent history
        assert len(repl.agent.history) >= 4
        # Verify provider received history in second call
        # args[0] is not usually used if called as keyword args in Agent
        # Agent calls: self.provider.chat_completion_stream(messages=messages, tools=tools)
        call_args = mock_provider.chat_completion_stream.call_args_list[1]
        # check kwargs 'messages'
        messages = call_args.kwargs["messages"]
        # History should be: User, Assistant, User
        # Plus System prompt if set.
        # Check that we have multiple messages
        assert len(messages) >= 3
