"""End-to-end tests for MCP server integration.

These tests simulate real usage scenarios with MCP servers
including Serena, filesystem, and other servers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from henchman.mcp.config import McpServerConfig
from henchman.mcp.manager import McpManager
from henchman.tools.registry import ToolRegistry


class TestMcpEndToEnd:
    """End-to-end tests for MCP integration."""

    @pytest.fixture
    def sample_settings_with_mcp(self, tmp_path: Path) -> dict[str, Any]:
        """Create sample settings with MCP server configurations."""
        return {
            "providers": {
                "default": "deepseek",
                "deepseek": {"model": "deepseek-chat"},
            },
            "mcp_servers": {
                "serena": {
                    "command": "echo",
                    "args": ["Mock Serena MCP Server"],
                    "trusted": True,
                },
                "filesystem": {
                    "command": "echo",
                    "args": ["Mock Filesystem MCP Server"],
                    "trusted": False,
                },
            },
            "tools": {
                "auto_approve_read": True,
                "shell_timeout": 60,
            },
        }

    @pytest.mark.anyio
    async def test_mcp_tools_in_registry(self) -> None:
        """Test that MCP tools are properly registered in the tool registry."""
        from unittest.mock import MagicMock, patch

        from henchman.mcp.client import McpClient, McpToolDefinition
        from henchman.mcp.config import McpServerConfig

        # Create mock MCP manager with tools
        mock_tool_def1 = McpToolDefinition(
            name="find_symbol",
            description="Find a symbol in codebase",
            input_schema={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        )

        mock_tool_def2 = McpToolDefinition(
            name="read_file",
            description="Read a file",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        )

        mock_client1 = MagicMock(spec=McpClient)
        mock_client1.name = "serena"
        mock_client1.get_tools.return_value = [mock_tool_def1]

        mock_client2 = MagicMock(spec=McpClient)
        mock_client2.name = "filesystem"
        mock_client2.get_tools.return_value = [mock_tool_def2]

        def create_mock_client(
            name: str, config: McpServerConfig | None = None, verbose: bool = False
        ) -> McpClient:
            if name == "serena":
                return mock_client1
            else:
                return mock_client2

        configs = {
            "serena": McpServerConfig(command="echo", args=["test"], trusted=True),
            "filesystem": McpServerConfig(command="echo", args=["test"], trusted=False),
        }

        with patch("henchman.mcp.manager.McpClient", side_effect=create_mock_client):
            # Create MCP manager and connect
            mcp_manager = McpManager(configs)
            await mcp_manager.connect_all()

            # Create tool registry and register MCP tools
            registry = ToolRegistry()

            # Get all MCP tools and register them
            mcp_tools = mcp_manager.get_all_tools()
            for tool in mcp_tools:
                registry.register(tool)

            # Verify tools are in registry
            declarations = registry.get_declarations()
            assert len(declarations) == 2

            # Check tool names
            tool_names = [decl.name for decl in declarations]
            assert any("mcp_serena_find_symbol" in name for name in tool_names)
            assert any("mcp_filesystem_read_file" in name for name in tool_names)

            # Check tool descriptions
            for decl in declarations:
                assert "MCP:" in decl.description

            await mcp_manager.disconnect_all()

    @pytest.mark.anyio
    async def test_mcp_tool_execution_flow(self) -> None:
        """Test the complete flow of MCP tool execution."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from henchman.mcp.client import McpClient, McpToolDefinition, McpToolResult
        from henchman.mcp.config import McpServerConfig

        # Setup mock MCP server response
        mock_result = McpToolResult(
            content=json.dumps(
                [
                    {
                        "symbol_id": "function:calculate_total:15",
                        "name": "calculate_total",
                        "file": "src/calculator.py",
                        "line": 15,
                    }
                ]
            ),
            is_error=False,
        )

        # Create mock client
        mock_client = MagicMock(spec=McpClient)
        mock_client.name = "serena"
        mock_client.call_tool = AsyncMock(return_value=mock_result)

        mock_tool_def = McpToolDefinition(
            name="find_symbol",
            description="Find symbol in codebase",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "kind": {"type": "string", "default": "function"},
                },
                "required": ["name"],
            },
        )
        mock_client.get_tools.return_value = [mock_tool_def]

        # Create MCP manager with mock
        config = McpServerConfig(command="echo", args=["test"], trusted=True)

        with patch("henchman.mcp.manager.McpClient", return_value=mock_client):
            mcp_manager = McpManager({"serena": config})
            await mcp_manager.connect_all()

            # Get the MCP tool wrapper
            mcp_tools = mcp_manager.get_all_tools()
            assert len(mcp_tools) == 1

            tool = mcp_tools[0]

            # Execute the tool
            result = await tool.execute(
                name="calculate_total",
                kind="function",
            )

            # Verify execution
            assert result.success
            assert "calculate_total" in result.content
            assert "src/calculator.py" in result.content

            # Verify the MCP client was called correctly
            mock_client.call_tool.assert_called_once_with(
                "find_symbol",
                {"name": "calculate_total", "kind": "function"},
            )

            await mcp_manager.disconnect_all()

    @pytest.mark.anyio
    async def test_mcp_tool_error_handling(self) -> None:
        """Test error handling for MCP tool execution."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from henchman.mcp.client import McpClient, McpToolDefinition, McpToolResult
        from henchman.mcp.config import McpServerConfig

        # Setup error response
        mock_result = McpToolResult(
            content="Symbol not found: unknown_function",
            is_error=True,
        )

        # Create mock client
        mock_client = MagicMock(spec=McpClient)
        mock_client.name = "serena"
        mock_client.call_tool = AsyncMock(return_value=mock_result)

        mock_tool_def = McpToolDefinition(
            name="find_symbol",
            description="Find symbol",
            input_schema={"type": "object", "properties": {"name": {"type": "string"}}},
        )
        mock_client.get_tools.return_value = [mock_tool_def]

        # Create MCP manager
        config = McpServerConfig(command="echo", args=["test"], trusted=True)

        with patch("henchman.mcp.manager.McpClient", return_value=mock_client):
            mcp_manager = McpManager({"serena": config})
            await mcp_manager.connect_all()

            mcp_tools = mcp_manager.get_all_tools()
            tool = mcp_tools[0]

            # Execute tool that returns error
            result = await tool.execute(name="unknown_function")

            # Verify error handling
            assert not result.success
            assert result.error == "Symbol not found: unknown_function"
            assert "unknown_function" in result.content

            await mcp_manager.disconnect_all()

    @pytest.mark.anyio
    async def test_mcp_server_connection_failure(self) -> None:
        """Test handling of MCP server connection failures."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from henchman.mcp.client import McpClient
        from henchman.mcp.config import McpServerConfig

        # Create configs for multiple servers
        configs = {
            "serena": McpServerConfig(command="echo", args=["working"], trusted=True),
            "failing": McpServerConfig(command="nonexistent", args=["command"], trusted=False),
        }

        # Mock successful client
        mock_serena_client = MagicMock(spec=McpClient)
        mock_serena_client.name = "serena"
        mock_serena_client.connect = AsyncMock()
        mock_serena_client.get_tools.return_value = []

        # Mock failing client
        mock_failing_client = MagicMock(spec=McpClient)
        mock_failing_client.name = "failing"
        mock_failing_client.connect = AsyncMock(side_effect=Exception("Connection failed"))

        def create_mock_client(name: str, config: McpServerConfig | None = None, verbose: bool = False) -> McpClient:
            if name == "serena":
                return mock_serena_client
            else:
                return mock_failing_client

        with patch("henchman.mcp.manager.McpClient", side_effect=create_mock_client):
            manager = McpManager(configs)

            # Should not raise even if one server fails
            await manager.connect_all()

            # Should have connected to successful server
            assert "serena" in manager.clients
            assert "failing" not in manager.clients

            # Should have some tools (even if empty list)
            tools = manager.get_all_tools()
            assert isinstance(tools, list)

            await manager.disconnect_all()

    def test_mcp_config_from_settings(self, sample_settings_with_mcp: dict[str, Any]) -> None:
        """Test loading MCP configuration from settings."""
        from henchman.config.schema import Settings

        settings = Settings(**sample_settings_with_mcp)

        # Verify MCP servers are loaded
        assert len(settings.mcp_servers) == 2
        assert "serena" in settings.mcp_servers
        assert "filesystem" in settings.mcp_servers

        # Verify Serena configuration
        serena_config = settings.mcp_servers["serena"]
        assert serena_config.command == "echo"
        assert serena_config.args == ["Mock Serena MCP Server"]
        assert serena_config.trusted is True

        # Verify filesystem configuration
        fs_config = settings.mcp_servers["filesystem"]
        assert fs_config.command == "echo"
        assert fs_config.args == ["Mock Filesystem MCP Server"]
        assert fs_config.trusted is False

    @pytest.mark.anyio
    async def test_mcp_tool_auto_approval_based_on_trust(self) -> None:
        """Test that tool auto-approval works based on server trust level."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from henchman.mcp.client import McpClient, McpToolDefinition
        from henchman.mcp.config import McpServerConfig
        from henchman.tools.base import ToolKind

        # Create trusted and untrusted servers
        configs = {
            "trusted_server": McpServerConfig(command="echo", args=["test"], trusted=True),
            "untrusted_server": McpServerConfig(command="echo", args=["test"], trusted=False),
        }

        # Create mock clients with async connect method
        mock_trusted_client = MagicMock(spec=McpClient)
        mock_trusted_client.name = "trusted_server"
        mock_trusted_client.connect = AsyncMock()
        mock_trusted_client.get_tools.return_value = [
            McpToolDefinition(name="safe_tool", description="Safe tool", input_schema={})
        ]

        mock_untrusted_client = MagicMock(spec=McpClient)
        mock_untrusted_client.name = "untrusted_server"
        mock_untrusted_client.connect = AsyncMock()
        mock_untrusted_client.get_tools.return_value = [
            McpToolDefinition(name="unsafe_tool", description="Unsafe tool", input_schema={})
        ]

        def create_mock_client(name: str, config: McpServerConfig | None = None, verbose: bool = False) -> McpClient:
            if name == "trusted_server":
                return mock_trusted_client
            else:
                return mock_untrusted_client

        with patch("henchman.mcp.manager.McpClient", side_effect=create_mock_client):
            manager = McpManager(configs)
            await manager.connect_all()

            tools = manager.get_all_tools()
            assert len(tools) == 2

            # Check tool kinds based on trust
            for tool in tools:
                if "mcp_trusted_server" in tool.name:
                    assert tool.kind == ToolKind.READ  # Auto-approved
                elif "mcp_untrusted_server" in tool.name:
                    assert tool.kind == ToolKind.NETWORK  # Requires confirmation

            await manager.disconnect_all()

    @pytest.mark.anyio
    async def test_real_serena_help_command(self) -> None:
        """Test that real Serena help command works (integration test)."""
        import subprocess

        try:
            # Try to run Serena help command
            result = subprocess.run(
                ["uvx", "--from", "git+https://github.com/oraios/serena", "serena", "--help"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            # Command should execute (even if it shows help)
            assert result.returncode == 0 or "serena" in result.stdout or "serena" in result.stderr
            assert "Usage:" in result.stdout or "serena" in result.stdout

        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
            pytest.skip("Serena not available for real integration test")
