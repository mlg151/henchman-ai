"""MCP client for connecting to a single server.

This module provides the McpClient class for managing
a connection to an MCP server.
"""

from __future__ import annotations

import io
import re
import sys
from contextlib import AsyncExitStack, suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp.client.session import ClientSession

    from henchman.mcp.config import McpServerConfig

from mcp.client.stdio import stdio_client

from mcp import ClientSession, StdioServerParameters


class FilteredStream(io.StringIO):
    """A stream that filters out unwanted log messages.

    This stream can be used as errlog for stdio_client to suppress
    INFO and DEBUG logs while still capturing errors.
    """

    def __init__(self, *, verbose: bool = False) -> None:
        """Initialize the filtered stream.

        Args:
            verbose: If True, pass through all messages. If False, filter out INFO/DEBUG.
        """
        super().__init__()
        self.verbose = verbose

    def write(self, text: str) -> int:
        """Write text to the stream, filtering if not verbose.

        Args:
            text: Text to write.

        Returns:
            Number of characters that would have been written.
        """
        if self.verbose:
            # In verbose mode, pass through to stderr
            return sys.stderr.write(text)

        # Filter out common log patterns
        lines = text.split("\n")
        filtered_lines = []

        # Regex patterns for common log formats
        info_pattern = re.compile(r"^(INFO|DEBUG)\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3}")
        bracketed_pattern = re.compile(r"^\[(INFO|DEBUG)\]")
        colon_pattern = re.compile(r"^(INFO|DEBUG):")

        for line in lines:
            # Skip empty lines
            if not line.strip():
                continue

            # Check for various log format patterns
            line_stripped = line.strip()
            if (
                info_pattern.match(line_stripped)
                or bracketed_pattern.match(line_stripped)
                or colon_pattern.match(line_stripped)
            ):
                # This is an INFO/DEBUG log line, skip it
                continue

            # Also check for common Python logging format variations
            if (
                line_stripped.startswith(("INFO ", "DEBUG ", "INFO:", "DEBUG:"))
                or "[INFO]" in line_stripped
                or "[DEBUG]" in line_stripped  # noqa: E501
            ):
                continue

            # For non-INFO/DEBUG lines (errors, warnings, regular output), pass through
            if line.strip():  # pragma: no branch
                filtered_lines.append(line)

        if filtered_lines:
            # Write filtered output to stderr
            output = "\n".join(filtered_lines) + ("\n" if text.endswith("\n") else "")
            return sys.stderr.write(output)

        return len(text)


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

    def __init__(self, name: str, config: McpServerConfig, *, verbose: bool = False) -> None:
        """Initialize the client.

        Args:
            name: Server name.
            config: Server configuration.
            verbose: If True, show server logs. If False, suppress INFO/DEBUG logs.
        """
        self.name = name
        self.config = config
        self.verbose = verbose
        self._session: ClientSession | None = None
        self._tools: list[McpToolDefinition] = []
        self._exit_stack: AsyncExitStack | None = None

    @property
    def is_connected(self) -> bool:
        """Check if connected to server."""
        return self._session is not None

    async def connect(self) -> None:  # pragma: no cover
        """Connect to the MCP server.

        Uses AsyncExitStack to properly manage the stdio_client and
        ClientSession context managers, keeping their task groups alive
        for the duration of the connection.

        Returns:
            None
        """
        if self._session is not None:
            return

        server_params = StdioServerParameters(
            command=self.config.command,
            args=self.config.args,
            env=self.config.env or None,
        )

        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()

        try:
            # Create filtered error stream based on verbosity
            errlog = FilteredStream(verbose=self.verbose)

            # Enter stdio_client context — keeps task group alive
            read, write = await self._exit_stack.enter_async_context(
                stdio_client(server_params, errlog=errlog),
            )

            # Enter ClientSession context
            session = await self._exit_stack.enter_async_context(ClientSession(read, write))

            self._session = session
            await self._session.initialize()

            # Discover tools on connect
            await self.discover_tools()
        except Exception:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self._session = None
            raise

    async def disconnect(self) -> None:
        """Disconnect from the MCP server.

        Returns:
            None
        """
        if self._exit_stack is not None:
            with suppress(Exception):
                await self._exit_stack.aclose()
            self._exit_stack = None
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
            msg = f"Client '{self.name}' is not connected"
            raise RuntimeError(msg)

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
