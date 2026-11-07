"""MCP client for connecting to a single server.

This module provides the McpClient class for managing
a connection to an MCP server.
"""

from __future__ import annotations

import asyncio
import codecs
import copy
import io
import json
import os
import re
import sys
from collections.abc import Callable, Iterable
from contextlib import AsyncExitStack, asynccontextmanager, suppress
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, cast, runtime_checkable

import anyio
from pydantic import ValidationError

from henchman.mcp.credentials import reference_values, resolve_environment
from henchman.mcp.diagnostics import sdk_diagnostics
from henchman.tools.contracts import SchemaContract, SchemaContractError
from henchman.utils.evidence_redaction import EvidenceRedactor, EvidenceStreamRedactor
from henchman.utils.pipe_output import pipe_chunk as _pipe_chunk
from mcp import StdioServerParameters

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from typing import Self, TextIO

    from henchman.config.schema import McpServerConfig
    from henchman.mcp.context import McpContextCatalog, McpContextResult
    from henchman.mcp.oauth_transport import OAuthHttpAuthority, OAuthHttpPermit
    from henchman.mcp.protocol import McpProtocolSession


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
MAX_DISCOVERY_PAGES = 32
MAX_DISCOVERY_TOOLS = 1024
MAX_CATALOG_BYTES = 4 * 1024 * 1024
MAX_RESULT_BLOCKS = 256
_JSON_PAYLOAD = SchemaContract(True)


def _sdk_payload(value: Any) -> dict[str, Any]:
    payload = value.model_dump(mode="json", by_alias=True, exclude_unset=True)
    _JSON_PAYLOAD.validate(payload)
    return cast("dict[str, Any]", payload)


_LOG_TIMESTAMP_RE = re.compile(
    r"^(INFO|DEBUG)\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3}",
)
_LOG_BRACKETED_RE = re.compile(r"^\[(INFO|DEBUG)\]")
_LOG_COLON_RE = re.compile(r"^(INFO|DEBUG):")
_LOG_PREFIXES = ("INFO ", "DEBUG ", "INFO:", "DEBUG:")
_LOG_INLINE_TAGS = ("[INFO]", "[DEBUG]")


async def _join_session_task(task: asyncio.Task[None]) -> None:
    """Join transport cleanup even when the caller is cancelled again."""
    interruption: asyncio.CancelledError | None = None
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError as error:
            if not task.done():
                interruption = error
        except BaseException:
            break
    if interruption is not None:
        # Retrieve any owner error before forwarding the caller's cancellation.
        if not task.cancelled():
            task.exception()
        raise interruption
    task.result()


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


