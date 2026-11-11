"""Pinned SDK compatibility without implicit replay, schema retrieval or tracing."""

from __future__ import annotations

import asyncio
import copy
from collections.abc import Callable
from contextlib import AsyncExitStack, suppress
from typing import TYPE_CHECKING, Annotated, Any, Protocol, TextIO, TypeVar

import anyio
from mcp.client.session import _clamp_inbound_ttl, _later_revision_fields
from mcp.shared.dispatcher import CallOptions
from mcp.shared.exceptions import MCPError
from mcp.shared.inbound import (
    MCP_NAME_HEADER,
    encode_header_value,
    find_invalid_x_mcp_header,
    x_mcp_header_map,
)
from mcp_types import methods
from opentelemetry import propagate, trace
from pydantic import BaseModel, BeforeValidator, TypeAdapter, ValidationError

from henchman.mcp.stdio_transport import StdioState, bounded_stdio_client
from henchman.tools.contracts import SchemaContractError
from mcp import Client, ClientSession, StdioServerParameters, types

if TYPE_CHECKING:
    from henchman.mcp.oauth_transport import OAuthHttpPermit

SUPPORTED_STDIO_REVISIONS = (
    "2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25", "2026-07-28",
)
REQUEST_TIMEOUT_SECONDS = 30.0
NEGOTIATION_TIMEOUT_SECONDS = 40.0
CATALOG_TIMEOUT_SECONDS = 60.0
_TOOL_RESULT: TypeAdapter[types.CallToolResult | types.InputRequiredResult] = TypeAdapter(
    types.CallToolResult | types.InputRequiredResult,
)
_ResultT = TypeVar("_ResultT", bound=BaseModel)


class _ConnectionState(Protocol):
    @property
    def failure(self) -> Exception | None: ...

    @property
    def closed(self) -> bool: ...


