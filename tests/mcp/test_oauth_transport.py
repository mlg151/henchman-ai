"""OAuth HTTP permits authorize each owned request without replay or fallback."""

# ruff: noqa: F811 -- imported fixtures are resolved by pytest parameter name.

import asyncio
import hashlib
import logging
import traceback
from contextlib import suppress

import pytest

from henchman.mcp.oauth import OAuthError
from henchman.mcp.oauth_store import OAuthCredentials
from tests.mcp.http_fixture import HttpPeer
from tests.mcp.test_oauth_discovery import tls_contexts, trusted_tls  # noqa: F401
from tests.mcp.test_oauth_manager import allowed, runtime
from tests.mcp.test_oauth_store import binding, credentials, ready, store


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def test_rejected_access_is_unavailable_but_preserves_one_explicit_refresh_claim(tmp_path):
    service = store(tmp_path, clock=lambda: 100)
    authority = ready(service)
    assert service.reject_access(authority, digest("access-private-canary"))
    status, rejected = service.bound_status(binding())
    assert status.state == "access_rejected" and status.refresh_available
    assert rejected.generation > authority.generation
    assert service.credentials(rejected) is None
    claim = service.begin_refresh(rejected)
    assert claim.refresh_token == "refresh-private-canary"
    assert claim.previous_scopes == ("read",)
    assert claim.token_endpoint == "https://issuer.example/token"
    with pytest.raises(OAuthError):
        service.begin_refresh(rejected)


@pytest.mark.parametrize("supersede", ["rotation", "logout", "config", "wrong_token"])
def test_late_rejection_never_invalidates_superseding_authority(tmp_path, supersede):
    service = store(tmp_path, clock=lambda: 100)
    old = ready(service)
    if supersede == "rotation":
        current = service.complete(service.begin_refresh(old), credentials("new-access", "new-refresh"))
    elif supersede == "logout":
        service.logout("fixture")
    elif supersede == "config":
        service.bind(binding("different-client"))
    path = tmp_path / ".henchman/mcp/oauth.json"
    before = path.read_bytes()
    assert not service.reject_access(old, digest("wrong-token" if supersede == "wrong_token" else "access-private-canary"))
    assert path.read_bytes() == before
    if supersede == "rotation":
        assert service.credentials(current).access_token == "new-access"


def test_explicit_capture_releases_no_token_until_a_current_request_is_checked(tmp_path):
    service = store(tmp_path, clock=lambda: 100)
    ready(service)
    manager, settings = runtime(tmp_path)
    manager._oauth_runtime._store._clock = lambda: 100
    permit = manager.capture_oauth_http("fixture", authorize=allowed)
    assert "canary" not in repr(permit)
    request = permit.for_client(object()).request("POST", settings.mcp_servers["fixture"].url)
    assert request.authorization == "Bearer access-private-canary"
    assert "canary" not in repr(request)
    manager.oauth_logout("fixture", authorize=allowed)
    with pytest.raises(OAuthError):
        permit.for_client(object()).request("POST", settings.mcp_servers["fixture"].url)


def test_closing_permit_is_exact_session_endpoint_and_preserves_common_guards(tmp_path):
    service = store(tmp_path, clock=lambda: 100)
    ready(service)
    manager, settings = runtime(tmp_path)
    manager._oauth_runtime._store._clock = lambda: 100
    owner = object()
    permit = manager.capture_oauth_http("fixture", authorize=allowed).for_client(owner)
    closing = permit.closing(owner, "owned-session")
    manager._invalidate("fixture")
    with pytest.raises(OAuthError):
        permit.request("POST", settings.mcp_servers["fixture"].url)
    assert closing.request("DELETE", settings.mcp_servers["fixture"].url, "owned-session").authorization.startswith("Bearer ")
    for method, url, session in (("POST", settings.mcp_servers["fixture"].url, "owned-session"),
                                ("DELETE", "https://outside.example", "owned-session"),
                                ("DELETE", settings.mcp_servers["fixture"].url, "other-session")):
        with pytest.raises(OAuthError):
            closing.request(method, url, session)
    settings.tools.network_access = "disabled"
    with pytest.raises(OAuthError):
        closing.request("DELETE", settings.mcp_servers["fixture"].url, "owned-session")


