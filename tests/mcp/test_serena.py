"""Tests for Serena MCP integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.mcp.client import McpClient
from henchman.mcp.config import McpServerConfig
from henchman.mcp.serena import SerenaMcpClient, SerenaServerConfig


class TestSerenaServerConfig:
    """Tests for SerenaServerConfig class."""

    def test_init_defaults(self) -> None:
        """Test initialization with defaults."""
        config = SerenaServerConfig(
            workspace="/path/to/workspace",
            backend="lsp",
        )
        assert config.command == "uvx"
        assert config.args == [
            "--from",
            "git+https://github.com/oraios/serena",
            "serena",
            "start-mcp-server",
        ]
        assert config.env["SERENA_WORKSPACE"] == "/path/to/workspace"
        assert config.env["SERENA_BACKEND"] == "lsp"
        assert config.env["SERENA_LOG_LEVEL"] == "WARNING"
        assert config.trusted is True

    def test_init_custom(self) -> None:
        """Test initialization with custom values."""
        config = SerenaServerConfig(
            workspace="/custom/workspace",
            backend="jetbrains",
            log_level="INFO",
            trusted=False,
            command="custom-uvx",
            args=["custom", "args"],
        )
        assert config.command == "custom-uvx"
        assert config.args == ["custom", "args"]
        assert config.env["SERENA_WORKSPACE"] == "/custom/workspace"
        assert config.env["SERENA_BACKEND"] == "jetbrains"
        assert config.env["SERENA_LOG_LEVEL"] == "INFO"
        assert config.trusted is False

    def test_from_mcp_config_conversion(self) -> None:
        """Test conversion from McpServerConfig to SerenaServerConfig."""
        mcp_config = McpServerConfig(
            command="uvx",
            args=["--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server"],
            env={
                "SERENA_WORKSPACE": "/test/workspace",
                "SERENA_BACKEND": "lsp",
                "SERENA_LOG_LEVEL": "ERROR",
            },
            trusted=True,
        )
        
        serena_config = SerenaServerConfig.from_mcp_config("serena", mcp_config)
        assert serena_config.workspace == "/test/workspace"
        assert serena_config.backend == "lsp"
        assert serena_config.log_level == "ERROR"
        assert serena_config.trusted is True

    def test_from_mcp_config_invalid(self) -> None:
        """Test conversion fails for non-Serena config."""
        mcp_config = McpServerConfig(
            command="npx",
            args=["@anthropic-ai/mcp-filesystem-server", "/home/user"],
            env={},
            trusted=False,
        )
        
        with pytest.raises(ValueError, match="Not a Serena server configuration"):
            SerenaServerConfig.from_mcp_config("filesystem", mcp_config)


class TestSerenaMcpClient:
    """Tests for SerenaMcpClient class."""

    @pytest.fixture
    def serena_config(self) -> SerenaServerConfig:
        """Create a test Serena config."""
        return SerenaServerConfig(
            workspace="/test/workspace",
            backend="lsp",
        )

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock MCP session."""
        session = AsyncMock()
        session.initialize = AsyncMock()
        session.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
        return session

    def test_init(self, serena_config: SerenaServerConfig) -> None:
        """Test initializing Serena client."""
        client = SerenaMcpClient(name="serena", config=serena_config)
        assert client.name == "serena"
        assert isinstance(client.config, SerenaServerConfig)
        assert client.config.workspace == "/test/workspace"
        assert not client.is_connected

    @pytest.mark.anyio
    async def test_connect_disconnect(
        self, serena_config: SerenaServerConfig, mock_session: AsyncMock
    ) -> None:
        """Test connecting and disconnecting Serena client."""
        client = SerenaMcpClient(name="serena", config=serena_config)
        
        with patch("henchman.mcp.serena.stdio_client", return_value=(mock_session, AsyncMock())):
            await client.connect()
            assert client.is_connected
            
            await client.disconnect()
            assert not client.is_connected

    @pytest.mark.anyio
    async def test_get_serena_tools(
        self, serena_config: SerenaServerConfig, mock_session: AsyncMock
    ) -> None:
        """Test getting Serena-specific tools."""
        client = SerenaMcpClient(name="serena", config=serena_config)
        
        # Mock session with Serena tools
        mock_tools = MagicMock()
        mock_tools.tools = [
            MagicMock(
                name="find_symbol",
                description="Find symbols by name and kind",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "kind": {"type": "string", "enum": ["function", "class", "method"]},
                    },
                    "required": ["name"],
                },
            ),
            MagicMock(
                name="find_referencing_symbols",
                description="Find symbols that reference a given symbol",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol_id": {"type": "string"},
                    },
                    "required": ["symbol_id"],
                },
            ),
        ]
        mock_session.list_tools = AsyncMock(return_value=mock_tools)
        
        with patch("henchman.mcp.serena.stdio_client", return_value=(mock_session, AsyncMock())):
            await client.connect()
            tools = client.get_tools()
            
            assert len(tools) == 2
            assert tools[0].name == "find_symbol"
            assert tools[1].name == "find_referencing_symbols"
            
            await client.disconnect()

    @pytest.mark.anyio
    async def test_call_serena_tool(
        self, serena_config: SerenaServerConfig, mock_session: AsyncMock
    ) -> None:
        """Test calling a Serena tool."""
        client = SerenaMcpClient(name="serena", config=serena_config)
        
        # Mock tool call result
        mock_result = MagicMock()
        mock_result.content = [MagicMock(type="text", text="Found symbol: authenticate_user")]
        mock_session.call_tool = AsyncMock(return_value=mock_result)
        
        with patch("henchman.mcp.serena.stdio_client", return_value=(mock_session, AsyncMock())):
            await client.connect()
            
            result = await client.call_tool(
                "find_symbol",
                {"name": "authenticate_user", "kind": "function"}
            )
            
            assert result.content == "Found symbol: authenticate_user"
            mock_session.call_tool.assert_called_once_with(
                "find_symbol",
                arguments={"name": "authenticate_user", "kind": "function"}
            )
            
            await client.disconnect()

    def test_is_serena_tool(self) -> None:
        """Test identifying Serena tools."""
        assert SerenaMcpClient.is_serena_tool("find_symbol") is True
        assert SerenaMcpClient.is_serena_tool("find_referencing_symbols") is True
        assert SerenaMcpClient.is_serena_tool("insert_after_symbol") is True
        assert SerenaMcpClient.is_serena_tool("replace_symbol") is True
        assert SerenaMcpClient.is_serena_tool("delete_symbol") is True
        assert SerenaMcpClient.is_serena_tool("read_file") is False
        assert SerenaMcpClient.is_serena_tool("write_file") is False

    def test_get_serena_tool_categories(self) -> None:
        """Test getting Serena tool categories."""
        categories = SerenaMcpClient.get_serena_tool_categories()
        
        assert "search" in categories
        assert "navigation" in categories
        assert "editing" in categories
        assert "analysis" in categories
        
        # Check some expected tools in each category
        assert "find_symbol" in categories["search"]
        assert "find_referencing_symbols" in categories["navigation"]
        assert "insert_after_symbol" in categories["editing"]
        assert "get_symbol_info" in categories["analysis"]


