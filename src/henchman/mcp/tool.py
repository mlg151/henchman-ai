"""MCP tool wrapper.

This module provides the McpTool class that wraps MCP server
tools as internal Tool instances.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from henchman.tools.base import Tool, ToolKind, ToolResult

if TYPE_CHECKING:
    from henchman.mcp.client import McpClient, McpToolDefinition, McpToolResult


def _build_tool_result(result: McpToolResult) -> ToolResult:
    """Build a ToolResult from a raw MCP call result.

    Extracts content, success flag, and error message from the MCP
    response into the internal ToolResult format.

    Args:
        result: Raw MCP tool call result.

    Returns:
        Normalized ToolResult.
    """
    return ToolResult(
        content=result.content,
        success=not result.is_error,
        error=result.content if result.is_error else None,
    )


class McpTool(Tool):
    """Wrapper for an MCP server tool.

    Adapts MCP tools to the internal Tool ABC interface.
    """

    def __init__(
        self: McpTool,
        mcp_tool: McpToolDefinition,
        client: McpClient,
        server_name: str,
        *,
        trusted: bool = False,
    ) -> None:
        """Initialize the tool wrapper.

        Args:
            mcp_tool: MCP tool definition.
            client: MCP client for execution.
            server_name: Name of the MCP server.
            trusted: Whether the server is trusted.
        """
        super().__init__()
        self._mcp_tool = mcp_tool
        self._client = client
        self._server_name = server_name
        self._trusted = trusted

    @property
    def name(self: McpTool) -> str:
        """Tool name with server prefix.

        Returns:
            Prefixed tool name.
        """
        return f"mcp_{self._server_name}_{self._mcp_tool.name}"

    @property
    def description(self: McpTool) -> str:
        """Tool description with server info.

        Returns:
            Description string.
        """
        server_tag = f"[MCP:{self._server_name}]"
        return f"{server_tag} {self._mcp_tool.description}"

    @property
    def parameters(self: McpTool) -> dict[str, object]:
        """Tool parameters from MCP schema.

        Returns:
            JSON schema for parameters.
        """
        return dict(self._mcp_tool.input_schema)

    @property
    def kind(self: McpTool) -> ToolKind:
        """Tool kind based on trust level.

        Trusted servers get READ kind (auto-approved).
        Untrusted servers get NETWORK kind (requires confirmation).

        Returns:
            Tool kind.
        """
        if self._trusted:
            return ToolKind.READ
        return ToolKind.NETWORK

    async def execute(self: McpTool, **params: object) -> ToolResult:
        """Execute the tool via MCP.

        Args:
            params: Tool parameters as keyword arguments. Passed directly
                to the MCP server tool.

        Returns:
            Tool execution result.
        """
        arguments: dict[str, Any] = dict(params)

        result = await self._client.call_tool(
            self._mcp_tool.name,
            arguments,
        )

        return _build_tool_result(result)