def native_authority(peer, tmp_path):
    from henchman.config.schema import McpServerConfig
    from henchman.mcp.oauth import OAuthBinding

    origin = peer.url.removesuffix("/mcp")
    config = McpServerConfig(transport="streamable_http", url=peer.url,
                            oauth={"issuer": origin + "/issuer", "client_id": "public-client"})
    service = store(tmp_path, clock=lambda: 100)
    authority = service.bind(OAuthBinding.from_config("fixture", config))
    service.complete(service.begin_login(authority), OAuthCredentials(access_token="http-access-private-canary",
        refresh_token="http-refresh-private-canary", token_endpoint=origin + "/token", scopes=("read",), issued_at=100, expires_at=200))
    manager, settings = runtime(tmp_path, config)
    manager._oauth_runtime._store._clock = lambda: 100
    return manager, settings, config


def native_client(manager, config):
    from henchman.mcp.client import McpClient

    return McpClient("fixture", config, oauth_authority=manager.capture_oauth_http("fixture", authorize=allowed))


@pytest.mark.parametrize("version", ["2025-03-26", "2025-06-18", "2025-11-25", "2026-07-28"])
@pytest.mark.parametrize("mode", ["json", "sse"])
async def test_explicit_native_client_authenticates_every_request_and_only_exact_resource(tmp_path, trusted_tls, version, mode, caplog):
    caplog.set_level(logging.DEBUG)
    async with HttpPeer(version=version, mode=mode, ssl_context=trusted_tls) as peer:
        manager, _settings, config = native_authority(peer, tmp_path)
        client = native_client(manager, config)
        try:
            await client.connect()
            result = await client.call_tool("effect", {"region": "north"})
            assert not result.is_error and result.content == "http executed"
        finally:
            await client.disconnect()
        assert peer.effects == 1
        assert all(item["headers"].get("authorization") == "Bearer http-access-private-canary" for item in peer.requests)
        assert all(item["target"] == "/mcp" for item in peer.requests)
        assert all("cookie" not in item["headers"] for item in peer.requests)
        assert sum(item["verb"] == "DELETE" for item in peer.requests) == (0 if version == "2026-07-28" else 1)
        assert "canary" not in caplog.text
        assert all(record.exc_info is None for record in caplog.records)
        before = len(peer.requests)
        with pytest.raises(RuntimeError, match="not yet supported"):
            await manager.connect_server("fixture")
        assert len(peer.requests) == before


@pytest.mark.parametrize("change", ["logout", "config", "policy", "expiry"])
async def test_waiting_capacity_rechecks_authority_before_any_second_post(tmp_path, trusted_tls, monkeypatch, change):
    from henchman.mcp import http_transport

    monkeypatch.setattr(http_transport, "HTTP_CONCURRENCY", 1)
    async with HttpPeer(ssl_context=trusted_tls) as peer:
        manager, settings, config = native_authority(peer, tmp_path)
        client = native_client(manager, config)
        first = second = None
        try:
            await client.connect()
            peer.delays["tools/call"] = .15
            first = asyncio.create_task(client.call_tool("effect", {}))
            async with asyncio.timeout(2):
                while not any(item["body"].get("method") == "tools/call" for item in peer.requests):
                    await asyncio.sleep(.001)
            second = asyncio.create_task(client.call_tool("effect", {}))
            await asyncio.sleep(.02)
            if change == "logout":
                manager.oauth_logout("fixture", authorize=allowed)
            elif change == "config":
                settings.mcp_servers["fixture"].oauth.client_id = "changed"
            elif change == "policy":
                settings.tools.network_access = "disabled"
            else:
                manager._oauth_runtime._store._clock = lambda: 200
            results = await asyncio.wait_for(asyncio.gather(first, second, return_exceptions=True), 3)
            assert isinstance(results[1], Exception)
            assert sum(item["body"].get("method") == "tools/call" for item in peer.requests) == 1
        finally:
            for task in (first, second):
                if task is not None:
                    task.cancel()
            await asyncio.gather(*(task for task in (first, second) if task is not None), return_exceptions=True)
            with suppress(Exception):
                await client.disconnect()


