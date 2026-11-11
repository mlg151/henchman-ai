"""Host policy and live HTTP authority use scoped registry boundaries."""

import asyncio
import inspect

import aiohttp
import pytest

from henchman.config.schema import Settings
from henchman.tools.access_policy import ToolAccessError, ToolAccessPolicy, use_access_policies
from henchman.tools.base import ToolResult
from henchman.tools.builtins.web_fetch import WebFetchTool
from henchman.tools.registry import ToolRegistry
from henchman.tools.scoped_registry import ScopedToolRegistry
from henchman.utils.retry import RetryConfig
from tests.tools.test_web_fetch_security import (
    admit_local_fixture_peer,
    local_server,
    route_dns_to,
    route_public_connections_locally,
    tls_contexts,
)

socket_guard = pytest.mark.skipif(
    "socket_factory" not in inspect.signature(aiohttp.TCPConnector).parameters,
    reason="Restricted HTTP requires the public aiohttp socket_factory hook",
)


def policy(root, **settings):
    return ToolAccessPolicy.from_settings(Settings(tools=settings).tools, project_root=root)


def test_host_sets_intersect_and_disabled_overrides(tmp_path):
    from henchman.tools.access_policy import check_network_access

    parent = policy(tmp_path, network_allowed_hosts=["one.test", "two.test"])
    child = policy(tmp_path, network_allowed_hosts=["two.test", "three.test"])
    assert parent.restricted
    with use_access_policies((parent, child)):
        check_network_access("two.test")
        for hostname in ("one.test", "three.test", "sub.two.test", "8.8.8.8"):
            with pytest.raises(ToolAccessError):
                check_network_access(hostname)
    with use_access_policies((parent, policy(tmp_path, network_access="disabled"))), pytest.raises(ToolAccessError):
        check_network_access("one.test")


def test_empty_or_unbound_host_policy_cannot_grant_network(tmp_path):
    from henchman.tools.access_policy import check_network_access

    for restricted in (policy(tmp_path, network_allowed_hosts=[]), ToolAccessPolicy(network_allowed_hosts=("example.test",))):
        with use_access_policies((restricted,)), pytest.raises(ToolAccessError):
            check_network_access("example.test")


@pytest.mark.parametrize("change", [
    "parent_policy", "temporary_policy", "remove", "replace", "method", "grants", "project", "worktree", "guard",
    "existing_guard",
])
async def test_live_lease_rejects_authority_changes_after_an_await(tmp_path, monkeypatch, change):
    from henchman.tools import access_policy
    from henchman.tools.builtins import web_fetch

    project = tmp_path / "project"
    project.mkdir()
    (project / ".git").write_text("gitdir: first\n")
    monkeypatch.chdir(project)
    parent = ToolRegistry(retry_config=RetryConfig(max_retries=0))
    parent.register(WebFetchTool())
    parent.add_auto_approve_policy("web_fetch")
    registry = ScopedToolRegistry(parent, None, inherit_auto_approve=True)
    entered, release = asyncio.Event(), asyncio.Event()
    deny = False
    if change == "existing_guard":
        parent.bind_execution_guard(lambda *_: ToolResult(content="denied", success=False) if deny else None)

    async def controlled(_params):
        access_policy.check_network_access("public.test")
        entered.set()
        await release.wait()
        access_policy.check_network_access("public.test")
        return ToolResult(content="sent")

    monkeypatch.setattr(web_fetch, "_fetch_content_with_aiohttp", controlled)
    invocation = asyncio.create_task(registry.execute("web_fetch", {"url": "https://public.test"}))
    await asyncio.wait_for(entered.wait(), 2)
    if change == "parent_policy":
        parent.set_access_policy(policy(project, network_allowed_hosts=[]))
    elif change == "temporary_policy":
        parent.set_access_policy(policy(project, network_allowed_hosts=[]))
        parent.set_access_policy(ToolAccessPolicy())
    elif change == "remove":
        parent.unregister("web_fetch")
    elif change == "replace":
        parent.unregister("web_fetch")
        parent.register(WebFetchTool())
    elif change == "method":
        monkeypatch.setattr(parent.get("web_fetch"), "execute", controlled)
    elif change == "grants":
        parent.clear_grants()
    elif change == "project":
        monkeypatch.chdir(tmp_path)
        project.rename(tmp_path / "old")
        project.mkdir()
        monkeypatch.chdir(project)
    elif change == "worktree":
        (project / ".git").write_text("gitdir: second\n")
    elif change == "existing_guard":
        deny = True
    else:
        parent.bind_execution_guard(lambda *_args: ToolResult(content="denied", success=False))
    release.set()
    result = await asyncio.wait_for(invocation, 2)
    assert not result.success and result.content != "sent"


