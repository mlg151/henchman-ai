"""MCP tool wrapper.

This module provides the McpTool class that wraps MCP server
tools as internal Tool instances.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from henchman.tools.base import ConfirmationRequest, Tool, ToolKind, ToolResult
from henchman.tools.contracts import SchemaContract

if TYPE_CHECKING:
    from henchman.mcp.client import McpClientProtocol, McpToolDefinition, McpToolResult


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
        content_blocks=copy.deepcopy(result.content_blocks),
        structured_content=copy.deepcopy(result.structured_content),
        structured_content_present=result.structured_content_present,
        metadata=copy.deepcopy(result.metadata),
    )


class McpTool(Tool):
    """Wrapper for an MCP server tool.

    Adapts MCP tools to the internal Tool ABC interface.
    """

    def __init__(
        self: McpTool,
        mcp_tool: McpToolDefinition,
        client: McpClientProtocol,
        server_name: str,
        *,
        trusted: bool = False,
        before_call: Callable[[], None] | None = None,
    ) -> None:
        """Initialize the tool wrapper.

        Args:
            mcp_tool: MCP tool definition.
            client: MCP client for execution.
            server_name: Name of the MCP server.
            trusted: Whether the server is trusted.
        """
        super().__init__()
        self._mcp_tool = copy.deepcopy(mcp_tool)
        self._client = client
        self._server_name = server_name
        self._trusted = trusted
        self._before_call = before_call
        generation = getattr(client, "catalog_generation", None)
        self._catalog_generation = generation if type(generation) is int else None

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
        return copy.deepcopy(self._mcp_tool.input_schema)

    @property
    def output_schema(self) -> dict[str, Any] | None:
        """Return detached untrusted output contract metadata."""
        return copy.deepcopy(self._mcp_tool.output_schema)

    @property
    def annotations(self) -> dict[str, Any]:
        """Return metadata hints which never change execution authority."""
        return copy.deepcopy(self._mcp_tool.annotations)

    @property
    def kind(self: McpTool) -> ToolKind:
        """Catalog tool kind based on trust level.

        Trusted servers get READ kind (auto-approved locally).
        Untrusted servers get NETWORK kind (requires confirmation).

        Returns:
            Tool kind.
        """
        if self._trusted:
            return ToolKind.READ
        return ToolKind.NETWORK

    def execution_kind(self: McpTool, params: dict[str, object]) -> ToolKind:
        """Classify this invocation conservatively as a remote call.

        Trust controls local confirmation, not effect: an MCP server tool can
        perform remote or local side effects the local runtime cannot see.
        Every MCP tool call therefore carries the conservative NETWORK
        classification, so Plan Mode blocks it even when the server is
        trusted.
        """
        del params
        return ToolKind.NETWORK

    def needs_confirmation(self: McpTool, params: dict[str, object]) -> ConfirmationRequest | None:
        """Confirmation policy that preserves trusted-server auto-approval.

        Trusted servers skip confirmation exactly as before; untrusted
        servers keep the standard NETWORK confirmation request.
        """
        if self._trusted:
            return None
        return super().needs_confirmation(params)

    async def execute(self: McpTool, **params: object) -> ToolResult:
        """Execute the tool via MCP.

        Args:
            params: Tool parameters as keyword arguments. Passed directly
                to the MCP server tool.

        Returns:
            Tool execution result.
        """
        arguments: dict[str, Any] = dict(params)
        if self._catalog_generation is not None and getattr(self._client, "catalog_generation", None) != self._catalog_generation:
            raise RuntimeError("MCP catalog changed; resolve a current tool before dispatch")
        if self._before_call is not None:
            self._before_call()
        SchemaContract(self._mcp_tool.input_schema).validate(arguments)
        result = await self._client.call_tool(
            self._mcp_tool.name,
            arguments,
        )

        return _build_tool_result(result)