async def test_revocation_during_tls_connection_wait_sends_no_application_http(tmp_path, trusted_tls, monkeypatch):
    from httpcore2._async.connection import AsyncHTTPConnection

    entered, release = asyncio.Event(), asyncio.Event()
    original = AsyncHTTPConnection._connect

    async def connected_then_paused(self, request):
        stream = await original(self, request)
        entered.set()
        await release.wait()
        return stream

    monkeypatch.setattr(AsyncHTTPConnection, "_connect", connected_then_paused)
    async with HttpPeer(ssl_context=trusted_tls) as peer:
        manager, _settings, config = native_authority(peer, tmp_path)
        client = native_client(manager, config)
        task = asyncio.create_task(client.connect())
        try:
            await asyncio.wait_for(entered.wait(), 2)
            manager.oauth_logout("fixture", authorize=allowed)
            release.set()
            with pytest.raises(Exception) as caught:
                await asyncio.wait_for(task, 3)
            assert "canary" not in "".join(traceback.format_exception(caught.value))
            assert peer.requests == []
        finally:
            release.set()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            with suppress(Exception):
                await client.disconnect()


@pytest.mark.parametrize("status", [401, 403])
async def test_auth_failure_never_refreshes_or_replays_and_keeps_refresh_material(tmp_path, trusted_tls, status):
    async with HttpPeer(ssl_context=trusted_tls) as peer:
        manager, _settings, config = native_authority(peer, tmp_path)
        client = native_client(manager, config)
        try:
            await client.connect()
            before = len(peer.requests)
            peer.required_bearer, peer.auth_status = "Bearer another-credential", status
            with pytest.raises(Exception) as caught:
                await client.call_tool("effect", {})
            assert "canary" not in "".join(traceback.format_exception(caught.value))
            assert len(peer.requests) == before + 1 and peer.effects == 0
            result = manager.oauth_status("fixture", authorize=allowed)
            assert result.state == ("access_rejected" if status == 401 else "ready")
            assert result.refresh_available
            if status == 401:
                with pytest.raises(OAuthError):
                    manager.capture_oauth_http("fixture", authorize=allowed)
        finally:
            with suppress(Exception):
                await client.disconnect()


async def test_late_401_does_not_reject_rotated_tokens_or_replacement_client(tmp_path, trusted_tls):
    from henchman.mcp.oauth import OAuthBinding

    async with HttpPeer(ssl_context=trusted_tls) as peer:
        manager, _settings, config = native_authority(peer, tmp_path)
        old, fresh, operation = native_client(manager, config), None, None
        try:
            await old.connect()
            peer.required_bearer = "Bearer replacement-access-canary"
            peer.delays["tools/call"] = .2
            operation = asyncio.create_task(old.call_tool("effect", {}))
            async with asyncio.timeout(2):
                while not any(item["body"].get("method") == "tools/call" for item in peer.requests):
                    await asyncio.sleep(.001)
            service = store(tmp_path, clock=lambda: 100)
            _status, authority = service.bound_status(OAuthBinding.from_config("fixture", config))
            previous = service.credentials(authority)
            service.complete(service.begin_refresh(authority), previous.model_copy(update={
                "access_token": "replacement-access-canary", "refresh_token": "replacement-refresh-canary"}))
            fresh = native_client(manager, config)
            await fresh.connect()
            with pytest.raises(RuntimeError, match="token rejected"):
                await operation
            assert manager.oauth_status("fixture", authorize=allowed).state == "ready"
            peer.delays.clear()
            assert (await fresh.call_tool("effect", {})).content == "http executed"
            assert fresh.is_connected and peer.effects == 1
        finally:
            if operation is not None:
                operation.cancel()
                await asyncio.gather(operation, return_exceptions=True)
            for client in (old, fresh):
                if client is not None:
                    with suppress(Exception):
                        await client.disconnect()