@pytest.mark.parametrize("outcome", ["return", "error", "cancel"])
async def test_inherited_lease_closes_when_the_fetch_exits(monkeypatch, outcome):
    from henchman.tools import access_policy
    from henchman.tools.builtins import web_fetch

    registry = ToolRegistry(retry_config=RetryConfig(max_retries=0))
    registry.register(WebFetchTool())
    registry.add_auto_approve_policy("web_fetch")
    release = asyncio.Event()
    entered = asyncio.Event()
    background = []

    async def late():
        await release.wait()
        access_policy.check_network_access("public.test")

    async def controlled(_params):
        background.append(asyncio.create_task(late()))
        entered.set()
        if outcome == "cancel":
            await asyncio.Future()
        if outcome == "error":
            raise RuntimeError("request failed")
        return ToolResult(content="done")

    monkeypatch.setattr(web_fetch, "_fetch_content_with_aiohttp", controlled)
    invocation = asyncio.create_task(registry.execute("web_fetch", {"url": "https://public.test"}))
    await asyncio.wait_for(entered.wait(), 2)
    if outcome == "cancel":
        invocation.cancel()
        with pytest.raises(asyncio.CancelledError):
            await invocation
    else:
        assert (await invocation).success == (outcome == "return")
    release.set()
    with pytest.raises(ToolAccessError, match="closed"):
        await background[0]


async def test_host_only_manager_stays_unbound_before_runtime_and_denies_opaque_tools(tmp_path):
    from henchman.cli.tool_manager import ToolManager
    from henchman.tools.builtins.shell import ShellTool

    manager = ToolManager(Settings(tools={"network_allowed_hosts": ["public.test"]}))
    manager.registry.register(WebFetchTool())
    manager.registry.add_auto_approve_policy("web_fetch")
    assert manager.registry._effective_access_policies
    assert not (await manager.registry.execute("web_fetch", {"url": "https://public.test"})).success
    manager.bind_runtime(project_root=tmp_path)
    manager.registry.register(ShellTool())
    manager.registry.add_auto_approve_policy("shell")
    result = await manager.registry.execute("shell", {"command": "echo forbidden", "background": False})
    assert not result.success and "unsupported" in result.content


@pytest.mark.parametrize("hosts", [[], ["public.test"]])
async def test_host_only_policy_denies_mcp_before_client_creation(tmp_path, hosts):
    from unittest.mock import Mock

    from henchman.config.schema import McpServerConfig
    from henchman.mcp.manager import McpManager

    settings = Settings(tools={"network_allowed_hosts": hosts}, mcp_servers={
        "server": McpServerConfig(command="never-launch"),
    })
    manager = McpManager.create_from_settings(settings, project_root=tmp_path)
    assert manager is not None
    manager._client_factory = Mock(side_effect=AssertionError("unmediated client created"))
    with pytest.raises(ToolAccessError, match="unsupported"):
        await manager.connect_server("server")
    manager._client_factory.assert_not_called()


def test_network_checks_keep_unrestricted_context_and_do_not_recurse():
    from henchman.tools.access_policy import check_network_access, use_network_authorization

    checks = []
    with (use_network_authorization(lambda: checks.append("first")),
          use_network_authorization(lambda: checks.append("second"))):
        check_network_access("public.test")
    assert checks == ["first", "second"]
    check_network_access("public.test")
    with use_access_policies((ToolAccessPolicy(),)):
        check_network_access("public.test")


