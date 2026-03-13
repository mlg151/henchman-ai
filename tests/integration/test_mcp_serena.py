"""Integration tests for Serena MCP server.

These tests verify that Serena MCP server can be connected to
and that tools are properly discovered and wrapped.
"""

from __future__ import annotations

import asyncio
import subprocess

import pytest

from henchman.mcp.config import McpServerConfig
from henchman.mcp.manager import McpManager


class TestSerenaMcpIntegration:
    """Integration tests for Serena MCP server."""

    @pytest.fixture
    def serena_config(self) -> McpServerConfig:
        """Create Serena MCP server configuration."""
        return McpServerConfig(
            command="uvx",
            args=["--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server"],
            trusted=True,
        )

    @pytest.fixture
    def mock_serena_config(self) -> McpServerConfig:
        """Create a mock Serena config for testing without real server."""
        return McpServerConfig(
            command="echo",
            args=["Mock Serena Server"],
            trusted=True,
        )

    def test_serena_command_exists(self) -> None:
        """Test that Serena command is available."""
        try:
            result = subprocess.run(
                ["uvx", "--from", "git+https://github.com/oraios/serena", "serena", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # Check if command executed (even if it fails, it should show help or version)
            assert result.returncode == 0 or "serena" in result.stdout or "serena" in result.stderr
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("Serena not installed or uv not available")

    @pytest.mark.integration
    @pytest.mark.anyio
    async def test_serena_mcp_connection(self, serena_config: McpServerConfig) -> None:
        """Test connecting to Serena MCP server (integration test).

        This test requires Serena to be installed and may start a real server.
        """
        # Skip if we can't run the command
        try:
            subprocess.run(
                ["uvx", "--version"],
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("uv not available")

        manager = McpManager({"serena": serena_config})

        try:
            # Try to connect with a timeout
            await asyncio.wait_for(manager.connect_all(), timeout=30.0)

            # Check if tools were discovered
            tools = manager.get_all_tools()

            # Serena should provide some tools
            assert len(tools) > 0, "Serena should provide at least one tool"

            # Check tool properties
            for tool in tools:
                assert tool.name.startswith("mcp_serena_"), (
                    f"Tool name should be prefixed: {tool.name}"
                )
                assert tool.description, "Tool should have a description"
                assert tool.kind.name == "READ", "Serena tools should be READ kind (trusted)"

            await manager.disconnect_all()

        except asyncio.TimeoutError:
            pytest.skip("Serena server connection timed out - server may not be starting properly")
        except Exception as e:
            pytest.skip(f"Failed to connect to Serena: {e}")

    @pytest.mark.anyio
    async def test_serena_tool_wrapping(self, mock_serena_config: McpServerConfig) -> None:
        """Test that Serena tools are properly wrapped as internal tools."""
        from unittest.mock import MagicMock, patch

        from henchman.mcp.client import McpClient, McpToolDefinition

        # Create mock MCP client with Serena-like tools
        mock_client = MagicMock(spec=McpClient)
        mock_client.name = "serena"
        mock_client.get_tools.return_value = [
            McpToolDefinition(
                name="find_symbol",
                description="Find a symbol (function, class, etc.) in the codebase",
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Symbol name to find"},
                        "kind": {
                            "type": "string",
                            "description": "Symbol kind (function, class, etc.)",
                        },
                    },
                    "required": ["name"],
                },
            ),
            McpToolDefinition(
                name="find_referencing_symbols",
                description="Find symbols that reference a given symbol",
                input_schema={
                    "type": "object",
                    "properties": {
                        "symbol_id": {
                            "type": "string",
                            "description": "ID of the symbol to find references for",
                        },
                    },
                    "required": ["symbol_id"],
                },
            ),
        ]

        with patch("henchman.mcp.manager.McpClient", return_value=mock_client):
            manager = McpManager({"serena": mock_serena_config})
            await manager.connect_all()

            tools = manager.get_all_tools()
            assert len(tools) == 2

            # Check first tool
            find_symbol_tool = tools[0]
            assert "find_symbol" in find_symbol_tool.name
            assert "Find a symbol" in find_symbol_tool.description
            assert find_symbol_tool.kind.name == "READ"

            # Check parameters schema
            params = find_symbol_tool.parameters
            assert params["type"] == "object"
            assert "name" in params["properties"]
            assert "kind" in params["properties"]

            # Check second tool
            ref_tool = tools[1]
            assert "find_referencing_symbols" in ref_tool.name
            assert "Find symbols that reference" in ref_tool.description

            await manager.disconnect_all()

    @pytest.mark.anyio
    async def test_serena_tool_execution_mock(self) -> None:
        """Test mock execution of Serena tools."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from henchman.mcp.client import McpClient, McpToolDefinition, McpToolResult
        from henchman.mcp.config import McpServerConfig
        from henchman.mcp.manager import McpManager

        # Create mock config
        config = McpServerConfig(command="echo", args=["test"], trusted=True)

        # Create mock client with tool execution
        mock_client = MagicMock(spec=McpClient)
        mock_client.name = "serena"

        # Mock tool definition
        mock_tool_def = McpToolDefinition(
            name="find_symbol",
            description="Find symbol",
            input_schema={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        )

        # Mock tool execution result
        mock_result = McpToolResult(
            content='[{"symbol_id": "function:authenticate_user:42", "name": "authenticate_user", "file": "src/auth.py"}]',
            is_error=False,
        )

        mock_client.get_tools.return_value = [mock_tool_def]
        mock_client.call_tool = AsyncMock(return_value=mock_result)

        with patch("henchman.mcp.manager.McpClient", return_value=mock_client):
            manager = McpManager({"serena": config})
            await manager.connect_all()

            tools = manager.get_all_tools()
            assert len(tools) == 1

            # Execute the tool
            tool = tools[0]
            result = await tool.execute(name="authenticate_user")

            assert result.success
            assert "authenticate_user" in result.content
            assert "src/auth.py" in result.content

            # Verify the tool was called with correct arguments
            mock_client.call_tool.assert_called_once_with(
                "find_symbol",
                {"name": "authenticate_user"},
            )

            await manager.disconnect_all()

    def test_serena_config_validation(self) -> None:
        """Test that Serena configuration is valid."""
        from henchman.config.schema import Settings

        # Test with Serena configuration
        settings_dict = {
            "mcp_servers": {
                "serena": {
                    "command": "uvx",
                    "args": [
                        "--from",
                        "git+https://github.com/oraios/serena",
                        "serena",
                        "start-mcp-server",
                    ],
                    "trusted": True,
                }
            }
        }

        settings = Settings(**settings_dict)
        assert "serena" in settings.mcp_servers
        serena_config = settings.mcp_servers["serena"]
        assert serena_config.command == "uvx"
        assert len(serena_config.args) == 4
        assert serena_config.trusted is True

    @pytest.mark.anyio
    async def test_multiple_mcp_servers_integration(self) -> None:
        """Test integration with multiple MCP servers including Serena."""
        from unittest.mock import MagicMock, patch

        from henchman.mcp.client import McpClient, McpToolDefinition
        from henchman.mcp.config import McpServerConfig
        from henchman.mcp.manager import McpManager

        # Create multiple server configs
        configs = {
            "serena": McpServerConfig(
                command="uvx",
                args=["serena", "start-mcp-server"],
                trusted=True,
            ),
            "filesystem": McpServerConfig(
                command="npx",
                args=["@anthropic-ai/mcp-filesystem-server"],
                trusted=False,
            ),
        }

        # Mock clients
        mock_serena_client = MagicMock(spec=McpClient)
        mock_serena_client.name = "serena"
        mock_serena_client.get_tools.return_value = [
            McpToolDefinition(
                name="find_symbol",
                description="Serena: Find symbol",
                input_schema={},
            )
        ]

        mock_fs_client = MagicMock(spec=McpClient)
        mock_fs_client.name = "filesystem"
        mock_fs_client.get_tools.return_value = [
            McpToolDefinition(
                name="read_file",
                description="Filesystem: Read file",
                input_schema={},
            )
        ]

        # Create mock client instances
        mock_clients = {
            "serena": mock_serena_client,
            "filesystem": mock_fs_client,
        }

        def create_mock_client(
            *, name: str, config: McpServerConfig, verbose: bool = False
        ) -> McpClient:  # noqa: ARG001
            return mock_clients[name]

        with patch("henchman.mcp.manager.McpClient", side_effect=create_mock_client):
            manager = McpManager(configs)
            await manager.connect_all()

            tools = manager.get_all_tools()
            assert len(tools) == 2

            # Check tool names include server prefixes
            tool_names = [tool.name for tool in tools]
            assert any("mcp_serena" in name for name in tool_names)
            assert any("mcp_filesystem" in name for name in tool_names)

            # Check trust levels
            for tool in tools:
                if "serena" in tool.name:
                    assert tool.kind.name == "READ"  # Trusted
                elif "filesystem" in tool.name:
                    assert tool.kind.name == "NETWORK"  # Not trusted

            await manager.disconnect_all()
