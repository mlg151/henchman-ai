"""MCP client for connecting to a single server.

This module provides the McpClient class for managing
a connection to an MCP server.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from henchman.mcp.config import McpServerConfig

if TYPE_CHECKING:
    from mcp.client.session import ClientSession


@dataclass
class McpToolResult:
    """Result from an MCP tool call.

    Attributes:
        content: The result content.
        is_error: Whether the result is an error.
    """

    content: str
    is_error: bool = False


@dataclass
class McpToolDefinition:
    """Definition of an MCP tool.

    Attributes:
        name: Tool name.
        description: Tool description.
        input_schema: JSON schema for tool parameters.
    """

    name: str
    description: str
    input_schema: dict[str, Any]


class McpClient:
    """Client for a single MCP server.

    Manages the connection lifecycle and tool discovery/execution.
    """

    def __init__(self, name: str, config: McpServerConfig) -> None:
        """Initialize the client.

        Args:
            name: Server name.
            config: Server configuration.
        """
        self.name = name
        self.config = config
        self._session: ClientSession | None = None
        self._tools: list[McpToolDefinition] = []

    @property
    def is_connected(self) -> bool:
        """Check if connected to server."""
        return self._session is not None

    async def _create_session(self) -> ClientSession:  # pragma: no cover
        """Create the MCP client session.

        This method requires a real MCP server and is excluded from
        unit test coverage. It is tested via integration tests.

        Returns:
            ClientSession connected to the server.
        """
        from mcp.client.stdio import stdio_client

        from mcp import ClientSession, StdioServerParameters

        server_params = StdioServerParameters(
            command=self.config.command,
            args=self.config.args,
            env=self.config.env if self.config.env else None,
        )

        # Create the stdio transport
        read, write = await stdio_client(server_params).__aenter__()

        # Create and initialize session
        session = ClientSession(read, write)
        return session

    async def connect(self) -> None:
        """Connect to the MCP server."""
        if self._session is not None:
            return

        self._session = await self._create_session()
        await self._session.initialize()

        # Discover tools on connect
        await self.discover_tools()

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        self._session = None
        self._tools = []

    async def discover_tools(self) -> list[McpToolDefinition]:
        """Discover tools from the server.

        Returns:
            List of tool definitions.
        """
        if self._session is None:
            return []

        result = await self._session.list_tools()
        self._tools = [
            McpToolDefinition(
                name=tool.name,
                description=tool.description or "",
                input_schema=dict(tool.inputSchema) if tool.inputSchema else {},
            )
            for tool in result.tools
        ]
        return self._tools

    def get_tools(self) -> list[McpToolDefinition]:
        """Get cached tool definitions.

        Returns:
            List of tool definitions.
        """
        return self._tools

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> McpToolResult:
        """Call a tool on the server.

        Args:
            name: Tool name.
            arguments: Tool arguments.

        Returns:
            Tool execution result.

        Raises:
            RuntimeError: If not connected.
        """
        if self._session is None:
            raise RuntimeError(f"Client '{self.name}' is not connected")

        result = await self._session.call_tool(name, arguments)

        # Extract content from result
        content_parts = []
        for item in result.content:
            if hasattr(item, "text"):
                content_parts.append(item.text)
            else:
                content_parts.append(str(item))

        content = "\n".join(content_parts) if content_parts else ""

        return McpToolResult(
            content=content,
            is_error=bool(result.isError),
        )
