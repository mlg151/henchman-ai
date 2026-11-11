"""Explicit native manager connection never authorizes startup or tool replay."""

# ruff: noqa: F811 -- imported fixtures are resolved by pytest.

import asyncio

import pytest

from henchman.config.schema import McpOAuthConfig, McpServerConfig
from henchman.mcp.oauth import OAuthError
from henchman.tools.registry import ToolRegistry
from tests.cli.test_oauth_browser import wait_until
from tests.mcp.http_fixture import HttpPeer
from tests.mcp.test_oauth_discovery import tls_contexts, trusted_tls  # noqa: F401
from tests.mcp.test_oauth_manager import allowed, runtime
from tests.mcp.test_oauth_transport import native_authority


async def test_explicit_connect_publishes_native_catalog_but_default_connect_stays_closed(tmp_path, trusted_tls):
    async with HttpPeer(ssl_context=trusted_tls) as peer:
        manager, _settings, _config = native_authority(peer, tmp_path)
        registry = ToolRegistry()
        manager.bind_registry(registry)
        try:
            await manager.connect_oauth_server("fixture", authorize=allowed)
            tool = registry.get("mcp_fixture_effect")
            assert tool is not None
            result = await tool.execute(region="north")
            assert result.success and peer.effects == 1
            with pytest.raises(RuntimeError):
                await manager.connect_server("fixture")
            assert manager.clients["fixture"].is_connected
        finally:
            await manager.disconnect_all()


async def test_waiting_connect_lock_rechecks_caller_before_any_http(tmp_path, trusted_tls):
    async with HttpPeer(ssl_context=trusted_tls) as peer:
        manager, _settings, _config = native_authority(peer, tmp_path)
        lock = manager._connection_locks.setdefault("fixture", asyncio.Lock())
        await lock.acquire()
        active = [True]

        def authorize():
            if not active[0]:
                raise RuntimeError("private-authority-canary")

        operation = asyncio.create_task(manager.connect_oauth_server("fixture", authorize=authorize))
        await asyncio.sleep(0)
        active[0] = False
        lock.release()
        with pytest.raises(OAuthError) as caught:
            await operation
        assert "canary" not in str(caught.value) and peer.requests == []
        assert not manager.clients and not manager._connecting


async def test_cancellation_in_final_publication_does_not_leave_a_live_connection(tmp_path, trusted_tls, monkeypatch):
    async with HttpPeer(ssl_context=trusted_tls) as peer:
        manager, _settings, _config = native_authority(peer, tmp_path)
        original = manager._update_bound_server

        def publish(name):
            original(name)
            asyncio.current_task().cancel("cancel OAuth publication")

        monkeypatch.setattr(manager, "_update_bound_server", publish)
        task = asyncio.create_task(manager.connect_oauth_server("fixture", authorize=allowed))
        try:
            with pytest.raises(asyncio.CancelledError, match="cancel OAuth publication"):
                await task
            assert not manager.clients and not manager._connecting
        finally:
            await manager.disconnect_all()


async def test_cancelled_guard_does_not_disconnect_existing_client(tmp_path, trusted_tls):
    async with HttpPeer(ssl_context=trusted_tls) as peer:
        manager, _settings, _config = native_authority(peer, tmp_path)
        await manager.connect_oauth_server("fixture", authorize=allowed)
        client = manager.clients["fixture"]
        calls = 0

        def authorize():
            nonlocal calls
            calls += 1
            if calls == 2:
                asyncio.current_task().cancel("cancel reconnect before effects")

        task = asyncio.create_task(manager.connect_oauth_server("fixture", authorize=authorize))
        try:
            with pytest.raises(asyncio.CancelledError, match="cancel reconnect before effects"):
                await task
            assert manager.clients.get("fixture") is client and client.is_connected
        finally:
            await manager.disconnect_all()


@pytest.mark.parametrize("change", ["caller", "config", "policy", "logout", "disconnect", "cancel"])
async def test_catalog_wait_cannot_publish_after_revocation(tmp_path, trusted_tls, change):
    async with HttpPeer(ssl_context=trusted_tls) as peer:
        manager, settings, _config = native_authority(peer, tmp_path)
        peer.delays["tools/list"] = .2
        registry = ToolRegistry()
        manager.bind_registry(registry)
        active = [True]

        def authorize():
            if not active[0]:
                raise OAuthError("caller changed")

        task = asyncio.create_task(manager.connect_oauth_server("fixture", authorize=authorize))
        try:
            await wait_until(lambda: any(item["body"].get("method") == "tools/list" for item in peer.requests))
            if change == "caller":
                active[0] = False
            elif change == "config":
                settings.mcp_servers["fixture"].oauth.client_id = "changed"
            elif change == "policy":
                settings.tools.network_access = "disabled"
            elif change == "logout":
                manager.oauth_logout("fixture", authorize=allowed)
            elif change == "disconnect":
                await manager.disconnect_all()
            else:
                task.cancel("cancel owned OAuth connect")
            with pytest.raises((OAuthError, asyncio.CancelledError)):
                await task
            assert not manager.clients and not manager._connecting
            assert not registry.get("mcp_fixture_effect")
            assert not [task for task in asyncio.all_tasks() if task.get_name() == "henchman-mcp-session"]
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await manager.disconnect_all()


