"""SSRF policy checks resolved and connected peers before HTTP request bytes."""

import asyncio
import contextlib
import inspect
import socket
import ssl
from collections.abc import AsyncIterator, Awaitable, Callable
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from yarl import URL

from henchman.tools.builtins.web_fetch import WebFetchTool
from henchman.tools.http_security import PublicAddressResolver, request_origin
from henchman.tools.security import SSRFError, validate_url


@pytest.mark.parametrize("host", [
    "127.1", "2130706433", "0x7f000001", "0177.0.0.1", "127.0.0.2", "localhost.",
    "sub.localhost", "[::ffff:127.0.0.1]", "[::]", "[fe80::1%25eth0]", "100.64.0.1",
    "224.0.0.1", "[ff02::1]", "[fec0::1]", "[64:ff9b::7f00:1]",
])
def test_private_and_special_url_aliases_are_rejected(host: str) -> None:
    with pytest.raises(SSRFError):
        validate_url(f"http://{host}/secret")


@contextlib.asynccontextmanager
async def local_server(
    response: Callable[[bytes], bytes | Awaitable[bytes]] | None = None,
    **kwargs,
) -> AsyncIterator[tuple[int, list[bytes]]]:
    """Record actual HTTP bytes; no request ever leaves the local fixture."""
    received: list[bytes] = []
    writers: set[asyncio.StreamWriter] = set()
    tasks: set[asyncio.Task] = set()

    async def serve(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writers.add(writer)
        task = asyncio.current_task()
        assert task is not None
        tasks.add(task)
        try:
            try:
                data = await reader.readuntil(b"\r\n\r\n")
            except asyncio.IncompleteReadError as exc:
                data = exc.partial
            received.append(data)
            if data:
                payload = response(data) if response is not None else b"HTTP/1.1 200 OK\r\nContent-Length: 14\r\n\r\nprivate canary"
                if inspect.isawaitable(payload):
                    payload = await payload
                writer.write(payload)
                await writer.drain()
        finally:
            writer.close()
            with contextlib.suppress(ConnectionError):
                await writer.wait_closed()
            writers.discard(writer)
            tasks.discard(task)

    server = await asyncio.start_server(serve, "127.0.0.1", 0, **kwargs)
    try:
        yield server.sockets[0].getsockname()[1], received
    finally:
        server.close()
        for writer in tuple(writers):
            writer.close()
        pending = tuple(tasks)
        if pending:
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
        # Python 3.12 also waits for accepted connections here. Release our
        # writers and blocked response handlers before joining the listener.
        await server.wait_closed()


def route_dns_to(monkeypatch, records: list[str]) -> list[str]:
    """Supply numeric OS resolver answers without external DNS or connections."""
    loop = asyncio.get_running_loop()
    original = loop.getaddrinfo
    calls: list[str] = []

    async def resolve(host, port, *args, **kwargs):
        if host.endswith(".test"):
            calls.append(host)
            return [(socket.AF_INET6 if ":" in address else socket.AF_INET, socket.SOCK_STREAM,
                     socket.IPPROTO_TCP, "", (address, port, 0, 0) if ":" in address else (address, port))
                    for address in records]
        return await original(host, port, *args, **kwargs)

    monkeypatch.setattr(loop, "getaddrinfo", resolve)
    return calls


async def test_dns_name_resolving_to_loopback_is_rejected_before_request(monkeypatch) -> None:
    route_dns_to(monkeypatch, ["127.0.0.1"])
    async with local_server() as (port, received):
        result = await WebFetchTool().execute(url=f"http://private.test:{port}/secret")
    assert not result.success
    assert "private canary" not in result.content
    assert not any(received)


async def test_numeric_alias_cannot_reach_local_server() -> None:
    async with local_server() as (port, received):
        result = await WebFetchTool().execute(url=f"http://127.1:{port}/secret")
    assert not result.success
    assert not any(received)


@pytest.mark.parametrize("unsafe", ["127.0.0.2", "169.254.169.254", "::ffff:127.0.0.1", "fe80::1%eth0"])
async def test_mixed_dns_answer_sets_fail_as_a_whole(unsafe: str) -> None:
    delegate = AsyncMock()
    delegate.resolve.return_value = [
        {"hostname": "mixed.test", "host": address, "port": 443, "family": socket.AF_INET,
         "proto": socket.IPPROTO_TCP, "flags": 0} for address in ("8.8.8.8", unsafe)
    ]
    resolver = PublicAddressResolver(delegate)
    with pytest.raises(SSRFError):
        await resolver.resolve("mixed.test", 443)
    await resolver.close()
    delegate.close.assert_awaited_once()


def route_public_connections_locally(monkeypatch) -> list[tuple]:
    """Redirect only a fixture's admitted numeric address to a real local socket."""
    loop = asyncio.get_running_loop()
    original = loop.sock_connect
    original_create = loop.create_connection
    legacy_route: ContextVar[bool] = ContextVar("fixture_numeric_route", default=False)
    connects: list[tuple] = []

    async def connect(sock, address):
        if legacy_route.get() and address[0] == "127.0.0.1":
            return await original(sock, address)
        connects.append(address)
        assert address[0] == "8.8.8.8", f"Unexpected test connection: {address}"
        await original(sock, ("127.0.0.1", address[1]))

    async def create(protocol_factory, host=None, port=None, **kwargs):
        # aiohttp 3.9 supplies numeric host/port to this public loop method;
        # newer versions supply an already-connected socket. Route before the
        # offline guard, retaining the explicit TLS server_hostname unchanged.
        if host == "8.8.8.8":
            connects.append((host, port))
            token = legacy_route.set(True)
            try:
                return await original_create(protocol_factory, "127.0.0.1", port, **kwargs)
            finally:
                legacy_route.reset(token)
        return await original_create(protocol_factory, host, port, **kwargs)

    monkeypatch.setattr(loop, "sock_connect", connect)
    monkeypatch.setattr(loop, "create_connection", create)
    return connects


def admit_local_fixture_peer(monkeypatch) -> None:
    """Permit only the fixture peer for positive HTTP/TLS tests, never production."""
    from henchman.tools import http_security

    original = http_security.validate_public_ip
    monkeypatch.setattr(http_security, "validate_public_ip", lambda address:
                        "127.0.0.1" if address == "127.0.0.1" else original(address))


async def test_connected_private_peer_is_rejected_before_any_http_bytes(monkeypatch) -> None:
    dns = route_dns_to(monkeypatch, ["8.8.8.8"])
    connects = route_public_connections_locally(monkeypatch)
    async with local_server() as (port, received):
        result = await WebFetchTool().execute(url=f"http://public.test:{port}/secret")
    assert not result.success
    assert dns == ["public.test"]
    assert connects == [("8.8.8.8", port)]
    assert not any(received)


@pytest.mark.parametrize("location", [
    "http://127.1/secret", "http://2130706433/secret", "http://[::ffff:127.0.0.1]/secret",
    "http://169.254.169.254/secret", "//localhost./secret", "file:///etc/passwd",
])
async def test_every_redirect_target_is_checked_before_connect(monkeypatch, location: str) -> None:
    route_dns_to(monkeypatch, ["8.8.8.8"])
    connects = route_public_connections_locally(monkeypatch)
    admit_local_fixture_peer(monkeypatch)
    response = f"HTTP/1.1 302 Found\r\nLocation: {location}\r\nContent-Length: 0\r\n\r\n".encode()
    async with local_server(lambda _: response) as (port, received):
        result = await WebFetchTool().execute(url=f"http://public.test:{port}/redirect")
    assert not result.success
    assert len(connects) == 1
    assert len([request for request in received if request]) == 1


async def test_dns_rebinding_on_redirect_cannot_reach_second_address(monkeypatch) -> None:
    answers = ["8.8.8.8"]
    dns = route_dns_to(monkeypatch, answers)
    connects = route_public_connections_locally(monkeypatch)
    admit_local_fixture_peer(monkeypatch)

    def response(_request):
        answers[:] = ["127.0.0.2"]
        return b"HTTP/1.1 302 Found\r\nLocation: /second\r\nContent-Length: 0\r\n\r\n"

    async with local_server(response) as (port, received):
        result = await WebFetchTool().execute(url=f"http://rebound.test:{port}/first")
    assert not result.success
    assert dns == ["rebound.test", "rebound.test"]
    assert len(connects) == 1
    assert len([request for request in received if request]) == 1


@pytest.mark.parametrize("second_host", ["first.test", "other.test"])
async def test_cross_authority_redirect_drops_auth_and_never_reintroduces_it(monkeypatch, second_host: str) -> None:
    route_dns_to(monkeypatch, ["8.8.8.8"])
    route_public_connections_locally(monkeypatch)
    admit_local_fixture_peer(monkeypatch)
    ports = {}

    def first_response(request):
        if request.startswith(b"GET /return "):
            return b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok"
        return (f"HTTP/1.1 302 Found\r\nLocation: http://{second_host}:{ports['second']}/next\r\n"
                "Set-Cookie: session=private-cookie; Path=/\r\nContent-Length: 0\r\n\r\n").encode()

    def second_response(_request):
        return (f"HTTP/1.1 302 Found\r\nLocation: http://first.test:{ports['first']}/return\r\n"
                "Content-Length: 0\r\n\r\n").encode()

    async with local_server(first_response) as (first_port, first), local_server(second_response) as (second_port, second):
        ports.update(first=first_port, second=second_port)
        result = await WebFetchTool().execute(url=f"http://user:private-password@first.test:{first_port}/start")
    assert result.success, result.content
    assert b"Authorization: Basic " in first[0]
    assert b"Authorization:" not in second[0]
    assert b"Cookie:" not in second[0]
    assert b"Authorization:" not in first[1]
    assert b"Cookie:" not in first[1]
    assert "private-password" not in result.content


async def test_same_origin_relative_redirect_retains_only_explicit_initial_auth(monkeypatch) -> None:
    route_dns_to(monkeypatch, ["8.8.8.8"])
    route_public_connections_locally(monkeypatch)
    admit_local_fixture_peer(monkeypatch)

    def response(request):
        if request.startswith(b"GET /finish "):
            return b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok"
        return b"HTTP/1.1 302 Found\r\nLocation: /finish\r\nContent-Length: 0\r\n\r\n"

    async with local_server(response) as (port, received):
        result = await WebFetchTool().execute(url=f"http://user:password@public.test:{port}/start")
    assert result.success
    assert len(received) == 2
    assert all(b"Authorization: Basic " in request for request in received)


async def test_redirect_userinfo_cannot_introduce_new_credentials(monkeypatch) -> None:
    route_dns_to(monkeypatch, ["8.8.8.8"])
    connects = route_public_connections_locally(monkeypatch)
    admit_local_fixture_peer(monkeypatch)
    response = b"HTTP/1.1 302 Found\r\nLocation: http://user:secret@next.test/path\r\nContent-Length: 0\r\n\r\n"
    async with local_server(lambda _: response) as (port, _received):
        result = await WebFetchTool().execute(url=f"http://first.test:{port}/start")
    assert not result.success
    assert len(connects) == 1
    assert "secret" not in result.content


@pytest.mark.parametrize("first,second", [
    ("https://EXAMPLE.test", "https://example.test:443"),
    ("http://example.test", "http://example.test:80"),
    ("https://[2001:4860:4860:0:0:0:0:8888]", "https://[2001:4860:4860::8888]:443"),
])
def test_effective_origins_normalize_hosts_ipv6_and_default_ports(first: str, second: str) -> None:
    assert request_origin(URL(first)) == request_origin(URL(second))
    assert request_origin(URL(first)) != request_origin(URL(second).with_port(8443))


def tls_contexts(tmp_path):
    """Create an ephemeral test CA/certificate with a public.test DNS identity."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "public.test")])
    now = datetime.now(UTC)
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("public.test")]), critical=False)
            .sign(key, hashes.SHA256()))
    certificate = tmp_path / "test-certificate.pem"
    certificate.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    private_key = tmp_path / "test-key.pem"
    private_key.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                              serialization.NoEncryption()))
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(certificate, private_key)
    client_context = ssl.create_default_context(cafile=str(certificate))
    return server_context, client_context


@pytest.mark.parametrize("hostname,success", [("public.test", True), ("wrong.test", False)])
async def test_real_tls_keeps_original_sni_and_verifies_certificate_hostname(
    tmp_path, monkeypatch, hostname: str, success: bool,
) -> None:
    from henchman.tools.builtins import web_fetch

    route_dns_to(monkeypatch, ["8.8.8.8"])
    route_public_connections_locally(monkeypatch)
    admit_local_fixture_peer(monkeypatch)
    server_context, client_context = tls_contexts(tmp_path)
    sni = []
    server_context.set_servername_callback(lambda _socket, name, _context: sni.append(name))
    original_session = web_fetch.public_http_session
    monkeypatch.setattr(web_fetch, "public_http_session", lambda **kwargs: original_session(ssl_context=client_context, **kwargs))
    async with local_server(ssl=server_context) as (port, received):
        result = await WebFetchTool().execute(url=f"https://{hostname}:{port}/secure")
    assert result.success is success, result.content
    assert sni == [hostname]
    assert bool(any(received)) is success
    if success:
        assert f"Host: {hostname}:{port}".encode() in received[0]


async def test_real_tls_rejects_an_untrusted_certificate(tmp_path, monkeypatch) -> None:
    route_dns_to(monkeypatch, ["8.8.8.8"])
    route_public_connections_locally(monkeypatch)
    admit_local_fixture_peer(monkeypatch)
    server_context, _unused_client_context = tls_contexts(tmp_path)
    async with local_server(ssl=server_context) as (port, received):
        result = await WebFetchTool().execute(url=f"https://public.test:{port}/secure")
    assert not result.success
    assert not any(received)


async def test_transport_rejects_nonverifying_ssl_context() -> None:
    from henchman.tools.http_security import public_http_session

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with pytest.raises(SSRFError):
        async with public_http_session(ssl_context=context):
            pytest.fail("Unverified TLS session was accepted")


@pytest.mark.parametrize("cancel", [True, False])
async def test_cancellation_and_timeout_close_owned_connections(monkeypatch, cancel: bool) -> None:
    from henchman.tools.builtins import web_fetch

    route_dns_to(monkeypatch, ["8.8.8.8"])
    route_public_connections_locally(monkeypatch)
    admit_local_fixture_peer(monkeypatch)
    entered = asyncio.Event()
    sessions = []
    connectors = []
    original_session = web_fetch.public_http_session

    @contextlib.asynccontextmanager
    async def capture(**kwargs):
        async with original_session(**kwargs) as session:
            sessions.append(session)
            connectors.append(session.connector)
            yield session

    monkeypatch.setattr(web_fetch, "public_http_session", capture)

    async def response(_request):
        entered.set()
        await asyncio.Event().wait()
        return b""

    async with local_server(response) as (port, _received):
        task = asyncio.create_task(WebFetchTool().execute(url=f"http://public.test:{port}/wait", timeout=1))
        await asyncio.wait_for(entered.wait(), 2)
        if cancel:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            result = await asyncio.wait_for(task, 2)
            assert not result.success
            assert "timeout" in result.error.lower()
    assert sessions[0].closed
    assert connectors[0].closed


async def test_redirects_share_one_total_timeout(monkeypatch) -> None:
    route_dns_to(monkeypatch, ["8.8.8.8"])
    route_public_connections_locally(monkeypatch)
    admit_local_fixture_peer(monkeypatch)

    async def response(_request):
        await asyncio.sleep(0.6)
        return b"HTTP/1.1 302 Found\r\nLocation: /again\r\nContent-Length: 0\r\n\r\n"

    async with local_server(response) as (port, received):
        result = await asyncio.wait_for(WebFetchTool().execute(url=f"http://public.test:{port}/start", timeout=1), 2)
    assert not result.success
    assert "timeout" in result.error.lower()
    assert len([request for request in received if request]) == 2


async def test_environment_proxy_and_netrc_credentials_are_not_used(tmp_path, monkeypatch) -> None:
    dns = route_dns_to(monkeypatch, ["8.8.8.8"])
    route_public_connections_locally(monkeypatch)
    admit_local_fixture_peer(monkeypatch)
    credentials = tmp_path / "netrc"
    credentials.write_text("machine public.test login ambient-user password ambient-secret\n")
    monkeypatch.setenv("NETRC", str(credentials))
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.test:9000")
    monkeypatch.setenv("http_proxy", "http://proxy.test:9000")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    async with local_server() as (port, received):
        result = await WebFetchTool().execute(url=f"http://public.test:{port}/direct")
    assert result.success, result.content
    assert dns == ["public.test"]
    assert received[0].startswith(b"GET /direct ")
    assert b"Authorization:" not in received[0]


async def test_redirect_loop_has_a_finite_hop_limit(monkeypatch) -> None:
    route_dns_to(monkeypatch, ["8.8.8.8"])
    connects = route_public_connections_locally(monkeypatch)
    admit_local_fixture_peer(monkeypatch)
    response = b"HTTP/1.1 302 Found\r\nLocation: /again\r\nContent-Length: 0\r\n\r\n"
    async with local_server(lambda _: response) as (port, _received):
        result = await WebFetchTool().execute(url=f"http://public.test:{port}/start")
    assert not result.success
    assert "redirect limit" in result.content
    assert len(connects) == 11
