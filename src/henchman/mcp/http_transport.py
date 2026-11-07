"""Owned, bounded Streamable HTTP without redirects, auth fallback, or replay."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from http.cookiejar import CookieJar, DefaultCookiePolicy
from typing import Any

import anyio
import httpx2
from mcp.client._transport import TransportStreams
from mcp.shared._context_streams import create_context_streams
from mcp.shared.message import ClientMessageMetadata, SessionMessage

from henchman.config.mcp import validate_mcp_endpoint
from henchman.mcp.diagnostics import http_diagnostics
from henchman.tools.contracts import MAX_VALUE_BYTES, SchemaContract, SchemaContractError
from mcp import types

MAX_HTTP_BODY_BYTES = MAX_VALUE_BYTES
MAX_SSE_BODY_BYTES = 4 * MAX_VALUE_BYTES
MAX_HTTP_HEADER_BYTES = 8192
HTTP_SHUTDOWN_TIMEOUT_SECONDS = 5.0
_JSON = SchemaContract(True)


class McpHttpError(RuntimeError):
    """A value-free remote transport diagnostic."""


@dataclass
class HttpState:
    failure: Exception | None = None
    closed: bool = False
    session_id: str | None = None
    protocol_version: str | None = None


class _NoCookies(DefaultCookiePolicy):
    def set_ok(self, cookie: Any, request: Any) -> bool:
        return False

    def return_ok(self, cookie: Any, request: Any) -> bool:
        return False


class _BoundedBody(httpx2.AsyncByteStream):
    def __init__(self, stream: httpx2.AsyncByteStream, limit: int) -> None:
        self.stream = stream
        self.limit = limit

    async def __aiter__(self) -> AsyncIterator[bytes]:
        consumed = 0
        async for chunk in self.stream:
            consumed += len(chunk)
            if consumed > self.limit:
                raise McpHttpError("MCP HTTP response exceeds its byte limit")
            yield chunk

    async def aclose(self) -> None:
        await self.stream.aclose()


def _parse_message(data: str | bytes) -> SessionMessage:
    try:
        raw = json.loads(data)
        _JSON.validate(raw)
        parsed = types.jsonrpc_message_adapter.validate_python(raw, by_name=False)
    except (ValueError, RecursionError):
        raise McpHttpError("MCP HTTP response has an invalid or oversized message") from None
    return SessionMessage(parsed)


@asynccontextmanager
async def bounded_http_client(
    url: str, *, state: HttpState, authorize: Callable[[], None], authorize_cleanup: Callable[[], None],
    request_timeout: float,
) -> AsyncIterator[TransportStreams]:
    """Own HTTP requests and cleanup; every request targets one validated endpoint."""
    validate_mcp_endpoint(url)
    try:
        endpoint = httpx2.URL(url)
    except httpx2.InvalidURL:
        state.failure = McpHttpError("MCP HTTP endpoint encoding is unsupported")
        raise state.failure from None
    incoming, read_stream = create_context_streams[SessionMessage | Exception](0)
    write_stream, outgoing = create_context_streams[SessionMessage](0)
    active: dict[str | int, anyio.CancelScope] = {}

    def fail(error: Exception) -> None:
        if state.failure is None:
            state.failure = error
        state.closed = True
        incoming.close()
        write_stream.close()
        for scope in active.values():
            scope.cancel()

    def request_headers(message: SessionMessage | None = None) -> dict[str, str]:
        headers = {"accept": "application/json, text/event-stream", "content-type": "application/json",
                   "accept-encoding": "identity"}
        if state.session_id:
            headers["mcp-session-id"] = state.session_id
        if state.protocol_version:
            headers["mcp-protocol-version"] = state.protocol_version
        if message is not None and isinstance(message.metadata, ClientMessageMetadata):
            for key, value in (message.metadata.headers or {}).items():
                normalized = key.lower()
                if normalized not in {"mcp-protocol-version", "mcp-method", "mcp-name"} and not normalized.startswith("mcp-param-"):
                    raise McpHttpError("MCP HTTP request contains an unsupported header")
                headers[normalized] = value
        if sum(len(key) + len(value) for key, value in headers.items()) > MAX_HTTP_HEADER_BYTES:
            raise McpHttpError("MCP HTTP headers exceed their byte limit")
        return headers

    async with httpx2.AsyncClient(
        trust_env=False, follow_redirects=False, timeout=httpx2.Timeout(request_timeout),
        cookies=CookieJar(policy=_NoCookies()), limits=httpx2.Limits(max_connections=16, max_keepalive_connections=8),
    ) as client:
        async def deliver(data: str | bytes, request_id: str | int) -> bool:
            message = _parse_message(data)
            response = message.message
            if isinstance(response, types.JSONRPCResponse | types.JSONRPCError):
                if type(response.id) is not type(request_id) or response.id != request_id:
                    raise McpHttpError("MCP HTTP response does not match its request")
                await incoming.send(message)
                return True
            if isinstance(response, types.JSONRPCRequest):
                raise McpHttpError("MCP HTTP server-initiated requests are unsupported")
            await incoming.send(message)
            return False

        async def post(message: SessionMessage) -> None:
            body = message.message
            is_request = isinstance(body, types.JSONRPCRequest)
            method = body.method if isinstance(body, types.JSONRPCRequest | types.JSONRPCNotification) else None
            if method is None:
                raise McpHttpError("MCP HTTP outbound responses are unsupported")
            payload = body.model_dump_json(by_alias=True, exclude_unset=True).encode("utf-8")
            if len(payload) > MAX_HTTP_BODY_BYTES:
                raise McpHttpError("MCP HTTP request exceeds its byte limit")
            headers = request_headers(message)
            if method == "initialize":
                headers.pop("mcp-protocol-version", None)
                headers.pop("mcp-session-id", None)
            request = client.build_request("POST", endpoint, headers=headers, content=payload)
            if request.url != endpoint:
                raise McpHttpError("MCP HTTP destination changed before dispatch")
            authorize()
            response = await client.send(request, stream=True, follow_redirects=False)
            try:
                if response.status_code == 401:
                    raise McpHttpError("MCP HTTP authentication required; OAuth is not configured; no automatic retry")
                if 300 <= response.status_code < 400:
                    raise McpHttpError("MCP HTTP redirects are unsupported; configure the final endpoint explicitly")
                if response.headers.get("content-encoding", "identity").strip().lower() != "identity":
                    raise McpHttpError("MCP HTTP compressed responses are unsupported")
                content_type = response.headers.get("content-type", "").partition(";")[0].strip().lower()
                if not is_request:
                    if response.status_code != 202:
                        raise McpHttpError("MCP HTTP notification was not accepted")
                    return
                assert isinstance(body, types.JSONRPCRequest)
                if response.status_code == 202:
                    raise McpHttpError("MCP HTTP request has no response; outcome may be unknown")
                if method == "initialize" and response.status_code < 400:
                    session_id = response.headers.get("mcp-session-id")
                    if session_id is not None:
                        if not session_id or len(session_id) > 1024 or any(not 33 <= ord(char) <= 126 for char in session_id):
                            raise McpHttpError("MCP HTTP session identifier is invalid")
                        state.session_id = session_id
                if content_type not in {"application/json", "text/event-stream"}:
                    raise McpHttpError("MCP HTTP response has an unsupported content type")
                if response.status_code >= 400 and content_type != "application/json":
                    raise McpHttpError("MCP HTTP server rejected the request")
                limit = MAX_HTTP_BODY_BYTES if content_type == "application/json" else MAX_SSE_BODY_BYTES
                if not isinstance(response.stream, httpx2.AsyncByteStream):
                    raise McpHttpError("MCP HTTP response stream is unsupported")
                response.stream = _BoundedBody(response.stream, limit)
                if content_type == "application/json":
                    data = await response.aread()
                    parsed = _parse_message(data).message
                    if response.status_code >= 400 and not isinstance(parsed, types.JSONRPCError):
                        raise McpHttpError("MCP HTTP server rejected the request")
                    if method == "initialize" and isinstance(parsed, types.JSONRPCResponse):
                        version = parsed.result.get("protocolVersion")
                        if isinstance(version, str):
                            state.protocol_version = version
                    if not await deliver(data, body.id):
                        raise McpHttpError("MCP HTTP JSON response contains no result")
                else:
                    async for event in httpx2.EventSource(response, max_event_size=MAX_HTTP_BODY_BYTES):
                        if event.event == "message" and event.data:
                            parsed = _parse_message(event.data).message
                            if method == "initialize" and isinstance(parsed, types.JSONRPCResponse):
                                version = parsed.result.get("protocolVersion")
                                if isinstance(version, str):
                                    state.protocol_version = version
                            if await deliver(event.data, body.id):
                                return
                    raise McpHttpError("MCP HTTP stream ended without a result; no automatic resumption or replay")
            finally:
                await response.aclose()

        async def worker(message: SessionMessage, scope: anyio.CancelScope) -> None:
            body = message.message
            request_id = body.id if isinstance(body, types.JSONRPCRequest) else None
            try:
                with scope, anyio.fail_after(request_timeout), http_diagnostics():
                    await post(message)
            except (anyio.ClosedResourceError, anyio.BrokenResourceError):
                pass
            except (McpHttpError, SchemaContractError, PermissionError) as error:
                fail(error)
            except Exception:
                fail(McpHttpError("MCP HTTP transport failed; outcome may be unknown; no automatic replay"))
            finally:
                if request_id is not None and active.get(request_id) is scope:
                    active.pop(request_id, None)

        async with anyio.create_task_group() as group:
            async def writer() -> None:
                async with outgoing:
                    async for message in outgoing:
                        body = message.message
                        if isinstance(body, types.JSONRPCNotification) and body.method == "notifications/cancelled":
                            target = (body.params or {}).get("requestId")
                            if type(target) in {str, int} and target in active:
                                active[target].cancel()
                            if state.protocol_version == "2026-07-28":
                                continue
                        if isinstance(message.metadata, ClientMessageMetadata):
                            version = (message.metadata.headers or {}).get("Mcp-Protocol-Version")
                            if version and getattr(body, "method", None) != "initialize":
                                state.protocol_version = version
                        scope = anyio.CancelScope()
                        if isinstance(body, types.JSONRPCRequest):
                            active[body.id] = scope
                        context = outgoing.last_context
                        if context is None:
                            group.start_soon(worker, message, scope)
                        else:
                            context.run(group.start_soon, worker, message, scope)

            group.start_soon(writer)
            try:
                yield read_stream, write_stream
            finally:
                state.closed = True
                incoming.close()
                write_stream.close()
                for scope in active.values():
                    scope.cancel()
                try:
                    if state.session_id:
                        with anyio.move_on_after(HTTP_SHUTDOWN_TIMEOUT_SECONDS, shield=True) as cleanup, http_diagnostics():
                            try:
                                request = client.build_request("DELETE", endpoint, headers=request_headers())
                                authorize_cleanup()
                                response = await client.send(request, stream=True, follow_redirects=False)
                                try:
                                    # Legacy servers may explicitly decline session deletion.
                                    if not 200 <= response.status_code < 300 and response.status_code != 405:
                                        raise McpHttpError("MCP HTTP session cleanup was rejected")
                                finally:
                                    await response.aclose()
                            except PermissionError:
                                raise McpHttpError("MCP HTTP cleanup denied by active access policy") from None
                            except McpHttpError:
                                raise
                            except Exception:
                                raise McpHttpError("MCP HTTP session cleanup failed; remote state is unknown") from None
                        if cleanup.cancelled_caught:
                            raise McpHttpError("MCP HTTP session cleanup deadline exceeded; remote state is unknown")
                finally:
                    group.cancel_scope.cancel()
        await read_stream.aclose()
        await outgoing.aclose()
