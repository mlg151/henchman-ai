"""DNS and connected-peer checks for anonymous or explicitly URL-authenticated HTTP."""

from __future__ import annotations

import socket
import ssl
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from aiohttp import ClientRequest, ClientResponse, ClientSession
from aiohttp.abc import AbstractResolver
from aiohttp.resolver import ThreadedResolver
from yarl import URL

from henchman.tools.security import SSRFError, validate_public_ip, validate_url

if TYPE_CHECKING:
    from aiohttp.abc import ResolveResult
    from aiohttp.connector import Connection


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
        answers = await self._delegate.resolve(host, port, family=family)
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

    async def send(self, conn: Connection) -> ClientResponse:
        transport = conn.transport
        peer = transport.get_extra_info("peername") if transport is not None else None
        if not isinstance(peer, tuple) or len(peer) < 2 or not isinstance(peer[0], str):
            conn.close()
            raise SSRFError("Connected peer identity is unavailable")
        try:
            validate_public_ip(peer[0])
            if peer[1] != self.url.port:
                raise SSRFError("Connected peer port differs from the requested authority")
        except SSRFError:
            conn.close()
            raise
        return await super().send(conn)


@asynccontextmanager
async def public_http_session(
    *, resolver: AbstractResolver | None = None, ssl_context: ssl.SSLContext | None = None,
) -> AsyncIterator[ClientSession]:
    """Own a direct TLS-verifying session with no ambient proxy/auth/cookie state.

    Resolver/request-class constructor hooks work with the declared aiohttp 3.9
    minimum. No private connector override or newer socket-factory hook is used.
    """
    import aiohttp

    context = ssl_context if ssl_context is not None else ssl.create_default_context()
    if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
        raise SSRFError("HTTP TLS requires certificate and hostname verification")
    checked_resolver = PublicAddressResolver(resolver)
    connector = aiohttp.TCPConnector(
        resolver=checked_resolver, use_dns_cache=False, force_close=True,
        # In aiohttp 3.9, ssl=True selects an unverified context. An explicit
        # verified context has stable semantics across supported releases.
        ssl=context,
    )
    try:
        async with aiohttp.ClientSession(
            connector=connector, request_class=PeerCheckedRequest,
            trust_env=False, cookie_jar=aiohttp.DummyCookieJar(),
        ) as session:
            yield session
    finally:
        if not connector.closed:
            await connector.close()
        await checked_resolver.close()