@pytest.mark.parametrize("change", ["normal", "logout", "config", "policy", "expiry", "rotation"])
async def test_legacy_delete_uses_only_exact_policy_valid_closing_authority(tmp_path, trusted_tls, change):
    from henchman.mcp.oauth import OAuthBinding

    async with HttpPeer(version="2025-11-25", ssl_context=trusted_tls) as peer:
        manager, settings, config = native_authority(peer, tmp_path)
        client = native_client(manager, config)
        await client.connect()
        manager._invalidate("fixture")
        if change == "logout":
            manager.oauth_logout("fixture", authorize=allowed)
        elif change == "config":
            settings.mcp_servers["fixture"].oauth.client_id = "changed"
        elif change == "policy":
            settings.tools.network_access = "disabled"
        elif change == "expiry":
            manager._oauth_runtime._store._clock = lambda: 200
        elif change == "rotation":
            service = store(tmp_path, clock=lambda: 100)
            _status, authority = service.bound_status(OAuthBinding.from_config("fixture", config))
            previous = service.credentials(authority)
            service.complete(service.begin_refresh(authority), previous.model_copy(update={"access_token": "changed-access-canary"}))
        if change == "normal":
            await client.disconnect()
        else:
            with pytest.raises(Exception) as caught:
                await client.disconnect()
            evidence = "".join(traceback.format_exception(caught.value))
            assert "cleanup" in evidence.lower() and "canary" not in evidence
        assert sum(item["verb"] == "DELETE" for item in peer.requests) == (1 if change == "normal" else 0)
        assert client._owner_task is None


def test_sdk_diagnostics_retains_rotated_oauth_credentials_before_formatting(tmp_path, caplog):
    from henchman.mcp.diagnostics import sdk_diagnostics
    from henchman.utils.evidence_redaction import EvidenceRedactor

    caplog.set_level(logging.ERROR)
    service = store(tmp_path, clock=lambda: 100)
    authority = ready(service)
    evidence = EvidenceRedactor()
    service.register_evidence(evidence)
    with sdk_diagnostics({}, policy=evidence):
        service.complete(service.begin_refresh(authority), credentials("new-access-canary", "new-refresh-canary"))
        service.logout("fixture")
        try:
            raise RuntimeError("access-private-canary new-access-canary refresh-private-canary new-refresh-canary")
        except RuntimeError:
            logging.getLogger("mcp.client.client").exception("old=%s new=%s", "access-private-canary", "new-access-canary")
    assert "canary" not in caplog.text
    assert all(record.exc_info is None and "canary" not in logging.Formatter().format(record) for record in caplog.records)


@pytest.mark.parametrize("package", ["httpx2", "httpcore2"])
async def test_unqualified_http_stack_refuses_authenticated_client_before_network(tmp_path, trusted_tls, monkeypatch, package):
    from henchman.mcp import http_guard

    original = http_guard.version
    monkeypatch.setattr(http_guard, "version", lambda name: "0.0.0" if name == package else original(name))
    async with HttpPeer(ssl_context=trusted_tls) as peer:
        manager, _settings, config = native_authority(peer, tmp_path)
        with pytest.raises(OAuthError, match="runtime profile"):
            native_client(manager, config)
        assert peer.requests == []


async def test_manager_teardown_revokes_captured_http_permits_without_registered_clients(tmp_path):
    service = store(tmp_path, clock=lambda: 100)
    ready(service)
    manager, settings = runtime(tmp_path)
    manager._oauth_runtime._store._clock = lambda: 100
    captured = manager.capture_oauth_http("fixture", authorize=allowed).for_client(object())
    assert manager.clients == {}
    await manager.disconnect_all()
    with pytest.raises(OAuthError):
        captured.request("POST", settings.mcp_servers["fixture"].url)
    fresh = manager.capture_oauth_http("fixture", authorize=allowed).for_client(object())
    assert fresh.request("POST", settings.mcp_servers["fixture"].url).authorization.startswith("Bearer ")


async def test_removing_client_oauth_config_cannot_bypass_captured_configuration_guard(tmp_path, trusted_tls):
    async with HttpPeer(ssl_context=trusted_tls) as peer:
        manager, _settings, config = native_authority(peer, tmp_path)
        client = native_client(manager, config.model_copy(deep=True))
        try:
            await client.connect()
            before = len(peer.requests)
            client.config.oauth = None
            with pytest.raises(RuntimeError, match="configuration"):
                await client.call_tool("effect", {})
            assert len(peer.requests) == before
        finally:
            with suppress(Exception):
                await client.disconnect()


