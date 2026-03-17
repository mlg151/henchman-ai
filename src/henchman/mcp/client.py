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
    from typing import Self

    from mcp.client.session import ClientSession

    from henchman.mcp.config import McpServerConfig

from mcp.client.stdio import stdio_client

from mcp import ClientSession, StdioServerParameters

# Precompiled patterns for log-line detection (avoids recompilation on every write).
_LOG_TIMESTAMP_RE = re.compile(
    r"^(INFO|DEBUG)\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3}",
)
_LOG_BRACKETED_RE = re.compile(r"^\[(INFO|DEBUG)\]")
_LOG_COLON_RE = re.compile(r"^(INFO|DEBUG):")
_LOG_PREFIXES = ("INFO ", "DEBUG ", "INFO:", "DEBUG:")
_LOG_INLINE_TAGS = ("[INFO]", "[DEBUG]")


def _is_log_line(line: str) -> bool:
    """Return True if *line* is an INFO or DEBUG log entry that should be filtered."""
    stripped = line.strip()
    if not stripped:
        return False
    return (
        _LOG_TIMESTAMP_RE.match(stripped) is not None
        or _LOG_BRACKETED_RE.match(stripped) is not None
        or _LOG_COLON_RE.match(stripped) is not None
        or stripped.startswith(_LOG_PREFIXES)
        or any(tag in stripped for tag in _LOG_INLINE_TAGS)
    )


def _filter_log_lines(lines: list[str]) -> list[str]:
    """Return only non-empty lines that are not INFO/DEBUG log entries."""
    return [line for line in lines if line.strip() and not _is_log_line(line)]


class FilteredStream(io.StringIO):
    """A stream that filters out unwanted log messages.

    This stream can be used as errlog for stdio_client to suppress
    INFO and DEBUG logs while still capturing errors.
    """

    def __init__(self: Self, *, verbose: bool = False) -> None:
        """Initialize the filtered stream.

        Args:
            verbose: If True, pass through all messages. If False, filter out INFO/DEBUG.
        """
        super().__init__()
        self.verbose = verbose

    def write(self: Self, text: str) -> int:
        """Write text to the stream, filtering INFO/DEBUG lines unless verbose.

        Args:
            text: Text to write.

        Returns:
            Number of characters that would have been written.
        """
        if self.verbose:
            return sys.stderr.write(text)

        filtered = _filter_log_lines(text.split("\n"))
        if filtered:
            output = "\n".join(filtered) + ("\n" if text.endswith("\n") else "")
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

    def __init__(
        self: Self,
        name: str,
        config: McpServerConfig,
        *,
        verbose: bool = False,
    ) -> None:
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
    def is_connected(self: Self) -> bool:
        """Check if connected to server."""
        return self._session is not None

    def _build_server_params(self: Self) -> StdioServerParameters:  # pragma: no cover
        """Build StdioServerParameters from this client's configuration."""
        return StdioServerParameters(
            command=self.config.command,
            args=self.config.args,
            env=self.config.env or None,
        )

    async def _open_session(  # pragma: no cover
        self: Self,
        stack: AsyncExitStack,
    ) -> ClientSession:
        """Enter stdio_client and ClientSession contexts, then initialize."""
        errlog = FilteredStream(verbose=self.verbose)
        read, write = await stack.enter_async_context(
            stdio_client(self._build_server_params(), errlog=errlog),
        )
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        return session

    async def connect(self: Self) -> None:  # pragma: no cover
        """Connect to the MCP server.

        Uses AsyncExitStack to properly manage the stdio_client and
        ClientSession context managers, keeping their task groups alive
        for the duration of the connection.
        """
        if self._session is not None:
            return

        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()

        try:
            self._session = await self._open_session(self._exit_stack)
            await self.discover_tools()
        except Exception:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self._session = None
            raise

    async def disconnect(self: Self) -> None:
        """Disconnect from the MCP server."""
        if self._exit_stack is not None:
            with suppress(Exception):
                await self._exit_stack.aclose()
            self._exit_stack = None
        self._session = None
        self._tools = []

    async def discover_tools(self: Self) -> list[McpToolDefinition]:
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

    def get_tools(self: Self) -> list[McpToolDefinition]:
        """Get cached tool definitions.

        Returns:
            List of tool definitions.
        """
        return self._tools

    async def call_tool(
        self: Self,
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

        content_parts = [
            item.text if hasattr(item, "text") else str(item)
            for item in result.content
        ]
        content = "\n".join(content_parts) if content_parts else ""

        return McpToolResult(
            content=content,
            is_error=bool(result.isError),
        )
