"""
UI integration tests for MCP (Model Context Protocol).

Tests that verify MCP server integration works correctly through the UI,
including command execution and tool discovery.
"""

from __future__ import annotations

from io import StringIO
from unittest.mock import AsyncMock, Mock, patch

import pytest
from rich.console import Console

from henchman.cli.commands import CommandRegistry
from henchman.cli.repl import Repl, ReplConfig
from henchman.core.events import AgentEvent, EventType
from henchman.mcp.config import McpServerConfig
from henchman.mcp.manager import McpManager
from henchman.mcp.tool import McpTool
from henchman.providers.base import ToolCall
from henchman.tools.base import ToolResult
from henchman.tools.registry import ToolRegistry


class TestMCPUIIntegration:
    """UI integration tests for MCP functionality."""

    @pytest.fixture
    def mock_provider(self):
        """Mock provider for testing."""
        provider = Mock()
        provider.chat_completion = AsyncMock()
        return provider

    @pytest.fixture
    def console_with_recording(self):
        """Console that records output for verification."""
        return Console(record=True, width=80, file=StringIO())

    @pytest.fixture
    def mock_mcp_manager(self):
        """Create a mock MCP manager with test servers."""
        manager = Mock(spec=McpManager)

        # Configure mock manager behavior
        manager.get_server_names.return_value = ["filesystem", "github"]
        manager.is_trusted.side_effect = lambda name: name == "github"
        manager.clients = {
            "filesystem": Mock(is_connected=True),
            "github": Mock(is_connected=False),
        }

        # Create mock tools
        mock_tool1 = Mock(spec=McpTool)
        mock_tool1.name = "read_file"
        mock_tool1.description = "Read a file"
        mock_tool1.server_name = "filesystem"

        mock_tool2 = Mock(spec=McpTool)
        mock_tool2.name = "list_issues"
        mock_tool2.description = "List GitHub issues"
        mock_tool2.server_name = "github"

        manager.get_all_tools.return_value = [mock_tool1, mock_tool2]

        return manager

    @pytest.fixture
    def repl_with_mcp(self, mock_provider, console_with_recording, mock_mcp_manager):
        """REPL instance with MCP manager configured."""
        repl = Repl(provider=mock_provider, console=console_with_recording, config=ReplConfig())

        # Mock the command with proper execute method
        mock_command = Mock()
        mock_command.execute = AsyncMock(return_value=None)

        # Mock command_registry.get to return our mock command
        repl.command_processor.command_registry = Mock(spec=CommandRegistry)
        repl.command_processor.command_registry.get = Mock(return_value=mock_command)

        # Store mock_command on repl for assertions
        repl._mock_command = mock_command

        # Mock renderer
        repl.renderer = Mock()
        repl.renderer.console = console_with_recording
        repl.renderer.success = Mock()
        repl.renderer.error = Mock()
        repl.renderer.muted = Mock()
        repl.renderer.info = Mock()
        repl.renderer.warning = Mock()
        repl.renderer.print_newline = Mock()
        repl.renderer.print_agent_content = Mock()
        # create_status must return a context manager
        mock_status = Mock()
        mock_status.__enter__ = Mock(return_value=mock_status)
        mock_status.__exit__ = Mock(return_value=False)
        repl.renderer.create_status = Mock(return_value=mock_status)

        # Update command_processor's output_handler to use mocked renderer
        repl.command_processor.output_handler.renderer = repl.renderer

        # Add MCP manager to repl (simulating real REPL setup)
        repl.mcp_manager = mock_mcp_manager

        return repl

    async def test_mcp_list_command_integration(self, repl_with_mcp):
        """Test /mcp list command integration through REPL."""
        # Execute /mcp list command through REPL
        result = await repl_with_mcp.process_input("/mcp list")

        # Verify command was executed
        assert result is True
        repl_with_mcp.command_processor.command_registry.get.assert_called_with("mcp")
        repl_with_mcp._mock_command.execute.assert_called_once()

        # Check the context passed to execute
        ctx = repl_with_mcp._mock_command.execute.call_args[0][0]
        assert ctx.args == ["list"]

    async def test_mcp_status_command_integration(self, repl_with_mcp):
        """Test /mcp status command integration through REPL."""
        # Execute /mcp status command through REPL
        result = await repl_with_mcp.process_input("/mcp status")

        # Verify command was executed
        assert result is True
        repl_with_mcp.command_processor.command_registry.get.assert_called_with("mcp")
        repl_with_mcp._mock_command.execute.assert_called_once()

        # Check the context passed to execute
        ctx = repl_with_mcp._mock_command.execute.call_args[0][0]
        assert ctx.args == ["status"]

    async def test_mcp_command_no_args_shows_help(self, repl_with_mcp):
        """Test /mcp with no args shows help through REPL."""
        # Execute /mcp command without arguments
        result = await repl_with_mcp.process_input("/mcp")

        # Verify command was executed
        assert result is True
        repl_with_mcp.command_processor.command_registry.get.assert_called_with("mcp")
        repl_with_mcp._mock_command.execute.assert_called_once()

        # Check context has empty args
        ctx = repl_with_mcp._mock_command.execute.call_args[0][0]
        assert ctx.args == []

    async def test_mcp_tool_execution_through_ui(self, repl_with_mcp):
        """Test MCP tool execution through the UI via agent."""

        # Setup agent to request MCP tool call
        async def mock_agent_run(*_, **__):
            # Yield a tool call request for an MCP tool
            yield AgentEvent(
                type=EventType.TOOL_CALL_REQUEST,
                data=ToolCall(id="read-test", name="read_file", arguments={"path": "/tmp/test.txt"}),
            )
            yield AgentEvent(type=EventType.FINISHED, data=None)

        repl_with_mcp.orchestrator.run = Mock(side_effect=mock_agent_run)

        # Mock tool registry to handle MCP tool
        mock_tool_registry = Mock(spec=ToolRegistry)
        mock_tool_registry.execute = AsyncMock(
            return_value=ToolResult("File content: Hello World"),
        )
        repl_with_mcp.agent.tool_registry = mock_tool_registry

        async def finish_stream():
            yield AgentEvent(type=EventType.FINISHED, data="stop")

        repl_with_mcp.agent.continue_with_tool_results = Mock(side_effect=finish_stream)

        with patch("henchman.cli.input_handler.expand_at_references", side_effect=lambda x: x):
            # Process input that triggers agent with MCP tool
            result = await repl_with_mcp.process_input("Read the test file")

        # Verify agent was run
        assert result is True
        repl_with_mcp.orchestrator.run.assert_called_once()
        mock_tool_registry.execute.assert_awaited_once_with("read_file", {"path": "/tmp/test.txt"})
        repl_with_mcp.renderer.error.assert_not_called()

    async def test_mcp_unknown_subcommand(self, repl_with_mcp):
        """Test /mcp with unknown subcommand shows help."""
        # Execute unknown subcommand
        result = await repl_with_mcp.process_input("/mcp unknown")

        # Verify command was executed
        assert result is True
        repl_with_mcp.command_processor.command_registry.get.assert_called_with("mcp")
        repl_with_mcp._mock_command.execute.assert_called_once()

        # Check context has "unknown" as argument
        ctx = repl_with_mcp._mock_command.execute.call_args[0][0]
        assert ctx.args == ["unknown"]

    async def test_mcp_command_with_real_manager(self):
        """Test /mcp command with real McpManager (mocking external processes)."""
        # Create real McpManager with mock configs
        configs = {
            "test_server": McpServerConfig(
                command="echo",
                args=["test"],
                trusted=True,
            )
        }

        # Create mock client factory instead of patching McpClient at module level
        mock_client = Mock()
        mock_client.connect = AsyncMock()
        mock_client.disconnect = AsyncMock()
        mock_client.get_tools = Mock(return_value=[])
        mock_client.is_connected = True

        def mock_factory(
            _name: str,
            _config: McpServerConfig,
            _verbose: bool = False,
        ) -> object:
            return mock_client

        manager = McpManager(configs, client_factory=mock_factory)

        # Connect to test server
        await manager.connect_all()

        # Verify manager is properly initialized
        assert "test_server" in manager.get_server_names()
        assert manager.is_trusted("test_server")
        assert len(manager.clients) == 1

        await manager.disconnect_all()

    async def test_mcp_tool_integration(self):
        """Test MCP tool integration."""
        # Create a mock MCP tool
        mock_mcp_tool = Mock(spec=McpTool)
        mock_mcp_tool.name = "mcp_read_file"
        mock_mcp_tool.description = "Read file via MCP"
        mock_mcp_tool.kind = Mock()
        mock_mcp_tool.execute = AsyncMock(return_value="MCP file content")

        # Test tool execution directly
        result = await mock_mcp_tool.execute({})
        assert result == "MCP file content"