class TestSerenaIntegration:
    """Integration tests for Serena MCP functionality."""

    @pytest.mark.anyio
    async def test_serena_tool_wrapper(self) -> None:
        """Test Serena tool wrapper integration."""
        from henchman.mcp.tool import McpTool
        
        serena_config = SerenaServerConfig(
            workspace="/test/workspace",
            backend="lsp",
        )
        
        client = SerenaMcpClient(name="serena", config=serena_config)
        
        # Mock tool definition
        mock_tool_def = MagicMock(
            name="find_symbol",
            description="Find symbols by name",
            inputSchema={"type": "object"},
        )
        
        # Create McpTool wrapper
        tool = McpTool(
            mcp_tool=mock_tool_def,
            client=client,
            server_name="serena",
            trusted=True,
        )
        
        assert tool.name == "find_symbol"
        assert tool.server_name == "serena"
        assert tool.trusted is True
        
        # Test tool properties
        assert tool.kind.value == "read"  # Serena tools are read-only by default
        assert "Find symbols by name" in tool.description

    @pytest.mark.anyio
    async def test_serena_in_manager(self) -> None:
        """Test Serena integration in McpManager."""
        from henchman.mcp.manager import McpManager
        
        serena_config = SerenaServerConfig(
            workspace="/test/workspace",
            backend="lsp",
        )
        
        # Convert to McpServerConfig for manager
        mcp_config = McpServerConfig(
            command=serena_config.command,
            args=serena_config.args,
            env=serena_config.env,
            trusted=serena_config.trusted,
        )
        
        manager = McpManager({"serena": mcp_config})
        
        # Check server names
        assert "serena" in manager.get_server_names()
        assert manager.is_trusted("serena") is True
        
        # Test Serena-specific environment variable handling
        assert "SERENA_WORKSPACE" in mcp_config.env
        assert mcp_config.env["SERENA_WORKSPACE"] == "/test/workspace"
        assert mcp_config.env["SERENA_LOG_LEVEL"] == "WARNING"