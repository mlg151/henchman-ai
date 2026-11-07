"""MCP client for connecting to a single server.

This module provides the McpClient class for managing
a connection to an MCP server.
"""

from __future__ import annotations

import asyncio
import codecs
import io
import os
import re
import sys
from contextlib import AsyncExitStack, asynccontextmanager, suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, cast, runtime_checkable

import anyio
from mcp.client.stdio import stdio_client

from henchman.mcp.diagnostics import sdk_diagnostics
from henchman.utils.evidence_redaction import EvidenceRedactor, EvidenceStreamRedactor
from mcp import ClientSession, StdioServerParameters

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from typing import Self, TextIO

    from henchman.config.schema import McpServerConfig


@runtime_checkable
class McpClientProtocol(Protocol):
    """Protocol defining the minimal interface for MCP clients."""

    async def connect(self) -> None:
        """Connect to the MCP server."""
        ...

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        ...

    def get_tools(self) -> list[McpToolDefinition]:
        """Return the list of discovered tools."""
        ...

    @property
    def is_connected(self) -> bool:
        """Return whether the client is currently connected."""
        ...

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> McpToolResult:
        """Call a named tool on the connected server."""
        ...

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


def _pipe_chunk(reader: int) -> bytes | None:
    """Read available pipe bytes without occupying an executor worker."""
    if sys.platform == "win32":
        # Python 3.11 lacks nonblocking Windows pipe support in os.set_blocking.
        import ctypes
        import msvcrt
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        peek = kernel.PeekNamedPipe
        peek.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                         ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
                         ctypes.POINTER(wintypes.DWORD)]
        peek.restype = wintypes.BOOL
        available = wintypes.DWORD()
        if not peek(msvcrt.get_osfhandle(reader), None, 0, None, ctypes.byref(available), None):
            error = ctypes.get_last_error()
            if error in (109, 232):  # Broken pipe / closing pipe.
                return b""
            raise ctypes.WinError(error)
        return os.read(reader, min(available.value, 4096)) if available.value else None
    try:
        return os.read(reader, 4096)
    except BlockingIOError:
        return None


@asynccontextmanager
async def _stdio_stderr(config: McpServerConfig, *, verbose: bool) -> AsyncIterator[TextIO]:
    """Supply a real process descriptor and drain redacted diagnostics in memory."""
    reader, writer = os.pipe()
    if os.name != "nt":
        os.set_blocking(reader, False)
    output = os.fdopen(writer, "wb", buffering=0)
    policy = EvidenceRedactor()
    policy.register_config(config.env)
    projection = EvidenceStreamRedactor(policy)
    closing_deadline: float | None = None

    async def drain() -> None:
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        pending = ""
        discard_line: bool | None = None

        def emit(text: str, *, final: bool = False) -> None:
            nonlocal pending, discard_line
            pending += text
            while pending:
                newline = pending.find("\n", 0, 8192)
                if newline >= 0:
                    size = newline + 1
                elif len(pending) >= 8192:
                    size = 8192
                elif final:
                    size = len(pending)
                else:
                    break
                fragment = pending[:size]
                if discard_line is None:
                    discard_line = not verbose and _is_log_line(fragment)
                if not discard_line and (verbose or fragment.strip() or not fragment.endswith("\n")):
                    sys.stderr.write(fragment)
                if fragment.endswith("\n"):
                    discard_line = None
                pending = pending[size:]

        try:
            loop = asyncio.get_running_loop()
            while closing_deadline is None or loop.time() < closing_deadline:
                chunk = _pipe_chunk(reader)
                if chunk is None:
                    if closing_deadline is not None:
                        break
                    await asyncio.sleep(0.01)
                    continue
                if not chunk:
                    break
                emit(projection.feed(decoder.decode(chunk)))
                await asyncio.sleep(0)
            emit(projection.feed(decoder.decode(b"", final=True)))
            emit(projection.finish(interrupted=True), final=True)
        finally:
            os.close(reader)

    task = asyncio.create_task(drain(), name="henchman-mcp-stderr")
    try:
        yield cast("TextIO", output)
    finally:
        # A descendant can retain stderr after the SDK's direct process exits.
        # Flush available bytes with a bound instead of waiting for its EOF.
        closing_deadline = asyncio.get_running_loop().time() + 0.1
        output.close()
        with anyio.CancelScope(shield=True):
            await task


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
        self.protocol_version: str | None = None
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
        with sdk_diagnostics(self.config.env):
            errlog = await stack.enter_async_context(_stdio_stderr(self.config, verbose=self.verbose))
            read, write = await stack.enter_async_context(
                stdio_client(self._build_server_params(), errlog=errlog),
            )
            session = await stack.enter_async_context(ClientSession(read, write))
            initialized = await session.initialize()
            self.protocol_version = str(initialized.protocolVersion)
        return session

    async def connect(self: Self) -> None:  # pragma: no cover
        """Connect to the MCP server.

        Uses AsyncExitStack to properly manage the stdio_client and
        ClientSession context managers, keeping their task groups alive
        for the duration of the connection.

        Returns:
            None
        """
        if self._session is not None:
            return

        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()

        try:
            self._session = await self._open_session(self._exit_stack)
            await self.discover_tools()
        except BaseException:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self._session = None
            self.protocol_version = None
            raise

    async def disconnect(self: Self) -> None:
        """Disconnect from the MCP server.

        Closes the AsyncExitStack and clears all connection state.
        Any exceptions during cleanup are silently suppressed.

        Returns:
            None
        """
        if self._exit_stack is not None:
            with suppress(Exception):
                await self._exit_stack.aclose()
            self._exit_stack = None
        self._session = None
        self.protocol_version = None
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
