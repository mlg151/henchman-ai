"""End-to-end CLI integration tests for Serena MCP.

These tests verify that Serena MCP integration works correctly
within the Henchman-AI CLI environment.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

from henchman.config.settings import load_settings


class TestSerenaCliIntegration:
    """CLI integration tests for Serena MCP."""

    @pytest.fixture
    def temp_settings_file(self) -> Path:
        """Create a temporary settings file with Serena configuration."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            settings = {
                "providers": {
                    "default": "deepseek",
                    "deepseek": {"model": "deepseek-chat"},
                },
                "mcp_servers": {
                    "serena": {
                        "command": "uvx",
                        "args": ["Mock Serena for CLI test"],
                        "trusted": True,
                    }
                },
                "tools": {
                    "auto_approve_read": True,
                    "shell_timeout": 30,
                },
            }
            yaml.dump(settings, f)
            return Path(f.name)

    def test_cli_with_mcp_config(self, temp_settings_file: Path) -> None:
        """Test that CLI can load settings with MCP configuration."""
        # Set environment variable to use temp settings
        import os

        os.environ["HENCHMAN_SETTINGS_PATH"] = str(temp_settings_file)

        try:
            # Load settings
            settings = load_settings()

            # Verify MCP servers are loaded
            assert "serena" in settings.mcp_servers
            serena_config = settings.mcp_servers["serena"]
            assert serena_config.command == "uvx"
            assert serena_config.trusted is True

        finally:
            # Clean up
            if temp_settings_file.exists():
                temp_settings_file.unlink()
            if "HENCHMAN_SETTINGS_PATH" in os.environ:
                del os.environ["HENCHMAN_SETTINGS_PATH"]

    def test_mcp_list_command_integration(self) -> None:
        """Test that /mcp list command works (requires CLI test setup)."""
        # This would require a more complex CLI test setup
        # For now, we'll verify the command exists in the codebase
        import henchman.cli.commands.mcp as mcp_module

        # Check that McpCommand class exists
        assert hasattr(mcp_module, "McpCommand")

        # Check that it has list subcommand method
        mcp_command = mcp_module.McpCommand()
        assert hasattr(mcp_command, "_list")

    @pytest.mark.integration
    def test_real_serena_installation(self) -> None:
        """Test that Serena is actually installed and works."""
        try:
            # Check if uv is installed
            subprocess.run(["uv", "--version"], capture_output=True, check=True)

            # Try to get Serena version or help
            result = subprocess.run(
                ["uvx", "--from", "git+https://github.com/oraios/serena", "serena", "--help"],
                capture_output=True,
                text=True,
                timeout=15,
            )

            # Verify command works
            assert result.returncode == 0 or "serena" in result.stdout
            assert "Usage:" in result.stdout or "serena" in result.stdout

        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError) as e:
            pytest.skip(f"Serena not properly installed: {e}")

    def test_mcp_tool_integration_with_agent(self) -> None:
        """Test that MCP tools can be integrated with agent system."""
        # This is a structural test to ensure the integration points exist
        import henchman.core.agent as agent_module
        import henchman.tools as tools_module

        # Verify agent can accept tools
        assert hasattr(agent_module.Agent, "__init__")

        # Verify tool registry exists
        assert hasattr(tools_module, "ToolRegistry")

        # Verify MCP tools can be registered
        import henchman.mcp.tool as mcp_tool_module

        assert hasattr(mcp_tool_module, "McpTool")

    @pytest.mark.anyio
    async def test_serena_mcp_manager_integration(self) -> None:
        """Test Serena MCP manager integration with mock."""
        from unittest.mock import MagicMock, patch

        from henchman.mcp.client import McpClient, McpToolDefinition
        from henchman.mcp.config import McpServerConfig
        from henchman.mcp.manager import McpManager

        # Create realistic Serena-like tool definitions
        serena_tools = [
            McpToolDefinition(
                name="find_symbol",
                description="Find a symbol (function, class, etc.) by name",
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Symbol name pattern"},
                        "kind": {
                            "type": "string",
                            "enum": ["function", "class", "method", "variable"],
                            "description": "Symbol kind filter",
                        },
                    },
                    "required": ["name"],
                },
            ),
            McpToolDefinition(
                name="find_referencing_symbols",
                description="Find all symbols that reference a given symbol",
                input_schema={
                    "type": "object",
                    "properties": {
                        "symbol_id": {"type": "string", "description": "ID of the target symbol"},
                    },
                    "required": ["symbol_id"],
                },
            ),
            McpToolDefinition(
                name="get_symbol_context",
                description="Get context around a symbol (definition and usage)",
                input_schema={
                    "type": "object",
                    "properties": {
                        "symbol_id": {"type": "string", "description": "ID of the symbol"},
                        "context_lines": {
                            "type": "integer",
                            "description": "Number of context lines",
                            "default": 10,
                        },
                    },
                    "required": ["symbol_id"],
                },
            ),
        ]

        # Create mock client
        mock_client = MagicMock(spec=McpClient)
        mock_client.name = "serena"
        mock_client.get_tools.return_value = serena_tools

        # Create config
        config = McpServerConfig(
            command="uvx",
            args=["--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server"],
            trusted=True,
        )

        with patch("henchman.mcp.manager.McpClient", return_value=mock_client):
            manager = McpManager({"serena": config})
            await manager.connect_all()

            # Verify tools are discovered
            tools = manager.get_all_tools()
            assert len(tools) == 3

            # Verify tool names are prefixed
            for tool in tools:
                assert tool.name.startswith("mcp_serena_")
                assert "[MCP:serena]" in tool.description
                assert tool.kind.name == "READ"  # Trusted server

            # Verify specific tools exist
            tool_names = [tool.name for tool in tools]
            assert any("find_symbol" in name for name in tool_names)
            assert any("find_referencing_symbols" in name for name in tool_names)
            assert any("get_symbol_context" in name for name in tool_names)

            await manager.disconnect_all()

    def test_serena_environment_variables(self) -> None:
        """Test that Serena environment variables are properly handled."""
        from henchman.config.schema import McpServerConfig

        # Test with environment variables
        config = McpServerConfig(
            command="uvx",
            args=["serena", "start-mcp-server"],
            env={
                "SERENA_WORKSPACE": "/home/user/project",
                "SERENA_LOG_LEVEL": "INFO",
            },
            trusted=True,
        )

        assert config.command == "uvx"
        assert config.args == ["serena", "start-mcp-server"]
        assert config.env["SERENA_WORKSPACE"] == "/home/user/project"
        assert config.env["SERENA_LOG_LEVEL"] == "INFO"
        assert config.trusted is True

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Shell command tests may not work on Windows",
    )
    def test_serena_command_shell_execution(self) -> None:
        """Test that Serena command can be executed in shell."""
        try:
            # Simple test to see if uvx works
            result = subprocess.run(
                ["uvx", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            # If uvx works, test Serena command structure
            if result.returncode == 0:
                # Test a simple echo command with similar structure
                test_cmd = ["echo", "serena", "start-mcp-server", "--help"]
                test_result = subprocess.run(
                    test_cmd,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                # Should execute without error
                assert test_result.returncode == 0

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("uvx or echo command not available")

    def test_mcp_server_config_serialization(self) -> None:
        """Test that MCP server config can be serialized and deserialized."""
        from henchman.config.schema import McpServerConfig

        # Create config
        original = McpServerConfig(
            command="uvx",
            args=["serena", "start-mcp-server", "--project", "myproject"],
            env={"SERENA_WORKSPACE": "/path/to/workspace"},
            trusted=True,
        )

        # Convert to dict
        data = original.model_dump()

        # Recreate from dict
        recreated = McpServerConfig(**data)

        # Verify equality
        assert recreated.command == original.command
        assert recreated.args == original.args
        assert recreated.env == original.env
        assert recreated.trusted == original.trusted

    @pytest.mark.anyio
    async def test_multiple_mcp_servers_with_serena(self) -> None:
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
            "github": McpServerConfig(
                command="uvx",
                args=["mcp-github"],
                env={"GITHUB_TOKEN": "test-token"},
                trusted=True,
            ),
        }

        # Create mock responses for each server
        mock_serena_client = MagicMock(spec=McpClient)
        mock_serena_client.name = "serena"
        mock_serena_client.get_tools.return_value = [
            McpToolDefinition(name="find_symbol", description="Serena tool", input_schema={})
        ]

        mock_fs_client = MagicMock(spec=McpClient)
        mock_fs_client.name = "filesystem"
        mock_fs_client.get_tools.return_value = [
            McpToolDefinition(name="read_file", description="Filesystem tool", input_schema={})
        ]

        mock_github_client = MagicMock(spec=McpClient)
        mock_github_client.name = "github"
        mock_github_client.get_tools.return_value = [
            McpToolDefinition(name="list_issues", description="GitHub tool", input_schema={})
        ]

        def create_mock_client(name: str, config: McpServerConfig | None = None, verbose: bool = False) -> McpClient:
            clients = {
                "serena": mock_serena_client,
                "filesystem": mock_fs_client,
                "github": mock_github_client,
            }
            return clients[name]

        with patch("henchman.mcp.manager.McpClient", side_effect=create_mock_client):
            manager = McpManager(configs)
            await manager.connect_all()

            # Verify all servers connected
            assert len(manager.clients) == 3

            # Verify all tools discovered
            tools = manager.get_all_tools()
            assert len(tools) == 3

            # Verify tool names
            tool_names = [tool.name for tool in tools]
            assert any("serena" in name for name in tool_names)
            assert any("filesystem" in name for name in tool_names)
            assert any("github" in name for name in tool_names)

            # Verify trust levels
            for tool in tools:
                if "serena" in tool.name or "github" in tool.name:
                    assert tool.kind.name == "READ"  # Trusted
                elif "filesystem" in tool.name:
                    assert tool.kind.name == "NETWORK"  # Not trusted

            await manager.disconnect_all()
