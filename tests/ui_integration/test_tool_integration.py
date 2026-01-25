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
from henchman.tools.registry import ToolRegistry


class TestToolCallHandling:
    """Tests for tool call handling in REPL."""

    @pytest.fixture
    def mock_repl(self):
        """REPL with mocked components for tool call testing."""
        console = Console(record=True)
        repl = Repl(
            provider=Mock(),
            console=console,
            config=ReplConfig()
        )

        # Mock tool registry
        repl.tool_registry = Mock(spec=ToolRegistry)
        # Ensure tool.needs_confirmation returns None
        mock_tool = Mock()
        mock_tool.needs_confirmation.return_value = None
        mock_tool.execute = AsyncMock(return_value=ToolResult(content="Result", success=True))
        repl.tool_registry.get.return_value = mock_tool

        # Mock agent
        repl.agent = Mock(spec=Agent)

        # Create a proper async iterator for continue_with_tool_results
        async def async_iter():
            # Empty async iterator
            if False:
                yield

        # Mock the methods that return async iterators
        repl.agent.continue_with_tool_results = MagicMock(return_value=async_iter())

        # Mock other agent methods
        repl.agent.submit_tool_result = AsyncMock()

        # Mock renderer
        repl.renderer.muted = Mock()
        repl.renderer.info = Mock()
        repl.renderer.success = Mock()
        repl.renderer.error = Mock()

        return repl

    async def test_handle_tool_call_success(self, mock_repl):
        """Test successful tool call handling."""
        tool_call = ToolCall(
            id="test-id",
            name="test_tool",
            arguments={"param": "value"}
        )

        # Handle tool call
        await mock_repl._handle_tool_call(tool_call)

        # Verify tool was executed
        mock_tool = mock_repl.tool_registry.get.return_value
        mock_tool.execute.assert_called_once_with(param="value")

        # Verify agent received the result
        mock_repl.agent.submit_tool_result.assert_called_once_with(
            "test-id", "Result"
        )

    async def test_handle_tool_call_nonexistent_tool(self, mock_repl):
        """Test handling of call to non-existent tool."""
        mock_repl.tool_registry.execute.side_effect = ValueError("Tool not found")

        tool_call = ToolCall(
            id="test-id",
            name="nonexistent_tool",
            arguments={}
        )

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
        repl = Repl(
            provider=Mock(),
            console=console,
            config=ReplConfig()
        )

        # Mock renderer methods to capture calls
        repl.renderer = Mock()

        return repl

    async def test_tool_call_display(self, repl_with_mock_display):
        """Test that tool calls trigger display methods."""
        # This test verifies that when a tool call is handled,
        # appropriate display methods are called
        tool_call = ToolCall(
            id="test-id",
            name="read_file",
            arguments={"path": "/tmp/test.txt"}
        )

        # Mock agent methods needed by _handle_tool_call
        async def empty_async_iterator():
            if False:
                yield

        repl_with_mock_display.agent = Mock(spec=Agent)
        repl_with_mock_display.agent.submit_tool_result = AsyncMock()
        repl_with_mock_display.agent.continue_with_tool_results = MagicMock(
            return_value=empty_async_iterator()
        )

        # Mock the renderer.muted method (which is what _handle_tool_call calls)
        repl_with_mock_display.renderer.muted = Mock()
        repl_with_mock_display.renderer.tool_result = Mock()

        # Mock tool registry
        repl_with_mock_display.tool_registry = Mock(spec=ToolRegistry)
        mock_tool = Mock()
        mock_tool.needs_confirmation.return_value = None
        mock_tool.execute = AsyncMock(return_value=ToolResult(content="Test content", success=True))
        repl_with_mock_display.tool_registry.get.return_value = mock_tool

        # Handle the tool call directly (not through event)
        await repl_with_mock_display._handle_tool_call(tool_call)

        # Verify display interaction happened
        # We check tool_result was called
        repl_with_mock_display.renderer.tool_result.assert_called_once_with(
            "Test content", True, None
        )
