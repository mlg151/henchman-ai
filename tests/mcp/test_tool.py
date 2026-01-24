"""Tests for MCP tool wrapper."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from henchman.mcp.client import McpToolDefinition, McpToolResult
from henchman.mcp.tool import McpTool
from henchman.tools.base import ToolKind


class TestMcpTool:
    """Tests for McpTool wrapper."""

    @pytest.fixture
    def mcp_tool_info(self) -> McpToolDefinition:
        """Create MCP tool definition."""
        return McpToolDefinition(
            name="read_file",
            description="Read a file from the filesystem",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to file"},
                },
                "required": ["path"],
            },
        )

    @pytest.fixture
    def client(self) -> AsyncMock:
        """Create mock client."""
        client = AsyncMock()
        client.name = "filesystem"
        return client

    def test_name(
        self, mcp_tool_info: McpToolDefinition, client: AsyncMock
    ) -> None:
        """Test tool name includes server prefix."""
        tool = McpTool(
            mcp_tool=mcp_tool_info,
            client=client,
            server_name="filesystem",
            trusted=False,
        )
        assert tool.name == "mcp_filesystem_read_file"

    def test_description(
        self, mcp_tool_info: McpToolDefinition, client: AsyncMock
    ) -> None:
        """Test tool description."""
        tool = McpTool(
            mcp_tool=mcp_tool_info,
            client=client,
            server_name="filesystem",
            trusted=False,
        )
        assert "Read a file" in tool.description
        assert "[MCP:filesystem]" in tool.description

    def test_parameters(
        self, mcp_tool_info: McpToolDefinition, client: AsyncMock
    ) -> None:
        """Test tool parameters from schema."""
        tool = McpTool(
            mcp_tool=mcp_tool_info,
            client=client,
            server_name="filesystem",
            trusted=False,
        )
        params = tool.parameters
        assert params["type"] == "object"
        assert "path" in params["properties"]

    def test_kind_untrusted(
        self, mcp_tool_info: McpToolDefinition, client: AsyncMock
    ) -> None:
        """Test untrusted server tools require confirmation."""
        tool = McpTool(
            mcp_tool=mcp_tool_info,
            client=client,
            server_name="filesystem",
            trusted=False,
        )
        assert tool.kind == ToolKind.NETWORK

    def test_kind_trusted(
        self, mcp_tool_info: McpToolDefinition, client: AsyncMock
    ) -> None:
        """Test trusted server tools are auto-approved."""
        tool = McpTool(
            mcp_tool=mcp_tool_info,
            client=client,
            server_name="github",
            trusted=True,
        )
        assert tool.kind == ToolKind.READ

    @pytest.mark.anyio
    async def test_execute(
        self, mcp_tool_info: McpToolDefinition, client: AsyncMock
    ) -> None:
        """Test executing tool."""
        mock_result = McpToolResult(content="file contents", is_error=False)
        client.call_tool = AsyncMock(return_value=mock_result)

        tool = McpTool(
            mcp_tool=mcp_tool_info,
            client=client,
            server_name="filesystem",
            trusted=False,
        )

        result = await tool.execute(path="/test/file.txt")

        assert result.content == "file contents"
        assert result.success
        client.call_tool.assert_called_once_with("read_file", {"path": "/test/file.txt"})

    @pytest.mark.anyio
    async def test_execute_error(
        self, mcp_tool_info: McpToolDefinition, client: AsyncMock
    ) -> None:
        """Test executing tool that returns error."""
        mock_result = McpToolResult(content="Error: File not found", is_error=True)
        client.call_tool = AsyncMock(return_value=mock_result)

        tool = McpTool(
            mcp_tool=mcp_tool_info,
            client=client,
            server_name="filesystem",
            trusted=False,
        )

        result = await tool.execute(path="/missing.txt")

        assert not result.success
        assert "Error" in result.content