@pytest.mark.parametrize("header", ["Authorization", "Host", "Mcp-Session-Id"])
async def test_rpc_metadata_cannot_override_authentication_or_owned_routing_headers(tmp_path, trusted_tls, header):
    import anyio
    from mcp.shared.message import ClientMessageMetadata, SessionMessage

    from henchman.mcp.http_transport import HttpState, bounded_http_client
    from mcp import types

    async with HttpPeer(ssl_context=trusted_tls) as peer:
        manager, _settings, _config = native_authority(peer, tmp_path)
        owner = object()
        permit = manager.capture_oauth_http("fixture", authorize=allowed).for_client(owner)
        state = HttpState()
        async with bounded_http_client(peer.url, state=state, authorize=allowed, authorize_cleanup=allowed,
                                       request_timeout=1, oauth_permit=permit, oauth_owner=owner) as (read, write):
            await write.send(SessionMessage(types.JSONRPCNotification(jsonrpc="2.0", method="notifications/initialized"),
                metadata=ClientMessageMetadata(headers={header: "forged-private-canary"})))
            with pytest.raises(anyio.EndOfStream):
                await asyncio.wait_for(read.receive(), 2)
            assert state.failure is not None and "unsupported header" in str(state.failure)
        assert peer.requests == []


@pytest.mark.parametrize("phase", ["waiting_capacity", "after_dispatch"])
async def test_cancellation_settles_capacity_without_replaying_mutating_request(tmp_path, trusted_tls, monkeypatch, phase):
    from henchman.mcp import http_transport

    monkeypatch.setattr(http_transport, "HTTP_CONCURRENCY", 1)
    async with HttpPeer(ssl_context=trusted_tls) as peer:
        manager, _settings, config = native_authority(peer, tmp_path)
        client = native_client(manager, config)
        first = cancelled = None
        try:
            await client.connect()
            peer.delays["tools/call"] = .15
            first = asyncio.create_task(client.call_tool("effect", {}))
            async with asyncio.timeout(2):
                while not any(item["body"].get("method") == "tools/call" for item in peer.requests):
                    await asyncio.sleep(.001)
            cancelled = asyncio.create_task(client.call_tool("effect", {})) if phase == "waiting_capacity" else first
            await asyncio.sleep(.01)
            cancelled.cancel()
            with pytest.raises(asyncio.CancelledError):
                await cancelled
            if first is not cancelled:
                await first
            # A new explicit call proves the released permit remains usable.
            assert (await client.call_tool("effect", {})).content == "http executed"
            assert sum(item["body"].get("method") == "tools/call" for item in peer.requests) == 2
        finally:
            tasks = {task for task in (first, cancelled) if task is not None}
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            with suppress(Exception):
                await client.disconnect()


