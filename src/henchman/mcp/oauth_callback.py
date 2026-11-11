"""One owned, bounded native-loopback OAuth callback with value-free responses."""

from __future__ import annotations

import asyncio
import ipaddress
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Self
from urllib.parse import parse_qsl, urlsplit

from henchman.config.mcp import oauth_origin, validate_oauth_url
from henchman.mcp.client import _join_session_task
from henchman.mcp.oauth import OAuthError
from henchman.utils.evidence_redaction import EvidenceRedactor

CALLBACK_REQUEST_TIMEOUT = 5.0
CALLBACK_CLEANUP_TIMEOUT = 2.0
CALLBACK_HEADER_BYTES = 8192
CALLBACK_MAX_CONNECTIONS = 16
CALLBACK_MAX_REQUESTS = 32
_PATH = "/oauth/callback"


@dataclass(frozen=True, repr=False)
class OAuthCode:
    """A code is transient execution data, never printable evidence."""

    code: str


class OAuthCallback:
    """Own a loopback listener and every accepted connection until settled."""

    def __init__(
        self, *, state: str, issuer: str, require_iss: bool, evidence: EvidenceRedactor,
        authorize: Callable[[], None], authorization_origin: str | None = None,
    ) -> None:
        validate_oauth_url(issuer)
        if not state or not state.isascii() or len(state) > 256:
            raise OAuthError("OAuth callback state is invalid")
        self._state, self._issuer, self._require_iss = state, issuer, require_iss
        self._evidence, self._authorize = evidence, authorize
        self._origin = authorization_origin or oauth_origin(issuer)
        self._evidence.register_secret(state)
        self._server: asyncio.Server | None = None
        self._result: asyncio.Future[OAuthCode] | None = None
        self._tasks: set[asyncio.Task[None]] = set()
        self._writers: set[asyncio.StreamWriter] = set()
        self._requests = 0
        self._closing = False
        self._consumed = False
        self.redirect_uri = ""

    async def __aenter__(self) -> Self:
        if self._result is not None:
            raise OAuthError("OAuth callback cannot be reused")
        self._result = asyncio.get_running_loop().create_future()
        try:
            for host in ("127.0.0.1", "::1"):
                self._authorize()
                try:
                    self._server = await asyncio.start_server(self._accept, host, 0, limit=CALLBACK_HEADER_BYTES)
                except OSError:
                    continue
                address = self._server.sockets[0].getsockname()
                authority = f"[{host}]:{address[1]}" if ":" in host else f"{host}:{address[1]}"
                self.redirect_uri = f"http://{authority}{_PATH}"
                return self
            raise OAuthError("OAuth loopback callback could not bind an interface")
        except BaseException:
            await self.close()
            raise

    async def __aexit__(self, *_args: Any) -> None:
        await self.close()

    def _fail(self, message: str) -> None:
        if self._result is not None and not self._result.done():
            self._result.set_exception(OAuthError(message))

    def _accept(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._requests += 1
        if self._closing or len(self._tasks) >= CALLBACK_MAX_CONNECTIONS or self._requests > CALLBACK_MAX_REQUESTS:
            writer.close()
            writer.transport.abort()
            if self._requests > CALLBACK_MAX_REQUESTS:
                self._fail("OAuth callback request limit exceeded")
            return
        self._writers.add(writer)
        task = asyncio.create_task(self._handle(reader, writer), name="henchman-oauth-callback-request")
        self._tasks.add(task)

        def settled(done: asyncio.Task[None]) -> None:
            self._tasks.discard(done)
            if not done.cancelled() and done.exception() is not None:
                self._fail("OAuth callback connection failed")

        task.add_done_callback(settled)

    def _parameters(self, raw: bytes, writer: asyncio.StreamWriter) -> dict[str, str]:
        if len(raw) > CALLBACK_HEADER_BYTES:
            raise ValueError
        peer = writer.get_extra_info("peername")
        if not peer or not ipaddress.ip_address(peer[0]).is_loopback:
            raise ValueError
        lines = raw.decode("ascii").split("\r\n")
        method, target, version = lines[0].split(" ")
        if method != "GET" or version != "HTTP/1.1":
            raise ValueError
        fields: dict[str, str] = {}
        for line in lines[1:]:
            if not line:
                continue
            key, separator, value = line.partition(":")
            key = key.lower()
            if (not separator or not re.fullmatch(r"[a-z0-9-]+", key) or key in fields
                or any(ord(char) < 32 or ord(char) == 127 for char in value)):
                raise ValueError
            fields[key] = value.strip()
        if (fields.get("host") != urlsplit(self.redirect_uri).netloc
            or fields.get("content-length", "0") != "0" or "transfer-encoding" in fields
            or ("origin" in fields and fields["origin"] != self._origin)):
            raise ValueError
        parsed = urlsplit(target)
        if (parsed.scheme or parsed.netloc or parsed.fragment or parsed.path != _PATH
            or re.search(r"%(?![0-9a-fA-F]{2})", parsed.query)):
            raise ValueError
        pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True, errors="strict", max_num_fields=16)
        parameters = dict(pairs)
        if len(parameters) != len(pairs):
            raise ValueError
        for key in ("code", "state"):
            self._evidence.register_secret(parameters.get(key, ""))
        state = parameters.get("state", "")
        if not state.isascii() or not secrets.compare_digest(state, self._state):
            raise ValueError
        return parameters

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        accepted = False
        try:
            async with asyncio.timeout(CALLBACK_REQUEST_TIMEOUT):
                try:
                    parameters = self._parameters(await reader.readuntil(b"\r\n\r\n"), writer)
                except (ValueError, UnicodeError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
                    parameters = None
                if parameters is not None:
                    iss = parameters.get("iss")
                    if (iss is not None and iss != self._issuer) or (iss is None and self._require_iss):
                        self._fail("OAuth callback issuer validation failed")
                    elif "error" in parameters:
                        self._fail("OAuth authorization was rejected; remote error details withheld")
                    elif (not parameters.get("code") or len(parameters["code"]) > 4096
                          or any(ord(char) < 32 or ord(char) == 127 for char in parameters["code"])):
                        self._fail("OAuth callback code is invalid")
                    elif self._result is not None and not self._result.done():
                        self._authorize()
                        self._result.set_result(OAuthCode(parameters["code"]))
                        accepted = True
                body = b"Authorization response received. Return to Henchman." if accepted else b"Authorization response rejected."
                status = b"200 OK" if accepted else b"400 Bad Request"
                writer.write(b"HTTP/1.1 " + status + b"\r\nContent-Type: text/plain; charset=utf-8\r\n"
                             b"Cache-Control: no-store\r\nReferrer-Policy: no-referrer\r\n"
                             b"Content-Security-Policy: default-src 'none'\r\nConnection: close\r\nContent-Length: "
                             + str(len(body)).encode() + b"\r\n\r\n" + body)
                await writer.drain()
        except (TimeoutError, ConnectionError):
            pass
        except asyncio.CancelledError:
            raise
        except Exception:
            self._fail("OAuth callback failed or its authority changed")
        finally:
            writer.close()
            writer.transport.abort()
            self._writers.discard(writer)

    async def wait_code(self) -> OAuthCode:
        if self._result is None or self._consumed:
            raise OAuthError("OAuth callback code is unavailable or already consumed")
        self._consumed = True
        return await asyncio.shield(self._result)

    async def _close_owned(self) -> None:
        self._closing = True
        if self._server is not None:
            self._server.close()
        try:
            async with asyncio.timeout(CALLBACK_CLEANUP_TIMEOUT):
                while self._tasks or self._writers:
                    tasks, writers = tuple(self._tasks), tuple(self._writers)
                    for writer in writers:
                        writer.close()
                        writer.transport.abort()
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    # Completed gather may not yield on Python 3.12+. Retire
                    # our joined snapshot without depending on done callbacks.
                    self._tasks.difference_update(tasks)
                    self._writers.difference_update(writers)
                if self._server is not None:
                    await self._server.wait_closed()
        finally:
            if self._result is not None:
                if not self._result.done():
                    self._result.cancel()
                elif not self._result.cancelled():
                    self._result.exception()

    async def close(self) -> None:
        task = asyncio.create_task(self._close_owned(), name="henchman-oauth-callback-cleanup")
        await _join_session_task(task)