def fetch_registry(root, hosts):
    parent = ToolRegistry(retry_config=RetryConfig(max_retries=0))
    parent.set_access_policy(policy(root, network_allowed_hosts=hosts))
    parent.register(WebFetchTool())
    parent.add_auto_approve_policy("web_fetch")
    return parent, ScopedToolRegistry(parent, None, inherit_auto_approve=True)


@socket_guard
@pytest.mark.parametrize("host", ["public.test", "PUBLIC.test.", "faß.test"])
async def test_exact_qualified_fetch_works_without_filesystem_primitives(tmp_path, monkeypatch, host):
    from henchman.tools import access_policy

    _parent, registry = fetch_registry(tmp_path, [host])
    route_dns_to(monkeypatch, ["8.8.8.8"])
    # A trailing dot is a real DNS name too; use the canonical wire spelling.
    wire_host = Settings(tools={"network_allowed_hosts": [host]}).tools.network_allowed_hosts[0]
    route_public_connections_locally(monkeypatch)
    admit_local_fixture_peer(monkeypatch)
    monkeypatch.setattr(access_policy, "_SAFE_DIRECTORY_OPS", False)
    async with local_server() as (port, received):
        result = await registry.execute("web_fetch", {"url": f"http://{wire_host}:{port}/page"})
    assert result.success, result.content
    assert len(received) == 1 and f"Host: {wire_host}:{port}".encode() in received[0]


async def test_restricted_fetch_without_socket_hook_denies_before_dns(tmp_path, monkeypatch):
    from henchman.tools import http_security

    _parent, registry = fetch_registry(tmp_path, ["public.test"])
    monkeypatch.setattr(http_security, "supports_network_socket_guard", lambda: False, raising=False)
    dns = route_dns_to(monkeypatch, ["8.8.8.8"])
    result = await registry.execute("web_fetch", {"url": "https://public.test/page"})
    assert not result.success and "socket_factory" in result.content
    assert dns == []


@socket_guard
async def test_allowed_redirect_cannot_escape_host_set(tmp_path, monkeypatch):
    _parent, registry = fetch_registry(tmp_path, ["first.test"])
    dns = route_dns_to(monkeypatch, ["8.8.8.8"])
    connects = route_public_connections_locally(monkeypatch)
    admit_local_fixture_peer(monkeypatch)
    async with local_server(lambda _: b"HTTP/1.1 302 Found\r\nLocation: https://other.test/no\r\nContent-Length: 0\r\n\r\n") as (port, received):
        result = await registry.execute("web_fetch", {"url": f"http://first.test:{port}/start"})
    assert not result.success
    assert dns == ["first.test"] and len(connects) == 1 and len(received) == 1


@socket_guard
async def test_allowlisted_host_still_rejects_mixed_private_dns(tmp_path, monkeypatch):
    _parent, registry = fetch_registry(tmp_path, ["public.test"])
    dns = route_dns_to(monkeypatch, ["8.8.8.8", "127.0.0.1"])
    connects = route_public_connections_locally(monkeypatch)
    result = await registry.execute("web_fetch", {"url": "http://public.test/no"})
    assert not result.success and dns == ["public.test"] and connects == []