@pytest.mark.parametrize("cleanup", ["normal", "failure_after_close", "hang_after_close", "failure_before_close", "hang_before_close"])
@pytest.mark.parametrize("version", ["2025-11-25", "2026-07-28"])
async def test_native_sse_cancellation_preserves_primary_and_fences_uncertain_cleanup(tmp_path, trusted_tls, monkeypatch, cleanup, version):
    import json

    import httpx2

    from henchman.mcp import http_transport

    monkeypatch.setattr(http_transport, "HTTP_CONCURRENCY", 1)
    monkeypatch.setattr(http_transport, "HTTP_SHUTDOWN_TIMEOUT_SECONDS", .05)
    original_close = httpx2.Response.aclose
    original_iter = httpx2.Response.aiter_raw
    body_started = asyncio.Event()
    close_started = asyncio.Event()
    close_finished = asyncio.Event()

    async def observed_body(response, *args, **kwargs):
        if response.request.method == "POST" and json.loads(response.request.content).get("method") == "tools/call":
            body_started.set()
        async for chunk in original_iter(response, *args, **kwargs):
            yield chunk

    async def faulty_close(response):
        request = response.request
        if (request.method == "POST" and json.loads(request.content).get("method") == "tools/call"
                and not close_started.is_set()):
            close_started.set()
            try:
                if cleanup == "normal" or cleanup.endswith("after_close"):
                    await original_close(response)
                if cleanup.startswith("hang"):
                    await asyncio.Event().wait()
                if cleanup.startswith("failure"):
                    raise RuntimeError("private-response-close-canary")
            finally:
                close_finished.set()
        else:
            await original_close(response)

    monkeypatch.setattr(httpx2.Response, "aclose", faulty_close)
    monkeypatch.setattr(httpx2.Response, "aiter_raw", observed_body)
    async with HttpPeer(version=version, ssl_context=trusted_tls) as peer:
        manager, _settings, config = native_authority(peer, tmp_path)
        client = native_client(manager, config)
        operation = None
        try:
            await client.connect()
            peer.behavior = "sse_wait"
            operation = asyncio.create_task(client.call_tool("effect", {}))
            await asyncio.wait_for(peer.sse_started.wait(), 2)
            await asyncio.wait_for(body_started.wait(), 2)
            operation.cancel("owned-sse-cancellation")
            with pytest.raises(asyncio.CancelledError, match="owned-sse-cancellation"):
                await asyncio.wait_for(operation, 2)
            await asyncio.wait_for(close_finished.wait(), 2)
            peer.behavior = "complete"
            if cleanup != "normal":
                with pytest.raises(RuntimeError, match="cleanup") as caught:
                    await asyncio.wait_for(client.call_tool("effect", {}), 2)
                assert "canary" not in "".join(traceback.format_exception(caught.value))
                assert not client.is_connected and peer.effects == 1
                with pytest.raises((RuntimeError, ExceptionGroup)) as closed:
                    await asyncio.wait_for(client.disconnect(), 2)
                cleanup_detail = "".join(traceback.format_exception(closed.value))
                assert "cleanup" in cleanup_detail and "canary" not in cleanup_detail
                assert client._owner_task is None
                assert not any(item["verb"] == "DELETE" for item in peer.requests)
                # Recovery creates an explicit new owner; no hidden retry occurs.
                client = native_client(manager, config)
                await client.connect()
            await asyncio.wait_for(peer.sse_closed.wait(), 2)
            result = await asyncio.wait_for(client.call_tool("effect", {}), 2)
            assert result.content == "http executed"
            assert peer.effects == 2
        finally:
            if operation is not None:
                operation.cancel()
                await asyncio.gather(operation, return_exceptions=True)
            with suppress(Exception):
                await client.disconnect()


@pytest.mark.parametrize("cleanup", ["failure_after_close", "failure_before_close", "hang_before_close"])
async def test_http_primary_rejection_survives_response_close_failure(tmp_path, trusted_tls, monkeypatch, cleanup):
    import httpx2

    from henchman.mcp import http_transport

    monkeypatch.setattr(http_transport, "HTTP_SHUTDOWN_TIMEOUT_SECONDS", .05)
    original_close = httpx2.Response.aclose

    async def faulty_close(response):
        if response.status_code == 401:
            if cleanup == "failure_after_close":
                await original_close(response)
            if cleanup == "hang_before_close":
                await asyncio.Event().wait()
            raise RuntimeError("private-response-close-canary")
        await original_close(response)

    monkeypatch.setattr(httpx2.Response, "aclose", faulty_close)
    async with HttpPeer(ssl_context=trusted_tls) as peer:
        manager, _settings, config = native_authority(peer, tmp_path)
        client = native_client(manager, config)
        try:
            await client.connect()
            peer.required_bearer = "different-access"
            with pytest.raises(RuntimeError, match="access token rejected") as caught:
                await client.call_tool("effect", {})
            details = "".join(traceback.format_exception(caught.value))
            assert "canary" not in details and "cleanup" in details
            assert manager.oauth_status("fixture", authorize=allowed).state == "access_rejected"
            assert not client.is_connected
        finally:
            with suppress(Exception):
                await asyncio.wait_for(client.disconnect(), 2)
            assert client._owner_task is None
