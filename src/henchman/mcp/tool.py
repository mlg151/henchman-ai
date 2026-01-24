"""MCP tool wrapper.

This module provides the McpTool class that wraps MCP server
tools as internal Tool instances.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from henchman.tools.base import Tool, ToolKind, ToolResult

if TYPE_CHECKING:
    from henchman.mcp.client import McpClient, McpToolDefinition


class McpTool(Tool):
    """Wrapper for an MCP server tool.

    Adapts MCP tools to the internal Tool ABC interface.
    """

    def __init__(
        self,
        mcp_tool: McpToolDefinition,
        client: McpClient,
        server_name: str,
        trusted: bool = False,
    ) -> None:
        """Initialize the tool wrapper.

        Args:
            mcp_tool: MCP tool definition.
            client: MCP client for execution.
            server_name: Name of the MCP server.
            trusted: Whether the server is trusted.
        """
        self._mcp_tool = mcp_tool
        self._client = client
        self._server_name = server_name
        self._trusted = trusted

    @property
    def name(self) -> str:
        """Tool name with server prefix.

        Returns:
            Prefixed tool name.
        """
        return f"mcp_{self._server_name}_{self._mcp_tool.name}"

    @property
    def description(self) -> str:
        """Tool description with server info.

        Returns:
            Description string.
        """
        return f"[MCP:{self._server_name}] {self._mcp_tool.description}"

    @property
    def parameters(self) -> dict[str, object]:
        """Tool parameters from MCP schema.

        Returns:
            JSON schema for parameters.
        """
        return dict(self._mcp_tool.input_schema)

    @property
    def kind(self) -> ToolKind:
        """Tool kind based on trust level.

        Trusted servers get READ kind (auto-approved).
        Untrusted servers get NETWORK kind (requires confirmation).

        Returns:
            Tool kind.
        """
        if self._trusted:
            return ToolKind.READ
        return ToolKind.NETWORK

    async def execute(self, **params: object) -> ToolResult:
        """Execute the tool via MCP.

        Args:
            **params: Tool parameters.

        Returns:
            Tool execution result.
        """
        # Convert params to dict[str, Any]
        arguments: dict[str, Any] = dict(params)

        result = await self._client.call_tool(
            self._mcp_tool.name,
            arguments,
        )

        return ToolResult(
            content=result.content,
            success=not result.is_error,
            error=result.content if result.is_error else None,
        )