@socket_guard
@pytest.mark.parametrize("initial_hosts", [None, ["public.test"]])
@pytest.mark.parametrize("boundary", ["dns", "second_connect", "headers", "redirect"])
async def test_current_registry_revocation_at_actual_transport_boundaries(tmp_path, monkeypatch, initial_hosts, boundary):
    parent, registry = fetch_registry(tmp_path, initial_hosts)
    addresses = ["8.8.8.8", "8.8.4.4"] if boundary == "second_connect" else ["8.8.8.8"]
    dns = route_dns_to(monkeypatch, addresses)
    loop = asyncio.get_running_loop()
    resolve = loop.getaddrinfo
    connect = loop.sock_connect
    connects = []

    def revoke():
        parent.set_access_policy(policy(tmp_path, network_access="disabled"))

    async def controlled_resolve(*args, **kwargs):
        answers = await resolve(*args, **kwargs)
        if boundary == "dns":
            revoke()
        return answers

    async def controlled_connect(sock, address):
        connects.append(address)
        if boundary == "second_connect":
            await asyncio.sleep(0)
            revoke()
            raise ConnectionRefusedError("fixture first candidate failed")
        await connect(sock, ("127.0.0.1", address[1]))
        if boundary == "headers":
            revoke()

    def response(_request):
        revoke()
        return b"HTTP/1.1 302 Found\r\nLocation: /next\r\nContent-Length: 0\r\n\r\n"

    monkeypatch.setattr(loop, "getaddrinfo", controlled_resolve)
    monkeypatch.setattr(loop, "sock_connect", controlled_connect)
    admit_local_fixture_peer(monkeypatch)
    async with local_server(response) as (port, received):
        result = await registry.execute("web_fetch", {"url": f"http://public.test:{port}/start"})
    assert not result.success
    assert dns == ["public.test"]
    assert len(connects) == (0 if boundary == "dns" else 1)
    assert len([data for data in received if data]) == (1 if boundary == "redirect" else 0)


@socket_guard
async def test_paused_writer_cannot_defer_restricted_header_dispatch(tmp_path, monkeypatch):
    from henchman.tools.http_security import PeerCheckedRequest

    _parent, registry = fetch_registry(tmp_path, ["public.test"])
    route_dns_to(monkeypatch, ["8.8.8.8"])
    route_public_connections_locally(monkeypatch)
    admit_local_fixture_peer(monkeypatch)
    original = PeerCheckedRequest.send
    visited = []

    async def paused_send(self, conn):
        visited.append(True)
        conn.protocol.pause_writing()
        return await original(self, conn)

    monkeypatch.setattr(PeerCheckedRequest, "send", paused_send)
    async with local_server() as (port, received):
        result = await registry.execute("web_fetch", {"url": f"http://public.test:{port}/page", "timeout": 1})
    assert visited and not result.success and "deferred" in result.content.lower()
    assert not any(received)


@socket_guard
@pytest.mark.parametrize("allowed", [True, False])
async def test_direct_injected_immutable_policy_checks_its_host(tmp_path, monkeypatch, allowed):
    dns = route_dns_to(monkeypatch, ["8.8.8.8"])
    route_public_connections_locally(monkeypatch)
    admit_local_fixture_peer(monkeypatch)
    async with local_server() as (port, received):
        with use_access_policies((policy(tmp_path, network_allowed_hosts=["public.test" if allowed else "other.test"]),)):
            result = await WebFetchTool().execute(url=f"http://public.test:{port}/page")
    assert result.success is allowed
    assert bool(dns) is allowed and bool(received) is allowed


@socket_guard
@pytest.mark.parametrize("hostname,success", [("public.test", True), ("wrong.test", False)])
async def test_restricted_real_tls_preserves_hostname_verification(tmp_path, monkeypatch, hostname, success):
    from henchman.tools.builtins import web_fetch

    _parent, registry = fetch_registry(tmp_path, [hostname])
    route_dns_to(monkeypatch, ["8.8.8.8"])
    route_public_connections_locally(monkeypatch)
    admit_local_fixture_peer(monkeypatch)
    server_context, client_context = tls_contexts(tmp_path)
    sni = []
    server_context.set_servername_callback(lambda _socket, name, _context: sni.append(name))
    original = web_fetch.public_http_session
    monkeypatch.setattr(web_fetch, "public_http_session", lambda **kwargs: original(ssl_context=client_context, **kwargs))
    async with local_server(ssl=server_context) as (port, received):
        result = await registry.execute("web_fetch", {"url": f"https://{hostname}:{port}/page"})
    assert result.success is success, result.content
    assert sni == [hostname]
    assert bool(any(received)) is success