async def test_reconnect_uses_fresh_permit_and_invalidates_previous_wrapper(tmp_path, trusted_tls):
    async with HttpPeer(version="2025-11-25", ssl_context=trusted_tls) as peer:
        manager, _settings, _config = native_authority(peer, tmp_path)
        registry = ToolRegistry()
        manager.bind_registry(registry)
        try:
            await manager.connect_oauth_server("fixture", authorize=allowed)
            old_client = manager.clients["fixture"]
            old_tool = registry.get("mcp_fixture_effect")
            await manager.connect_oauth_server("fixture", authorize=allowed)
            assert old_client._owner_task is None
            assert registry.get("mcp_fixture_effect") is not old_tool
            with pytest.raises(RuntimeError, match="connection changed"):
                await old_tool.execute(region="north")
            assert (await registry.get("mcp_fixture_effect").execute(region="north")).success
            assert peer.effects == 1
        finally:
            await manager.disconnect_all()
        assert sum(item["verb"] == "DELETE" for item in peer.requests) == 2


async def test_live_oauth_configuration_cannot_fall_back_to_old_unauthenticated_factory(tmp_path, trusted_tls):
    async with HttpPeer(ssl_context=trusted_tls) as peer:
        manager, _settings, config = native_authority(peer, tmp_path)
        manager.configs["fixture"] = config.model_copy(update={"oauth": None})
        try:
            with pytest.raises(RuntimeError):
                await manager.connect_server("fixture")
            assert peer.requests == [] and manager.clients == {}
        finally:
            await manager.disconnect_all()


async def test_teardown_while_connect_waits_cannot_grant_a_new_generation(tmp_path, trusted_tls):
    async with HttpPeer(ssl_context=trusted_tls) as peer:
        manager, _settings, _config = native_authority(peer, tmp_path)
        lock = manager._connection_locks.setdefault("fixture", asyncio.Lock())
        await lock.acquire()
        task = asyncio.create_task(manager.connect_oauth_server("fixture", authorize=allowed))
        await asyncio.sleep(0)
        await manager.disconnect_all()
        lock.release()
        with pytest.raises(OAuthError):
            await task
        assert peer.requests == [] and manager.clients == {}


async def test_explicit_connect_deadline_includes_waiting_for_connection_lock(tmp_path, trusted_tls, monkeypatch):
    from henchman.mcp import manager as manager_module

    async with HttpPeer(ssl_context=trusted_tls) as peer:
        manager, settings, _config = native_authority(peer, tmp_path)
        settings.mcp_servers["fixture"].negotiation_timeout_seconds = .01
        settings.mcp_servers["fixture"].catalog_timeout_seconds = .01
        monkeypatch.setattr(manager_module, "OAUTH_CONNECT_CLEANUP_SECONDS", 0, raising=False)
        lock = manager._connection_locks.setdefault("fixture", asyncio.Lock())
        await lock.acquire()
        try:
            with pytest.raises(OAuthError, match="deadline"):
                await asyncio.wait_for(manager.connect_oauth_server("fixture", authorize=allowed), .5)
            assert peer.requests == [] and not manager.clients
        finally:
            lock.release()


async def test_explicit_connect_401_does_not_refresh_or_retry(tmp_path, trusted_tls):
    async with HttpPeer(ssl_context=trusted_tls) as peer:
        manager, _settings, _config = native_authority(peer, tmp_path)
        peer.behavior = "unauthorized"
        with pytest.raises(OAuthError):
            await manager.connect_oauth_server("fixture", authorize=allowed)
        assert len(peer.requests) == 1 and not manager.clients and not manager._connecting
        status = manager.oauth_status("fixture", authorize=allowed)
        assert status.state == "access_rejected" and status.refresh_available


def _enable_oauth(settings, peer):
    settings.mcp_servers["fixture"].oauth = McpOAuthConfig(
        issuer=peer.url.removesuffix("/mcp") + "/issuer", client_id="explicit-client",
    )


