"""Tests for MCP manager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.mcp.config import McpServerConfig
from henchman.mcp.manager import McpManager


class TestMcpManager:
    """Tests for McpManager class."""

    @pytest.fixture
    def configs(self) -> dict[str, McpServerConfig]:
        """Create test server configs."""
        return {
            "filesystem": McpServerConfig(
                command="npx",
                args=["@anthropic-ai/mcp-filesystem-server", "/home"],
                trusted=False,
            ),
            "github": McpServerConfig(
                command="uvx",
                args=["mcp-github"],
                env={"GITHUB_TOKEN": "token123"},
                trusted=True,
            ),
        }

    def test_init(self, configs: dict[str, McpServerConfig]) -> None:
        """Test initializing manager."""
        manager = McpManager(configs)
        assert len(manager.configs) == 2
        assert "filesystem" in manager.configs
        assert "github" in manager.configs

    def test_init_empty(self) -> None:
        """Test initializing with no configs."""
        manager = McpManager({})
        assert len(manager.configs) == 0

    def test_get_server_names(self, configs: dict[str, McpServerConfig]) -> None:
        """Test getting server names."""
        manager = McpManager(configs)
        names = manager.get_server_names()
        assert set(names) == {"filesystem", "github"}

    @pytest.mark.anyio
    async def test_connect_all(self, configs: dict[str, McpServerConfig]) -> None:
        """Test connecting to all servers."""
        manager = McpManager(configs)

        with patch("henchman.mcp.manager.McpClient") as MockClient:
            mock_client = MagicMock()
            mock_client.connect = AsyncMock()
            mock_client.get_tools = MagicMock(return_value=[])
            MockClient.return_value = mock_client

            await manager.connect_all()

            assert MockClient.call_count == 2
            assert mock_client.connect.call_count == 2

    @pytest.mark.anyio
    async def test_disconnect_all(self, configs: dict[str, McpServerConfig]) -> None:
        """Test disconnecting from all servers."""
        manager = McpManager(configs)

        with patch("henchman.mcp.manager.McpClient") as MockClient:
            mock_client = MagicMock()
            mock_client.connect = AsyncMock()
            mock_client.disconnect = AsyncMock()
            mock_client.get_tools = MagicMock(return_value=[])
            MockClient.return_value = mock_client

            await manager.connect_all()
            await manager.disconnect_all()

            assert mock_client.disconnect.call_count == 2

    @pytest.mark.anyio
    async def test_get_all_tools(self, configs: dict[str, McpServerConfig]) -> None:
        """Test getting all tools from all servers."""
        manager = McpManager(configs)

        mock_tool1 = MagicMock()
        mock_tool1.name = "read_file"
        mock_tool1.description = "Read a file"
        mock_tool1.input_schema = {}
        mock_tool2 = MagicMock()
        mock_tool2.name = "list_issues"
        mock_tool2.description = "List issues"
        mock_tool2.input_schema = {}

        with patch("henchman.mcp.manager.McpClient") as MockClient:
            # Different tools for different servers
            mock_client1 = MagicMock()
            mock_client1.name = "filesystem"
            mock_client1.connect = AsyncMock()
            mock_client1.get_tools = MagicMock(return_value=[mock_tool1])

            mock_client2 = MagicMock()
            mock_client2.name = "github"
            mock_client2.connect = AsyncMock()
            mock_client2.get_tools = MagicMock(return_value=[mock_tool2])

            clients = [mock_client1, mock_client2]
            MockClient.side_effect = clients

            await manager.connect_all()
            tools = manager.get_all_tools()

            assert len(tools) == 2

    @pytest.mark.anyio
    async def test_call_tool(self, configs: dict[str, McpServerConfig]) -> None:
        """Test calling a tool through manager."""
        manager = McpManager(configs)

        mock_tool = MagicMock()
        mock_tool.name = "read_file"

        mock_result = MagicMock()
        mock_result.content = "file contents"
        mock_result.is_error = False

        with patch("henchman.mcp.manager.McpClient") as MockClient:
            mock_client = MagicMock()
            mock_client.name = "filesystem"
            mock_client.connect = AsyncMock()
            mock_client.get_tools = MagicMock(return_value=[mock_tool])
            mock_client.call_tool = AsyncMock(return_value=mock_result)
            MockClient.return_value = mock_client

            await manager.connect_all()
            result = await manager.call_tool("filesystem", "read_file", {"path": "test"})

            assert result.content == "file contents"

    @pytest.mark.anyio
    async def test_call_tool_unknown_server(
        self, configs: dict[str, McpServerConfig]
    ) -> None:
        """Test calling a tool on unknown server raises error."""
        manager = McpManager(configs)

        with pytest.raises(KeyError):
            await manager.call_tool("unknown", "tool", {})

    def test_is_trusted(self, configs: dict[str, McpServerConfig]) -> None:
        """Test checking if server is trusted."""
        manager = McpManager(configs)
        assert not manager.is_trusted("filesystem")
        assert manager.is_trusted("github")

    def test_is_trusted_unknown_server(
        self, configs: dict[str, McpServerConfig]
    ) -> None:
        """Test is_trusted returns False for unknown server."""
        manager = McpManager(configs)
        assert not manager.is_trusted("unknown")