@asynccontextmanager
async def _stdio_stderr(
    config: McpServerConfig, *, verbose: bool, secrets: Iterable[str] = (),
) -> AsyncIterator[TextIO]:
    """Supply a real process descriptor and drain redacted diagnostics in memory."""
    reader, writer = os.pipe()
    if os.name != "nt":
        os.set_blocking(reader, False)
    output = os.fdopen(writer, "wb", buffering=0)
    policy = EvidenceRedactor(secrets)
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
    content_blocks: tuple[dict[str, Any], ...] = ()
    structured_content: object = None
    structured_content_present: bool = False
    metadata: dict[str, Any] | None = None


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
    output_schema: dict[str, Any] | None = None
    annotations: dict[str, Any] = field(default_factory=dict)


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
        oauth_authority: OAuthHttpAuthority | None = None,
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
        self._oauth_permit: OAuthHttpPermit | None = None
        self._oauth_config: dict[str, Any] | None = None
        if oauth_authority is not None:
            from henchman.mcp.oauth import OAuthBinding, OAuthError
            from henchman.mcp.oauth_transport import require_oauth_http_profile

            require_oauth_http_profile()
            if OAuthBinding.from_config(name, config) != oauth_authority.binding:
                raise OAuthError("OAuth HTTP permit does not match its client configuration")
            self._oauth_config = copy.deepcopy(config.model_dump())
            self._oauth_permit = oauth_authority.for_client(self)
        self._session: McpProtocolSession | None = None
        self.protocol_version: str | None = None
        self._tools: list[McpToolDefinition] = []
        self._exit_stack: AsyncExitStack | None = None
        self._owner_task: asyncio.Task[None] | None = None
        self._ready: asyncio.Future[None] | None = None
        self._stop = asyncio.Event()
        self._lifecycle_lock = asyncio.Lock()
        self._connection_environment: dict[str, str] | None = None
        self._dispatch_guard: Callable[[], None] | None = None
        self._access_guard: Callable[[], None] | None = None
        self._invalid_reason: str | None = None
        self.catalog_generation = 0
        self._discovery_lock = asyncio.Lock()
        self.connection_generation = 0
        from henchman.mcp.context import McpContextService
        self._context = McpContextService(self)

    @property
    def is_connected(self: Self) -> bool:
        """Check if connected to server."""
        if self._session is None or not getattr(self._session, "is_connected", True):
            return False
        try:
            self._check_credentials()
        except (RuntimeError, ValueError, PermissionError):
            return False
        return True

    def set_dispatch_guard(self, guard: Callable[[], None]) -> None:
        """Bind the manager's immutable connection generation to native dispatch."""
        self._dispatch_guard = guard

    def set_access_guard(self, guard: Callable[[], None]) -> None:
        """Bind trusted runtime restrictions independently of connection revocation."""
        self._access_guard = guard

    def _check_access(self) -> None:
        from henchman.tools.access_policy import ToolAccessError, current_access_policies

        if any(policy.restricted for policy in current_access_policies()):
            raise ToolAccessError("MCP transport is unsupported under restricted filesystem/network policy")
        if self._access_guard is not None:
            self._access_guard()

    def invalidate_credentials(self) -> None:
        """Synchronously deny new calls and signal the owning task to close."""
        self._invalid_reason = "MCP credentials changed; reconnect the server before dispatch"
        self._stop.set()
        if self._owner_task is not None and self._ready is not None and not self._ready.done():
            self._owner_task.cancel()

    def _check_credentials(self) -> None:
        self._check_access()
        if self._oauth_permit is not None:
            self._check_oauth_configuration()
            self._oauth_permit.check()
        elif getattr(self.config, "oauth", None) is not None:
            raise RuntimeError("MCP OAuth login and authenticated transport are not yet supported")
        if self._invalid_reason is not None:
            raise RuntimeError(self._invalid_reason)
        if self._dispatch_guard is not None:
            self._dispatch_guard()
        if self._connection_environment is not None:
            try:
                current = resolve_environment(self.config.env)
            except ValueError:
                self.invalidate_credentials()
                raise
            if current != self._connection_environment:
                self.invalidate_credentials()
                raise RuntimeError("MCP environment credentials changed; reconnect the server before dispatch")

    def _check_oauth_configuration(self) -> None:
        if self._oauth_config is not None and self.config.model_dump() != self._oauth_config:
            raise RuntimeError("MCP OAuth client configuration changed")

    def _check_http_cleanup(self) -> None:
        self._check_access()
        self._check_oauth_configuration()

    def _build_server_params(self: Self) -> StdioServerParameters:  # pragma: no cover
        """Build StdioServerParameters from this client's configuration."""
        environment = resolve_environment(self.config.env)
        self._connection_environment = environment
        if self.config.command is None:
            raise RuntimeError("MCP stdio requires a command")
        return StdioServerParameters(
            command=self.config.command,
            args=self.config.args,
            env=environment or None,
        )

    async def _open_session(  # pragma: no cover
        self: Self,
        stack: AsyncExitStack,
    ) -> McpProtocolSession:
        """Enter the bounded stdio transport and negotiate the pinned SDK."""
        from henchman.mcp.protocol import open_http_session, open_stdio_session

        request_timeout = self.config.request_timeout_seconds
        negotiation_timeout = self.config.negotiation_timeout_seconds
        timeouts = {"request_timeout": request_timeout if request_timeout != 30 else None,
                    "negotiation_timeout": negotiation_timeout if negotiation_timeout != 40 else None}
        if self.config.transport == "streamable_http":
            if self.config.url is None:
                raise RuntimeError("MCP Streamable HTTP requires an endpoint")
            policy = EvidenceRedactor()
            if self._oauth_permit is not None:
                self._oauth_permit.authority.register_evidence(policy)
            with sdk_diagnostics({}, policy=policy):
                session, self.protocol_version = await open_http_session(
                    stack, self.config.url, authorize=self._check_credentials, authorize_cleanup=self._check_http_cleanup,
                    oauth_permit=self._oauth_permit, oauth_owner=self,
                    **timeouts,
                )
            return session
        params = self._build_server_params()
        diagnostic_config = copy.copy(self.config)
        diagnostic_config.env = dict(params.env or {})
        secrets = reference_values(self.config.env, diagnostic_config.env)
        with sdk_diagnostics(diagnostic_config.env, secrets=secrets):
            errlog = await stack.enter_async_context(
                _stdio_stderr(diagnostic_config, verbose=self.verbose, secrets=secrets)
            )
            session, self.protocol_version = await open_stdio_session(stack, params, errlog, **timeouts)
        return session

    async def connect(self: Self) -> None:  # pragma: no cover
        """Connect to the MCP server.

        A retained owner task enters and exits the SDK context managers.
        Failed or cancelled startup joins that task before returning.

        Returns:
            None
        """
        from henchman.mcp.protocol import require_private_sdk

        require_private_sdk()
        async with self._lifecycle_lock:
            if self.is_connected:
                return
            if self._owner_task is not None:
                self._stop.set()
                await _join_session_task(self._owner_task)
                self._owner_task = None
            self._invalid_reason = None
            self._stop = asyncio.Event()
            self._ready = asyncio.get_running_loop().create_future()
            self._owner_task = asyncio.create_task(self._run_session(self._ready), name="henchman-mcp-session")
            ready = self._ready

            def startup_finished(task: asyncio.Task[None]) -> None:
                # Retrieve late failures too: readiness may already have been
                # delivered, and asyncio must not log raw transport errors on
                # garbage collection. Awaiting the task still raises its error.
                error = asyncio.CancelledError() if task.cancelled() else task.exception()
                if not ready.done():
                    if isinstance(error, asyncio.CancelledError) and self._invalid_reason is not None:
                        error = RuntimeError(self._invalid_reason)
                    ready.set_exception(error or RuntimeError("MCP session closed during startup"))

            self._owner_task.add_done_callback(startup_finished)
            try:
                await asyncio.shield(self._ready)
            except BaseException:
                self._owner_task.cancel()
                with suppress(BaseException):
                    await _join_session_task(self._owner_task)
                self._owner_task = None
                if self._ready.done() and not self._ready.cancelled():
                    self._ready.exception()
                raise

    async def _run_session(self, ready: asyncio.Future[None]) -> None:
        """Enter and exit SDK task groups in one task, including cancelled startup."""
        try:
            stack = AsyncExitStack()
            await stack.__aenter__()
            self._exit_stack = stack
            try:
                self._check_credentials()
                self._session = await self._open_session(stack)
                self.connection_generation += 1
                self._context.clear()
                self._check_credentials()
                await self.discover_tools()
                self._check_credentials()
                ready.set_result(None)
                await self._stop.wait()
            finally:
                # Do not inject application startup failures into SDK task
                # groups: that wraps a protocol error in nested ExceptionGroups.
                await stack.aclose()
        except BaseException as error:
            if not ready.done():
                ready.set_exception(
                    RuntimeError(self._invalid_reason)
                    if isinstance(error, asyncio.CancelledError) and self._invalid_reason is not None
                    else error
                )
            raise
        finally:
            self._exit_stack = None
            self._session = None
            self._connection_environment = None
            self.protocol_version = None
            self._tools = []
            self._context.clear()

    async def disconnect(self: Self) -> None:
        """Disconnect from the MCP server.

        Signals and joins the native owner task before clearing connection
        state, including when the caller is cancelled during cleanup.

        Returns:
            None
        """
        owner = self._owner_task
        self._stop.set()
        if self._owner_task is not None and self._ready is not None and not self._ready.done():
            self._owner_task.cancel()
        try:
            async with self._lifecycle_lock:
                if self._owner_task is not None:
                    try:
                        await _join_session_task(self._owner_task)
                    finally:
                        self._owner_task = None
                elif self._exit_stack is not None:
                    # Preserve manually supplied protocol/test sessions, which
                    # have no owned native transport or lifecycle task.
                    with suppress(Exception):
                        await self._exit_stack.aclose()
                    self._exit_stack = None
                self._session = None
                self.protocol_version = None
                self._tools = []
        except asyncio.CancelledError:
            # Cancellation can arrive while waiting for a startup caller to
            # release the lock. Its owner still must finish cleanup first.
            if owner is not None:
                with suppress(BaseException):
                    await _join_session_task(owner)
            raise

    async def discover_tools(self: Self) -> list[McpToolDefinition]:
        """Discover tools from the server.

        Returns:
            List of tool definitions.
        """
        async with self._discovery_lock:
            tools = await self.prepare_tools()
            self.publish_tools(tools)
            return self.get_tools()

    async def prepare_tools(self) -> list[McpToolDefinition]:
        """Stage a complete bounded catalog without changing published authority."""
        from henchman.mcp.protocol import CATALOG_TIMEOUT_SECONDS

        try:
            timeout = self.config.catalog_timeout_seconds
            with anyio.fail_after(CATALOG_TIMEOUT_SECONDS if timeout == 60 else timeout):
                return await self._prepare_tools()
        except TimeoutError:
            raise RuntimeError("MCP catalog discovery deadline exceeded; previous catalog retained") from None

    async def _prepare_tools(self) -> list[McpToolDefinition]:
        """Walk the catalog under prepare_tools' single operation deadline."""
        self._check_credentials()
        session = self._session
        if session is None:
            return []
        from henchman.mcp.protocol import McpProtocolSession
        if isinstance(session, McpProtocolSession) and not session.supports("tools"):
            return []
        tools: list[McpToolDefinition] = []
        names: set[str] = set()
        cursors: set[str] = set()
        cursor = None
        total_bytes = 0
        for _ in range(MAX_DISCOVERY_PAGES):
            try:
                result = await session.list_tools(cursor=cursor) if cursor is not None else await session.list_tools()
            except ValidationError:
                raise SchemaContractError("mcp_catalog_shape") from None
            self._check_credentials()
            if self._session is not session:
                raise SchemaContractError("mcp_connection_changed")
            payload = _sdk_payload(result)
            total_bytes += len(json.dumps(payload, ensure_ascii=True))
            if total_bytes > MAX_CATALOG_BYTES:
                raise SchemaContractError("mcp_catalog_bytes")
            for raw in payload.get("tools", []):
                name = raw["name"]
                if not name or len(name) > 128 or any(ord(char) < 32 for char in name):
                    raise SchemaContractError("mcp_tool_name")
                if name in names:
                    raise SchemaContractError("mcp_duplicate_tool")
                names.add(name)
                if len(names) > MAX_DISCOVERY_TOOLS:
                    raise SchemaContractError("mcp_tool_limit")
                input_schema = raw["inputSchema"]
                output_schema = raw.get("outputSchema")
                SchemaContract(input_schema)
                if output_schema is not None:
                    SchemaContract(output_schema)
                tools.append(McpToolDefinition(
                    name=name, description=raw.get("description") or "", input_schema=copy.deepcopy(input_schema),
                    output_schema=copy.deepcopy(output_schema), annotations=copy.deepcopy(raw.get("annotations") or {}),
                ))
            cursor = payload.get("nextCursor")
            if cursor is None:
                return tools
            if not isinstance(cursor, str) or not cursor or len(cursor) > 4096 or cursor in cursors:
                raise SchemaContractError("mcp_cursor_cycle_or_shape")
            cursors.add(cursor)
        raise SchemaContractError("mcp_page_limit")

    def publish_tools(self, tools: list[McpToolDefinition]) -> None:
        """Publish a previously validated staged snapshot without an await gap."""
        from henchman.mcp.protocol import McpProtocolSession

        self._check_credentials()
        if isinstance(self._session, McpProtocolSession):
            self._session.publish_catalog({tool.name: copy.deepcopy(tool.input_schema) for tool in tools})
        self._tools = copy.deepcopy(tools)
        self.catalog_generation += 1

    def get_tools(self: Self) -> list[McpToolDefinition]:
        """Get cached tool definitions.

        Returns:
            List of tool definitions.
        """
        return copy.deepcopy(self._tools)

    async def list_resources(self) -> McpContextCatalog:
        """Explicitly refresh this server's resource catalog."""
        return await self._context.list("resources")

    async def list_resource_templates(self) -> McpContextCatalog:
        """Explicitly refresh template descriptions without expanding any URI."""
        return await self._context.list("templates")

    async def list_prompts(self) -> McpContextCatalog:
        """Explicitly refresh prompt declarations without using their content."""
        return await self._context.list("prompts")

    async def read_resource(self, uri: str) -> McpContextResult:
        """Read an opaque resource URI exclusively through this server."""
        return await self._context.read(uri)

    async def get_prompt(self, name: str, arguments: dict[str, str]) -> McpContextResult:
        """Retrieve a declared prompt as data without changing conversation state."""
        return await self._context.prompt(name, arguments)

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
        self._check_credentials()
        if self._session is None:
            msg = f"Client '{self.name}' is not connected"
            raise RuntimeError(msg)

        definition = next((tool for tool in self._tools if tool.name == name), None)
        if definition is None:
            raise SchemaContractError("mcp_unknown_tool")
        definition = copy.deepcopy(definition)
        SchemaContract(definition.input_schema).validate(arguments)
        captured = copy.deepcopy(arguments)
        try:
            result = await self._session.call_tool(name, captured)
        except ValidationError:
            # The SDK validates against the negotiated revision. Older wire
            # contracts permit object-or-null structuredContent only.
            reason = ("mcp_result_shape" if self.protocol_version == "2026-07-28"
                      else "mcp_result_shape_object_or_null_required")
            raise SchemaContractError(reason) from None
        payload = _sdk_payload(result)
        blocks = payload.get("content", [])
        if len(blocks) > MAX_RESULT_BLOCKS:
            raise SchemaContractError("mcp_result_block_limit")
        present = "structuredContent" in payload
        structured = payload.get("structuredContent")
        is_error = bool(payload.get("isError", False))
        if not is_error and definition.output_schema is not None:
            if not present:
                raise SchemaContractError("mcp_structured_output_missing")
            SchemaContract(definition.output_schema).validate(structured)
        content = "\n".join(
            block["text"] if block["type"] == "text" else f"[MCP {block['type']} content]"
            for block in blocks
        )
        return McpToolResult(content=content, is_error=is_error,
                             content_blocks=tuple(copy.deepcopy(blocks)), structured_content=copy.deepcopy(structured),
                             structured_content_present=present, metadata=copy.deepcopy(payload.get("_meta")))