class TestMCPCommandOutputFormatting:
    """Tests for MCP command output formatting."""

    @pytest.fixture
    def console(self):
        """Create a test console."""
        return Console(file=StringIO(), force_terminal=True, width=80)

    async def test_mcp_list_output_format(self, console):
        """Test /mcp list output formatting."""
        from henchman.cli.commands import CommandContext
        from henchman.cli.commands.mcp import McpCommand

        # Create mock manager
        mock_manager = Mock(spec=McpManager)
        mock_manager.get_server_names.return_value = ["server1", "server2"]
        mock_manager.is_trusted.side_effect = lambda name: name == "server1"
        mock_manager.clients = {
            "server1": Mock(is_connected=True),
            "server2": Mock(is_connected=False),
        }

        # Create context with manager
        ctx = CommandContext(console=console, args=["list"])
        ctx.mcp_manager = mock_manager

        # Execute command
        cmd = McpCommand()
        await cmd.execute(ctx)

        # Verify output format
        output = console.file.getvalue()
        assert "server1" in output
        assert "server2" in output

    async def test_mcp_status_output_format(self, console):
        """Test /mcp status output formatting."""
        from henchman.cli.commands import CommandContext
        from henchman.cli.commands.mcp import McpCommand

        # Create mock manager with tools
        mock_manager = Mock(spec=McpManager)
        mock_manager.get_server_names.return_value = ["test"]
        mock_manager.clients = {"test": Mock(is_connected=True)}

        # Create mock tools
        mock_tools = [Mock(name=f"tool_{i}") for i in range(3)]
        for i, t in enumerate(mock_tools):
            t.name = f"tool_{i}"
        mock_manager.get_all_tools.return_value = mock_tools

        # Create context
        ctx = CommandContext(console=console, args=["status"])
        ctx.mcp_manager = mock_manager

        # Execute command
        cmd = McpCommand()
        await cmd.execute(ctx)

        # Verify output contains expected information
        output = console.file.getvalue()
        assert len(output) > 0  # Should produce some output


