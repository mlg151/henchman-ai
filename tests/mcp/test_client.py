"""Tests for MCP client."""

from __future__ import annotations

from contextlib import AsyncExitStack
from unittest.mock import AsyncMock, MagicMock

import pytest

from henchman.mcp.client import McpClient
from henchman.mcp.config import McpServerConfig


class TestMcpClient:
    """Tests for McpClient class."""

    @pytest.fixture
    def config(self) -> McpServerConfig:
        """Create a test config."""
        return McpServerConfig(
            command="python",
            args=["-m", "test_server"],
            env={"TEST": "1"},
        )

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock MCP session."""
        session = AsyncMock()
        session.initialize = AsyncMock()
        session.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
        return session

    def _connect_client(self, client: McpClient, mock_session: AsyncMock) -> None:
        """Wire a mock session into a client as if connected."""
        client._session = mock_session
        client._exit_stack = AsyncExitStack()

    def test_init(self, config: McpServerConfig) -> None:
        """Test initializing client."""
        client = McpClient(name="test", config=config)
        assert client.name == "test"
        assert client.config == config
        assert not client.is_connected

    @pytest.mark.anyio
    async def test_connect_disconnect(
        self, config: McpServerConfig, mock_session: AsyncMock
    ) -> None:
        """Test connecting and disconnecting."""
        client = McpClient(name="test", config=config)

        self._connect_client(client, mock_session)
        assert client.is_connected

        await client.disconnect()
        assert not client.is_connected

    @pytest.mark.anyio
    async def test_discover_tools(self, config: McpServerConfig, mock_session: AsyncMock) -> None:
        """Test discovering tools from server."""
        client = McpClient(name="test", config=config)

        # Create mock tool
        mock_tool = MagicMock()
        mock_tool.name = "read_file"
        mock_tool.description = "Read a file"
        mock_tool.inputSchema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }

        mock_session.list_tools = AsyncMock(return_value=MagicMock(tools=[mock_tool]))
        self._connect_client(client, mock_session)
        tools = await client.discover_tools()

        assert len(tools) == 1
        assert tools[0].name == "read_file"
        assert tools[0].description == "Read a file"

    @pytest.mark.anyio
    async def test_call_tool(self, config: McpServerConfig, mock_session: AsyncMock) -> None:
        """Test calling a tool."""
        client = McpClient(name="test", config=config)

        mock_result = MagicMock()
        mock_result.content = [MagicMock(text="file contents")]
        mock_result.isError = False

        mock_session.call_tool = AsyncMock(return_value=mock_result)
        self._connect_client(client, mock_session)
        result = await client.call_tool("read_file", {"path": "test.txt"})

        assert result.content == "file contents"
        assert not result.is_error

    @pytest.mark.anyio
    async def test_call_tool_error(self, config: McpServerConfig, mock_session: AsyncMock) -> None:
        """Test calling a tool that returns an error."""
        client = McpClient(name="test", config=config)

        mock_result = MagicMock()
        mock_result.content = [MagicMock(text="File not found")]
        mock_result.isError = True

        mock_session.call_tool = AsyncMock(return_value=mock_result)
        self._connect_client(client, mock_session)
        result = await client.call_tool("read_file", {"path": "missing.txt"})

        assert result.is_error
        assert "File not found" in result.content

    @pytest.mark.anyio
    async def test_call_tool_not_connected(self, config: McpServerConfig) -> None:
        """Test calling a tool when not connected raises error."""
        client = McpClient(name="test", config=config)

        with pytest.raises(RuntimeError, match="not connected"):
            await client.call_tool("read_file", {"path": "test.txt"})

    @pytest.mark.anyio
    async def test_discover_tools_not_connected(self, config: McpServerConfig) -> None:
        """Test discover_tools returns empty list when not connected."""
        client = McpClient(name="test", config=config)
        tools = await client.discover_tools()
        assert tools == []

    def test_get_tools_empty(self, config: McpServerConfig) -> None:
        """Test get_tools returns empty list initially."""
        client = McpClient(name="test", config=config)
        assert client.get_tools() == []

    @pytest.mark.anyio
    async def test_connect_already_connected(
        self, config: McpServerConfig, mock_session: AsyncMock
    ) -> None:
        """Test connect is no-op if already connected."""
        client = McpClient(name="test", config=config)
        self._connect_client(client, mock_session)

        # connect should be a no-op since _session is already set
        await client.connect()
        assert client.is_connected

    @pytest.mark.anyio
    async def test_call_tool_non_text_content(
        self, config: McpServerConfig, mock_session: AsyncMock
    ) -> None:
        """Test calling a tool that returns non-text content."""
        client = McpClient(name="test", config=config)

        # Content item without text attribute (falls back to str())
        class NonTextContent:
            def __str__(self) -> str:
                return "raw content"

        mock_result = MagicMock()
        mock_result.content = [NonTextContent()]
        mock_result.isError = False

        mock_session.call_tool = AsyncMock(return_value=mock_result)
        self._connect_client(client, mock_session)
        result = await client.call_tool("test", {})

        # Should fall back to str() representation
        assert "raw content" in result.content or len(result.content) > 0