async def test_live_oauth_added_during_automatic_connection_lock_wait_prevents_http(tmp_path, trusted_tls):
    async with HttpPeer(ssl_context=trusted_tls) as peer:
        manager, settings = runtime(tmp_path, McpServerConfig(transport="streamable_http", url=peer.url))
        lock = manager._connection_locks.setdefault("fixture", asyncio.Lock())
        await lock.acquire()
        operation = asyncio.create_task(manager.connect_server("fixture"))
        await asyncio.sleep(0)
        _enable_oauth(settings, peer)
        lock.release()
        try:
            with pytest.raises(RuntimeError):
                await operation
            assert peer.requests == [] and not manager.clients and not manager._connecting
        finally:
            await manager.disconnect_all()


async def test_live_oauth_added_during_old_connection_cleanup_prevents_http(tmp_path, trusted_tls, monkeypatch):
    async with HttpPeer(ssl_context=trusted_tls) as peer:
        manager, settings = runtime(tmp_path, McpServerConfig(transport="streamable_http", url=peer.url))
        original = manager.disconnect_server

        async def changed(name):
            await original(name)
            _enable_oauth(settings, peer)

        monkeypatch.setattr(manager, "disconnect_server", changed)
        try:
            with pytest.raises(RuntimeError):
                await manager.connect_server("fixture")
            assert peer.requests == [] and not manager.clients and not manager._connecting
        finally:
            await manager.disconnect_all()


async def test_live_oauth_added_after_automatic_connection_denies_retained_tool(tmp_path, trusted_tls):
    async with HttpPeer(ssl_context=trusted_tls) as peer:
        manager, settings = runtime(tmp_path, McpServerConfig(transport="streamable_http", url=peer.url))
        try:
            await manager.connect_server("fixture")
            tool, = manager.get_all_tools()
            assert (await tool.execute(region="north")).success
            before = len(peer.requests)
            _enable_oauth(settings, peer)
            with pytest.raises(RuntimeError):
                await tool.execute(region="north")
            assert len(peer.requests) == before and peer.effects == 1
            assert manager.get_all_tools() == []
        finally:
            await manager.disconnect_all()


@pytest.mark.parametrize("timing", ["catalog", "publication"])
async def test_live_oauth_added_before_automatic_catalog_publication_denies_connection(
    tmp_path, trusted_tls, monkeypatch, timing,
):
    async with HttpPeer(ssl_context=trusted_tls) as peer:
        manager, settings = runtime(tmp_path, McpServerConfig(transport="streamable_http", url=peer.url))
        registry = ToolRegistry()
        manager.bind_registry(registry)
        if timing == "catalog":
            peer.delays["tools/list"] = .2
        else:
            original = manager._update_bound_server

            def changed(name):
                original(name)
                _enable_oauth(settings, peer)

            monkeypatch.setattr(manager, "_update_bound_server", changed)
        operation = asyncio.create_task(manager.connect_server("fixture"))
        try:
            if timing == "catalog":
                await wait_until(lambda: any(item["body"].get("method") == "tools/list" for item in peer.requests))
                _enable_oauth(settings, peer)
            with pytest.raises(RuntimeError):
                await operation
            assert not manager.clients and not manager._connecting
            assert registry.get("mcp_fixture_effect") is None and peer.effects == 0
        finally:
            if not operation.done():
                operation.cancel()
            await asyncio.gather(operation, return_exceptions=True)
            await manager.disconnect_all()


@pytest.mark.parametrize("primary_cancel", [False, True])
async def test_failed_oauth_publication_cleanup_preserves_cancellation_precedence(
    tmp_path, trusted_tls, monkeypatch, primary_cancel,
):
    async with HttpPeer(ssl_context=trusted_tls) as peer:
        manager, _settings, _config = native_authority(peer, tmp_path)
        cleanup = asyncio.Event()
        owned = []

        def fail_publication(name):
            client = manager.clients[name]
            owned.append(client)
            original_disconnect = client.disconnect

            async def delayed_disconnect():
                cleanup.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    await original_disconnect()
                    raise

            monkeypatch.setattr(client, "disconnect", delayed_disconnect)
            if primary_cancel:
                raise asyncio.CancelledError("original publication cancellation")
            raise OAuthError("catalog publication refused")

        monkeypatch.setattr(manager, "_update_bound_server", fail_publication)
        operation = asyncio.create_task(manager.connect_oauth_server("fixture", authorize=allowed))
        await asyncio.wait_for(cleanup.wait(), 3)
        operation.cancel("cancel failed OAuth connection cleanup")
        reason = "original publication cancellation" if primary_cancel else "cancel failed OAuth connection cleanup"
        try:
            with pytest.raises(asyncio.CancelledError, match=reason):
                await operation
            assert not manager.clients and not manager._connecting
        finally:
            assert all(client._owner_task is None for client in owned)
            await manager.disconnect_all()