def _context_resource_forms(value: Any) -> Any:
    """Reject ambiguous resources before SDK union models discard extra fields."""
    if isinstance(value, dict):
        contents = list(value.get("contents", [])) if isinstance(value.get("contents"), list) else []
        for message in value.get("messages", []) if isinstance(value.get("messages"), list) else []:
            if isinstance(message, dict) and isinstance(message.get("content"), dict):
                block = message["content"]
                if block.get("type") == "resource":
                    contents.append(block.get("resource"))
        for content in contents:
            if isinstance(content, dict) and "text" in content and "blob" in content:
                raise SchemaContractError("mcp_context_resource_shape")
    return value


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

    def __init__(self, session: ClientSession, state: _ConnectionState, request_timeout: float) -> None:
        self.session = session
        self.state = state
        self.request_timeout = request_timeout
        capabilities = session.server_capabilities
        self._capabilities = capabilities.model_dump(mode="json", by_alias=True, exclude_none=True) if capabilities is not None else {}

    def supports(self, feature: str) -> bool:
        """Read the capabilities captured at negotiation, not later remote hints."""
        return feature in self._capabilities

    async def _send_request(
        self, request: types.Request[Any, Any], result_type: type[_ResultT] | TypeAdapter[_ResultT],
    ) -> _ResultT:
        """Check terminal results before SDK 2.3 removes later-revision fields.

        Preserve the pinned SDK's header stamping, dispatcher cancellation,
        revision validation and parsing, without its lossy continuation handling.
        This adapter deliberately exposes no resumption or retry options.
        """
        if self.state.failure is not None:
            raise self.state.failure
        if self.state.closed:
            raise RuntimeError("MCP transport is closed; explicit reconnection is required")
        data = request.model_dump(by_alias=True, mode="json", exclude_none=True)
        method = data["method"]
        options: CallOptions = {}
        self.session._stamp(data, options)
        headers = options.setdefault("headers", {})
        if (key := type(request).name_param) is not None and MCP_NAME_HEADER not in headers:
            name = (data.get("params") or {}).get(key)
            if not isinstance(name, str):
                raise SchemaContractError("mcp_request_name")
            headers[MCP_NAME_HEADER] = encode_header_value(name)
        options["timeout"] = self.request_timeout
        raw = await self.session._dispatcher.send_raw_request(method, data.get("params"), options)
        if (raw.get("resultType", "complete") != "complete"
            or "inputRequests" in raw or "requestState" in raw):
            raise RuntimeError("MCP input_required or other continuation is unsupported; no automatic replay")
        _clamp_inbound_ttl(raw)
        version = self.session.protocol_version or "2025-11-25"
        with suppress(KeyError):
            methods.validate_server_result(method, version, raw)
        foreign = _later_revision_fields(method, version)
        if not foreign.isdisjoint(raw):
            raw = {key: value for key, value in raw.items() if key not in foreign}
        if isinstance(result_type, TypeAdapter):
            return result_type.validate_python(raw, by_name=False)
        return result_type.model_validate(raw, by_name=False)

    async def request_context(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send one typed context request without automatic continuation or retry."""
        contracts: dict[str, tuple[Any, Any]] = {
            "resources/list": (types.ListResourcesRequest, types.ListResourcesResult),
            "resources/templates/list": (types.ListResourceTemplatesRequest, types.ListResourceTemplatesResult),
            "prompts/list": (types.ListPromptsRequest, types.ListPromptsResult),
            "resources/read": (types.ReadResourceRequest, TypeAdapter(Annotated[types.ReadResourceResult | types.InputRequiredResult, BeforeValidator(_context_resource_forms)])),
            "prompts/get": (types.GetPromptRequest, TypeAdapter(Annotated[types.GetPromptResult | types.InputRequiredResult, BeforeValidator(_context_resource_forms)])),
        }
        if method not in contracts:
            raise RuntimeError("Unsupported MCP context operation")
        request_type, result_type = contracts[method]
        require_private_sdk()
        try:
            request = request_type.model_validate({"method": method, "params": copy.deepcopy(params)})
            with anyio.fail_after(self.request_timeout):
                result = await self._send_request(request, result_type)
        except TimeoutError:
            raise RuntimeError("MCP context request deadline exceeded; no automatic retry") from None
        except ValidationError:
            raise SchemaContractError("mcp_context_shape") from None
        except MCPError:
            if self.state.failure is not None:
                raise self.state.failure from None
            raise RuntimeError("MCP context request failed; remote error details withheld") from None
        if isinstance(result, types.InputRequiredResult) or result.result_type != "complete":
            raise RuntimeError("MCP input_required continuation is unsupported; no automatic retry")
        return copy.deepcopy(result.model_dump(mode="json", by_alias=True, exclude_unset=True))

    @property
    def is_connected(self) -> bool:
        return not self.state.closed and self.state.failure is None

    def publish_catalog(self, schemas: dict[str, dict[str, Any]]) -> None:
        """Replace SDK header maps only after the complete catalog is accepted."""
        if self.session.protocol_version == "2026-07-28":
            self.session._x_mcp_header_maps = {name: x_mcp_header_map(schema) for name, schema in schemas.items()}

    async def list_tools(self, *, cursor: str | None = None) -> types.ListToolsResult:
        require_private_sdk()
        try:
            # The SDK list_tools helper silently drops invalid header-annotated
            # entries and mutates caches before the complete catalog is valid.
            # Stdio needs no HTTP header maps; retain our atomic publication.
            with anyio.fail_after(self.request_timeout):
                result = await self._send_request(
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
            with anyio.fail_after(self.request_timeout):
                result = await self._send_request(
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
    *, request_timeout: float | None = None, negotiation_timeout: float | None = None,
) -> tuple[McpProtocolSession, str]:
    """Negotiate modern or legacy stdio and retain its owner in the supplied stack."""
    require_private_sdk()
    state = StdioState()
    timeout = REQUEST_TIMEOUT_SECONDS if request_timeout is None else request_timeout
    client = Client(bounded_stdio_client(params, errlog=errlog, state=state),
                    mode="auto", cache=None, read_timeout_seconds=timeout)
    return await _negotiate(stack, client, state, timeout, negotiation_timeout, SUPPORTED_STDIO_REVISIONS)


async def open_http_session(
    stack: AsyncExitStack, url: str, *, authorize: Callable[[], None], authorize_cleanup: Callable[[], None],
    request_timeout: float | None = None, negotiation_timeout: float | None = None,
    oauth_permit: OAuthHttpPermit | None = None, oauth_owner: object | None = None,
) -> tuple[McpProtocolSession, str]:
    """Negotiate the HTTP revisions over an owned bounded transport."""
    from henchman.mcp.http_transport import HttpState, bounded_http_client

    require_private_sdk()
    state = HttpState()
    timeout = REQUEST_TIMEOUT_SECONDS if request_timeout is None else request_timeout
    transport = bounded_http_client(url, state=state, authorize=authorize, authorize_cleanup=authorize_cleanup,
                                    request_timeout=timeout, oauth_permit=oauth_permit, oauth_owner=oauth_owner)
    client = Client(transport, mode="auto", cache=None, read_timeout_seconds=timeout)
    return await _negotiate(stack, client, state, timeout, negotiation_timeout, SUPPORTED_STDIO_REVISIONS[1:])


async def _negotiate(
    stack: AsyncExitStack, client: Client, state: _ConnectionState, request_timeout: float,
    negotiation_timeout: float | None, supported_revisions: tuple[str, ...],
) -> tuple[McpProtocolSession, str]:
    try:
        # Client.__aenter__ retains anyio task groups until stack cleanup. An
        # enclosing anyio cancel scope cannot exit ahead of those groups;
        # the native asyncio owner uses a task deadline for this entry only.
        async with asyncio.timeout(NEGOTIATION_TIMEOUT_SECONDS if negotiation_timeout is None else negotiation_timeout):
            await stack.enter_async_context(client)
    except TimeoutError:
        raise RuntimeError("MCP negotiation deadline exceeded") from None
    except (MCPError, ValidationError, RuntimeError, ExceptionGroup):
        if state.failure is not None:
            raise state.failure from None
        raise RuntimeError("Unsupported protocol version or malformed MCP negotiation") from None
    if client.protocol_version not in supported_revisions:
        raise RuntimeError("Unsupported protocol version")
    return McpProtocolSession(client.session, state, request_timeout), client.protocol_version
