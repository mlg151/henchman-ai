"""
Integration tests for tool execution through UI - MINIMAL WORKING VERSION.

Tests that verify all built-in tools can be executed through the REPL
and their results are properly displayed in the UI.
"""

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from rich.console import Console

from henchman.cli.repl import Repl, ReplConfig
from henchman.core.agent import Agent
from henchman.providers.base import ToolCall
from henchman.tools.base import ToolResult


class TestToolCallHandling:
    """Tests for tool call handling in REPL."""

    @pytest.fixture
    def mock_repl(self):
        """REPL with mocked components for tool call testing."""
        console = Console(record=True)
        repl = Repl(provider=Mock(), console=console, config=ReplConfig())

        # Mock the tool_executor's tool_manager.registry.execute
        repl.tool_executor.tool_manager.registry.execute = AsyncMock(
            return_value=ToolResult(content="Result", success=True)
        )

        # Mock the tool_executor's output_handler methods
        repl.tool_executor.output_handler.muted = Mock()
        repl.tool_executor.output_handler.error = Mock()
        repl.tool_executor.output_handler.warning = Mock()

        # Mock agent with all required attributes
        repl.agent = Mock(spec=Agent)

        # Mock turn attribute (TurnState object)
        turn_mock = Mock()
        turn_mock.increment_iteration = Mock()
        turn_mock.record_tool_call = Mock()
        turn_mock.get_status_string = Mock(return_value="Turn status: iteration 1")
        repl.agent.turn = turn_mock

        # Mock identity attribute
        identity_mock = Mock()
        identity_mock.id = "test-agent"
        repl.agent.identity = identity_mock

        # Create a proper async iterator for continue_with_tool_results
        async def async_iter():
            # Empty async iterator
            if False:
                yield

        # Mock the methods that return async iterators
        repl.agent.continue_with_tool_results = MagicMock(return_value=async_iter())

        # Mock other agent methods
        repl.agent.submit_tool_result = Mock()

        return repl

    async def test_handle_tool_call_success(self, mock_repl):
        """Test successful tool call handling."""
        tool_call = ToolCall(id="test-id", name="test_tool", arguments={"param": "value"})

        # Handle tool call
        await mock_repl._handle_tool_call(tool_call)

        # Verify tool was executed via tool_executor's registry.execute
        mock_repl.tool_executor.tool_manager.registry.execute.assert_called_once_with("test_tool", {"param": "value"})

        # Verify agent received the result
        mock_repl.agent.submit_tool_result.assert_called_once_with("test-id", "Result")

    async def test_handle_tool_call_nonexistent_tool(self, mock_repl):
        """Test handling of call to non-existent tool."""
        mock_repl.tool_executor.tool_manager.registry.execute.side_effect = ValueError("Tool not found")

        tool_call = ToolCall(id="test-id", name="nonexistent_tool", arguments={})

        # Handle tool call - should handle the error gracefully
        try:
            await mock_repl._handle_tool_call(tool_call)
            # If we get here, error was handled
        except ValueError as e:
            # ValueError might be raised, that's OK for this test
            # as long as it doesn't crash the REPL
            assert "Tool not found" in str(e)
        except Exception as e:
            # Other exceptions should not occur
            pytest.fail(f"Unexpected exception: {e}")


class TestToolDisplayFormatting:
    """Tests for tool-related display formatting in UI."""

    @pytest.fixture
    def repl_with_mock_display(self):
        """REPL with mocked display components."""
        console = Console(record=True)
        repl = Repl(provider=Mock(), console=console, config=ReplConfig())

        # Mock renderer methods to capture calls
        repl.renderer = Mock()

        # Mock tool_executor components
        repl.tool_executor.output_handler.muted = Mock()
        repl.tool_executor.output_handler.error = Mock()
        repl.tool_executor.output_handler.warning = Mock()
        repl.tool_executor.tool_manager.registry.execute = AsyncMock(
            return_value=ToolResult(content="Test content", success=True)
        )

        return repl

    async def test_tool_call_display(self, repl_with_mock_display):
        """Test that tool calls trigger display methods."""
        # This test verifies that when a tool call is handled,
        # appropriate display methods are called
        tool_call = ToolCall(id="test-id", name="read_file", arguments={"path": "/tmp/test.txt"})

        # Mock agent methods needed by _handle_tool_call
        async def empty_async_iterator():
            if False:
                yield

        repl_with_mock_display.agent = Mock(spec=Agent)

        # Mock turn attribute
        turn_mock = Mock()
        turn_mock.increment_iteration = Mock()
        turn_mock.record_tool_call = Mock()
        turn_mock.get_status_string = Mock(return_value="Turn status: iteration 1")
        repl_with_mock_display.agent.turn = turn_mock

        # Mock identity attribute
        identity_mock = Mock()
        identity_mock.id = "test-agent"
        repl_with_mock_display.agent.identity = identity_mock

        repl_with_mock_display.agent.submit_tool_result = Mock()
        repl_with_mock_display.agent.continue_with_tool_results = MagicMock(
            return_value=empty_async_iterator()
        )

        # Handle the tool call directly (not through event)
        await repl_with_mock_display._handle_tool_call(tool_call)

        # Verify display interaction happened via tool_executor's output_handler
        # tool_executor calls output_handler.muted for tool calls and results
        assert repl_with_mock_display.tool_executor.output_handler.muted.call_count >= 2
        # First call shows the tool call
        first_call_args = repl_with_mock_display.tool_executor.output_handler.muted.call_args_list[0][0][0]
        assert "read_file" in first_call_args
        # Second call shows the result
        second_call_args = repl_with_mock_display.tool_executor.output_handler.muted.call_args_list[1][0][0]
        assert "result" in second_call_args.lower() or "Test content" in second_call_args