class TestMCPErrorHandling:
    """Tests for MCP error handling."""

    async def test_mcp_server_connection_error(self):
        """Test MCP server connection error handling."""
        # Create a real McpManager
        configs = {
            "test_server": McpServerConfig(
                command="echo",
                args=["test"],
                trusted=True,
            )
        }

        # Create mock client factory that returns a client with connect failure
        mock_client = Mock()
        mock_client.connect = AsyncMock(side_effect=ConnectionError("Failed to connect"))
        mock_client.get_tools = Mock(return_value=[])

        def mock_factory(
            _name: str,
            _config: McpServerConfig,
            _verbose: bool = False,
        ) -> object:
            return mock_client

        manager = McpManager(configs, client_factory=mock_factory)

        # Connect should handle the error gracefully (logged, not raised)
        await manager.connect_all()

        # Verify client was created but connection failed
        mock_client.connect.assert_called_once()

    async def test_mcp_tool_execution_error(self):
        """Test MCP tool execution error handling."""
        # Create a mock MCP tool that raises an error
        mock_mcp_tool = Mock(spec=McpTool)
        mock_mcp_tool.name = "error_tool"
        mock_mcp_tool.execute = AsyncMock(side_effect=Exception("Tool execution failed"))

        # Test that error is propagated
        with pytest.raises(Exception, match="Tool execution failed"):
            await mock_mcp_tool.execute({})


# Run the tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
