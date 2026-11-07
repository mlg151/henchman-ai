"""Pinned SDK compatibility without implicit replay, schema retrieval or tracing."""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from typing import Any, TextIO

import anyio
from mcp.shared.exceptions import MCPError
from mcp.shared.inbound import find_invalid_x_mcp_header
from opentelemetry import propagate, trace
from pydantic import TypeAdapter, ValidationError

from henchman.mcp.stdio_transport import StdioState, bounded_stdio_client
from henchman.tools.contracts import SchemaContractError
from mcp import Client, ClientSession, StdioServerParameters, types

SUPPORTED_STDIO_REVISIONS = (
    "2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25", "2026-07-28",
)
REQUEST_TIMEOUT_SECONDS = 30.0
NEGOTIATION_TIMEOUT_SECONDS = 40.0
CATALOG_TIMEOUT_SECONDS = 60.0
_TOOL_RESULT: TypeAdapter[types.CallToolResult | types.InputRequiredResult] = TypeAdapter(
    types.CallToolResult | types.InputRequiredResult,
)


def require_private_sdk() -> None:
    """Refuse tracing SDK configurations; never alter application-global OTel.

    SDK 2.3 has no public telemetry-off switch. A configured provider can export
    spans (including exceptions); ambient propagation can expose metadata even
    with a no-op provider. Check again immediately before every native request.
    """
    if type(trace.get_tracer_provider()) not in {trace.ProxyTracerProvider, trace.NoOpTracerProvider}:
        raise RuntimeError("MCP telemetry is configured; SDK 2.3 has no supported privacy-off switch")
    carrier: dict[str, Any] = {}
    try:
        propagate.inject(carrier)
    except Exception:
        raise RuntimeError("MCP telemetry propagation cannot be verified private") from None
    if carrier:
        raise RuntimeError("MCP telemetry propagation is active; clear tracing/baggage before dispatch")


class McpProtocolSession:
    """Expose only single-dispatch operations, preserving native cancellation."""

    def __init__(self, session: ClientSession, state: StdioState) -> None:
        self.session = session
        self.state = state

    @property
    def is_connected(self) -> bool:
        return not self.state.closed and self.state.failure is None

    async def list_tools(self, *, cursor: str | None = None) -> types.ListToolsResult:
        require_private_sdk()
        try:
            # The SDK list_tools helper silently drops invalid header-annotated
            # entries and mutates caches before the complete catalog is valid.
            # Stdio needs no HTTP header maps; retain our atomic publication.
            with anyio.fail_after(REQUEST_TIMEOUT_SECONDS):
                result = await self.session.send_request(
                    types.ListToolsRequest(
                        params=types.PaginatedRequestParams(cursor=cursor) if cursor is not None else None,
                    ),
                    types.ListToolsResult,
                )
        except TimeoutError:
            raise RuntimeError("MCP catalog request deadline exceeded") from None
        except MCPError:
            if self.state.failure is not None:
                raise self.state.failure from None
            raise RuntimeError("MCP catalog request failed; remote error details withheld") from None
        if self.session.protocol_version == "2026-07-28":
            for tool in result.tools:
                if find_invalid_x_mcp_header(tool.input_schema) is not None:
                    raise SchemaContractError("mcp_invalid_header_annotation")
        return result

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> types.CallToolResult:
        require_private_sdk()
        try:
            with anyio.fail_after(REQUEST_TIMEOUT_SECONDS):
                result = await self.session.send_request(
                    types.CallToolRequest(params=types.CallToolRequestParams(name=name, arguments=arguments)),
                    _TOOL_RESULT,
                )
        except TimeoutError:
            raise RuntimeError("MCP tool request deadline exceeded; outcome may be unknown; no automatic replay") from None
        except MCPError:
            if self.state.failure is not None:
                raise self.state.failure from None
            raise RuntimeError("MCP tool request failed; outcome may be unknown; no automatic replay") from None
        if isinstance(result, types.InputRequiredResult) or result.result_type == "input_required":
            raise RuntimeError("MCP input_required continuation is unsupported; no automatic replay")
        return result


async def open_stdio_session(
    stack: AsyncExitStack, params: StdioServerParameters, errlog: TextIO,
) -> tuple[McpProtocolSession, str]:
    """Negotiate modern or legacy stdio and retain its owner in the supplied stack."""
    require_private_sdk()
    state = StdioState()
    client = Client(bounded_stdio_client(params, errlog=errlog, state=state),
                    mode="auto", cache=None, read_timeout_seconds=REQUEST_TIMEOUT_SECONDS)
    try:
        # Client.__aenter__ retains anyio task groups until stack cleanup. An
        # enclosing anyio cancel scope cannot exit ahead of those groups;
        # the native asyncio owner uses a task deadline for this entry only.
        async with asyncio.timeout(NEGOTIATION_TIMEOUT_SECONDS):
            await stack.enter_async_context(client)
    except TimeoutError:
        raise RuntimeError("MCP negotiation deadline exceeded") from None
    except (MCPError, ValidationError, RuntimeError, ExceptionGroup):
        if state.failure is not None:
            raise state.failure from None
        raise RuntimeError("Unsupported protocol version or malformed MCP negotiation") from None
    if client.protocol_version not in SUPPORTED_STDIO_REVISIONS:
        raise RuntimeError("Unsupported protocol version")
    return McpProtocolSession(client.session, state), client.protocol_version
