"""DNS and connected-peer checks for anonymous or explicitly URL-authenticated HTTP."""

from __future__ import annotations

import inspect
import socket
import ssl
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, ClassVar

from aiohttp import ClientRequest, ClientResponse, ClientSession
from aiohttp.abc import AbstractResolver
from aiohttp.resolver import ThreadedResolver
from yarl import URL

from henchman.tools.access_policy import (
    ToolAccessError,
    check_network_access,
    current_access_policies,
)
from henchman.tools.security import SSRFError, validate_public_ip, validate_url

if TYPE_CHECKING:
    from aiohttp.abc import ResolveResult
    from aiohttp.connector import Connection

_AddressInfo = tuple[int, int, int, str, tuple[str, int] | tuple[str, int, int, int]]


def supports_network_socket_guard() -> bool:
    """Require the public per-attempt connector hook for restricted HTTP."""
    import aiohttp

    try:
        return "socket_factory" in inspect.signature(aiohttp.TCPConnector).parameters
    except (TypeError, ValueError):
        return False


def checked_http_url(value: str) -> URL:
    """Apply literal/syntax checks using the same URL parser as the transport."""
    validate_url(value)
    try:
        url = URL(value)
        if url.scheme not in {"http", "https"} or not url.raw_host or url.port is None:
            raise ValueError("Missing HTTP authority")
    except ValueError:
        raise SSRFError("Invalid HTTP URL") from None
    return url


def request_origin(url: URL) -> tuple[str, str, int]:
    """Compare canonical scheme, IDNA/IP host and effective port, including defaults."""
    host, port = url.raw_host, url.port
    if host is None or port is None:
        raise SSRFError("HTTP request requires an authority")
    return url.scheme, host, port


class PublicAddressResolver(AbstractResolver):
    """Validate every OS DNS result and return only pinned numeric connect targets."""

    def __init__(self, delegate: AbstractResolver | None = None) -> None:
        self._delegate = delegate if delegate is not None else ThreadedResolver()

    async def resolve(
        self, host: str, port: int = 0, family: socket.AddressFamily = socket.AF_INET,
    ) -> list[ResolveResult]:
        """Reject the entire answer set if any candidate is unsafe or malformed."""
        check_network_access(host)
        answers = await self._delegate.resolve(host, port, family=family)
        check_network_access(host)
        if not answers:
            raise SSRFError("DNS returned no approved addresses")
        checked: list[ResolveResult] = []
        for answer in answers:
            address = validate_public_ip(answer["host"])
            if answer["port"] != port:
                raise SSRFError("DNS returned an unexpected destination port")
            checked.append({
                "hostname": host,
                "host": address,
                "port": port,
                "family": socket.AF_INET6 if ":" in address else socket.AF_INET,
                "proto": socket.IPPROTO_TCP,
                "flags": socket.AI_NUMERICHOST | socket.AI_NUMERICSERV,
            })
        return checked

    async def close(self) -> None:
        """Release resolver resources owned by this fetch."""
        await self._delegate.close()


class PeerCheckedRequest(ClientRequest):
    """Reject an unsafe connected peer before aiohttp writes request headers."""

    _network_target: ClassVar[URL | None] = None

    async def send(self, conn: Connection) -> ClientResponse:
        transport = conn.transport
        peer = transport.get_extra_info("peername") if transport is not None else None
        if not isinstance(peer, tuple) or len(peer) < 2 or not isinstance(peer[0], str):
            conn.close()
            raise SSRFError("Connected peer identity is unavailable")
        try:
            if self._network_target is not None and request_origin(self.url) != request_origin(self._network_target):
                raise ToolAccessError("HTTP request authority changed inside its transport scope")
            host = self.url.raw_host
            if host is None:
                raise SSRFError("HTTP request authority is unavailable")
            check_network_access(host)
            validate_public_ip(peer[0])
            if peer[1] != self.url.port:
                raise SSRFError("Connected peer port differs from the requested authority")
            # Bodyless GET with no traces flushes synchronously in supported
            # aiohttp versions. A paused protocol instead schedules a later
            # writer task, which cannot retain this no-await authorization.
            if getattr(conn.protocol, "writing_paused", False):
                raise ToolAccessError("Deferred HTTP header dispatch is unsupported under mediated transport")
        except (SSRFError, ToolAccessError, ValueError, OSError):
            conn.close()
            raise
        return await super().send(conn)


@asynccontextmanager
async def public_http_session(
    *, resolver: AbstractResolver | None = None, ssl_context: ssl.SSLContext | None = None,
    authority: URL | None = None,
) -> AsyncIterator[ClientSession]:
    """Own a direct TLS-verifying session with no ambient proxy/auth/cookie state.

    Restricted calls require a public socket_factory hook. Unrestricted aiohttp
    3.9 retains DNS/header checks, but cannot revoke every already scheduled TCP
    attempt. No private connector override or ambient proxy state is used.
    """
    import aiohttp

    capable = supports_network_socket_guard()
    if any(policy.restricted for policy in current_access_policies()) and (not capable or authority is None):
        raise ToolAccessError("Restricted HTTP requires an explicit authority and aiohttp socket_factory capability")
    if authority is not None:
        assert authority.raw_host is not None
        check_network_access(authority.raw_host)
    context = ssl_context if ssl_context is not None else ssl.create_default_context()
    if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
        raise SSRFError("HTTP TLS requires certificate and hostname verification")
    checked_resolver = PublicAddressResolver(resolver)
    if authority is not None and capable:
        target = authority

        def checked_socket(address_info: _AddressInfo) -> socket.socket:
            assert target.raw_host is not None
            check_network_access(target.raw_host)
            family, kind, protocol, _name, address = address_info
            validate_public_ip(address[0])
            if (family not in (socket.AF_INET, socket.AF_INET6) or kind != socket.SOCK_STREAM
                or protocol not in (0, socket.IPPROTO_TCP) or address[1] != target.port):
                raise SSRFError("Socket destination differs from the requested HTTP authority")
            return socket.socket(family=family, type=kind, proto=protocol)

        connector = aiohttp.TCPConnector(
            resolver=checked_resolver, use_dns_cache=False, force_close=True,
            ssl=context, socket_factory=checked_socket,
        )
    else:
        connector = aiohttp.TCPConnector(
            resolver=checked_resolver, use_dns_cache=False, force_close=True,
            # An explicit verified context has stable aiohttp 3.9+ semantics.
            ssl=context,
        )

    class AuthorityCheckedRequest(PeerCheckedRequest):
        _network_target = authority

    try:
        async with aiohttp.ClientSession(
            connector=connector, request_class=AuthorityCheckedRequest,
            trust_env=False, cookie_jar=aiohttp.DummyCookieJar(),
        ) as session:
            yield session
    finally:
        if not connector.closed:
            await connector.close()
        await checked_resolver.close()