@socket_guard
async def test_qualified_fetch_does_not_inherit_trust_by_name_or_subclass(tmp_path, monkeypatch):
    from unittest.mock import AsyncMock

    class CustomFetch(WebFetchTool):
        pass

    for candidate in (CustomFetch(), WebFetchTool()):
        parent, registry = fetch_registry(tmp_path, ["public.test"])
        parent.unregister("web_fetch")
        if type(candidate) is WebFetchTool:
            replacement = AsyncMock(return_value=ToolResult(content="unmediated"))
            monkeypatch.setattr(candidate, "execute", replacement)
        parent.register(candidate)
        result = await registry.execute("web_fetch", {"url": "https://public.test/page"})
        assert not result.success and "unsupported" in result.content


@socket_guard
@pytest.mark.parametrize("url", ["https://sub.public.test/page", "https://8.8.8.8/page"])
async def test_requested_authority_cannot_substitute_subdomain_or_resolved_ip(tmp_path, monkeypatch, url):
    _parent, registry = fetch_registry(tmp_path, ["public.test"])
    dns = route_dns_to(monkeypatch, ["8.8.8.8"])
    connects = route_public_connections_locally(monkeypatch)
    result = await registry.execute("web_fetch", {"url": url})
    assert not result.success and dns == [] and connects == []


@socket_guard
async def test_allowlisted_ip_literal_uses_guard_without_dns(tmp_path, monkeypatch):
    _parent, registry = fetch_registry(tmp_path, ["8.8.8.8"])
    dns = route_dns_to(monkeypatch, ["8.8.8.8"])
    connects = route_public_connections_locally(monkeypatch)
    admit_local_fixture_peer(monkeypatch)
    async with local_server() as (port, received):
        result = await registry.execute("web_fetch", {"url": f"http://8.8.8.8:{port}/page"})
    assert result.success, result.content
    assert dns == [] and len(connects) == 1 and len(received) == 1


@socket_guard
async def test_allowed_cross_origin_redirects_never_restore_initial_credentials(tmp_path, monkeypatch):
    _parent, registry = fetch_registry(tmp_path, ["first.test", "other.test"])
    route_dns_to(monkeypatch, ["8.8.8.8"])
    route_public_connections_locally(monkeypatch)
    admit_local_fixture_peer(monkeypatch)
    ports = {}

    def response(request):
        if request.startswith(b"GET /return "):
            return b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok"
        host, path = ("other.test", "next") if request.startswith(b"GET /start ") else ("first.test", "return")
        return (f"HTTP/1.1 302 Found\r\nLocation: http://{host}:{ports['port']}/{path}\r\n"
                "Set-Cookie: canary=forbidden\r\nContent-Length: 0\r\n\r\n").encode()

    async with local_server(response) as (port, received):
        ports["port"] = port
        result = await registry.execute("web_fetch", {"url": f"http://user:canary@first.test:{port}/start"})
    assert result.success, result.content
    assert len(received) == 3 and b"Authorization:" in received[0]
    assert all(b"Authorization:" not in request and b"Cookie:" not in request for request in received[1:])


async def test_legacy_unrestricted_transport_rechecks_revocation_before_headers(tmp_path, monkeypatch):
    from henchman.tools import http_security

    parent, registry = fetch_registry(tmp_path, None)
    monkeypatch.setattr(http_security, "supports_network_socket_guard", lambda: False)
    route_dns_to(monkeypatch, ["8.8.8.8"])
    connects = route_public_connections_locally(monkeypatch)
    loop = asyncio.get_running_loop()
    create = loop.create_connection

    async def revoke_after_connect(*args, **kwargs):
        transport = await create(*args, **kwargs)
        parent.set_access_policy(policy(tmp_path, network_access="disabled"))
        return transport

    monkeypatch.setattr(loop, "create_connection", revoke_after_connect)
    admit_local_fixture_peer(monkeypatch)
    async with local_server() as (port, received):
        result = await registry.execute("web_fetch", {"url": f"http://public.test:{port}/page"})
    assert not result.success and len(connects) == 1 and not any(received)
