"""Manager OAuth authority stays bound to trusted runtime settings and one project."""

# ruff: noqa: F811 -- imported fixtures are resolved by pytest parameter name.

import asyncio
import json
import traceback

import pytest

from henchman.config.runtime import RuntimeSettingsState
from henchman.config.schema import Settings
from henchman.mcp.manager import McpManager
from henchman.mcp.oauth import OAuthError
from henchman.utils.evidence_redaction import EvidenceRedactor
from tests.mcp.oauth_fixture import OAuthPeer
from tests.mcp.test_oauth_discovery import tls_contexts, trusted_tls  # noqa: F401
from tests.mcp.test_oauth_flow import browser
from tests.mcp.test_oauth_foundation import configuration
from tests.mcp.test_oauth_store import binding, ready, store


def allowed():
    return None


def runtime(tmp_path, config=None, **tools):
    settings = Settings(mcp_servers={"fixture": config or configuration()}, tools=tools)
    manager = McpManager.create_from_settings(settings, project_root=tmp_path)
    assert manager is not None
    return manager, settings


def native_config(peer):
    return configuration(issuer=peer.issuer).model_copy(update={"url": peer.endpoint})


def test_bound_status_is_read_only_and_never_lends_another_config_authority(tmp_path):
    service = store(tmp_path)
    assert service.bound_status(binding()) == (service.status("fixture"), None)
    assert not (tmp_path / ".henchman").exists()
    authority = ready(service)
    path = tmp_path / ".henchman/mcp/oauth.json"
    before = path.read_bytes()
    status, matching = service.bound_status(binding())
    assert matching == authority and status.state == "ready"
    stale, absent = service.bound_status(binding("changed-client"))
    assert stale.state == "configuration_changed" and absent is None
    assert not stale.refresh_available and stale.expires_at is None
    assert path.read_bytes() == before
    assert "canary" not in repr((status, matching, stale))


def test_bound_status_validates_persisted_destination_before_returning_authority(tmp_path):
    service = store(tmp_path)
    ready(service)
    path = tmp_path / ".henchman/mcp/oauth.json"
    payload = json.loads(path.read_bytes())
    payload["records"]["fixture"]["credentials"]["token_endpoint"] = "https://outside.example/private-canary"
    path.write_text(json.dumps(payload))
    with pytest.raises(OAuthError) as caught:
        service.bound_status(binding())
    assert "private-canary" not in "".join(traceback.format_exception(caught.value))


def test_manager_status_uses_fixed_root_without_writing_or_following_cwd(tmp_path, monkeypatch):
    manager, _settings = runtime(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    assert manager.oauth_status("fixture", authorize=allowed).state == "missing"
    assert not (tmp_path / ".henchman").exists()
    assert not (other / ".henchman").exists()


def test_explicit_binding_cannot_be_replaced_by_another_project_or_settings_owner(tmp_path):
    manager = McpManager({"fixture": configuration()})
    with pytest.raises(OAuthError, match="runtime"):
        manager.oauth_status("fixture", authorize=allowed)
    settings = Settings(mcp_servers={"fixture": configuration()})
    manager.bind_oauth_runtime(settings, project_root=tmp_path)
    manager.bind_oauth_runtime(settings, project_root=tmp_path)
    for replacement, root in ((settings.model_copy(deep=True), tmp_path), (settings, tmp_path / "other")):
        with pytest.raises(OAuthError):
            manager.bind_oauth_runtime(replacement, project_root=root)


@pytest.mark.parametrize("authorization", [None, False, lambda: False])
def test_explicit_trusted_caller_is_required_before_storage_access(tmp_path, authorization):
    manager, _settings = runtime(tmp_path)
    with pytest.raises(OAuthError):
        manager.oauth_status("fixture", authorize=authorization)
    assert not (tmp_path / ".henchman").exists()


def test_caller_exception_is_value_free_and_config_trust_is_not_login_authority(tmp_path):
    manager, _settings = runtime(tmp_path, configuration().model_copy(update={"trusted": True}))

    def denied():
        raise RuntimeError("private-caller-canary")

    with pytest.raises(OAuthError) as caught:
        manager.oauth_status("fixture", authorize=denied)
    assert "private-caller-canary" not in "".join(traceback.format_exception(caught.value))
    assert not (tmp_path / ".henchman").exists()


def test_status_rechecks_live_replaced_settings_without_rebinding_record(tmp_path):
    service = store(tmp_path)
    ready(service)
    manager, settings = runtime(tmp_path)
    path = tmp_path / ".henchman/mcp/oauth.json"
    before = path.read_bytes()
    assert manager.oauth_status("fixture", authorize=allowed).state == "ready"
    state = RuntimeSettingsState.from_settings(settings)
    state.update({"mcp_servers": {"fixture": {"oauth": {"client_id": "changed-client"}}}})
    assert manager.oauth_status("fixture", authorize=allowed).state == "configuration_changed"
    assert path.read_bytes() == before


def test_local_status_logout_remain_available_under_network_restriction_and_retain_evidence(tmp_path):
    service = store(tmp_path)
    ready(service)
    manager, settings = runtime(tmp_path, network_access="disabled")
    policy = EvidenceRedactor()
    manager.register_evidence(policy)
    assert manager.oauth_status("fixture", authorize=allowed).state == "ready"
    settings.mcp_servers.clear()
    assert manager.oauth_logout("fixture", authorize=allowed).state == "revoked"
    late = EvidenceRedactor()
    manager.register_evidence(late)
    for evidence in (policy, late):
        assert evidence.text("access-private-canary refresh-private-canary") == "[REDACTED] [REDACTED]"


@pytest.mark.parametrize("control", [{"network_access": "disabled"}, {"network_allowed_hosts": []},
                                    {"filesystem_read_roots": []}, {"sandbox": "docker"}])
async def test_initial_tool_restrictions_cannot_be_widened_before_login(tmp_path, trusted_tls, control):
    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        manager, settings = runtime(tmp_path, native_config(peer), **control)
        settings.tools = Settings().tools
        with pytest.raises(OAuthError):
            await manager.oauth_login("fixture", authorize=allowed, browser_opener=browser)
        assert peer.requests == []
        assert not (tmp_path / ".henchman/mcp/oauth.json").exists()


async def test_native_manager_login_refresh_logout_never_connects_or_promotes_stdio_token(tmp_path, trusted_tls):
    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        manager, _settings = runtime(tmp_path, native_config(peer))
        policy = EvidenceRedactor()
        manager.register_evidence(policy)
        status = await manager.oauth_login("fixture", authorize=allowed, browser_opener=browser)
        assert status.state == "ready" and manager.clients == {}
        peer.routes["/token"] = (200, {"access_token": "rotated-access-canary", "token_type": "Bearer"}, {}, 0)
        assert (await manager.oauth_refresh("fixture", authorize=allowed)).state == "ready"
        assert len(peer.token_forms) == 2 and manager.clients == {}
        before = len(peer.requests)
        with pytest.raises(RuntimeError, match="not yet supported"):
            await manager.connect_server("fixture")
        assert len(peer.requests) == before
        assert manager.oauth_logout("fixture", authorize=allowed).state == "revoked"
        assert policy.text("issued-access-private-canary rotated-access-canary") == "[REDACTED] [REDACTED]"
        assert "canary" not in repr(status)


@pytest.mark.parametrize("change", ["settings", "policy", "caller", "logout", "disconnect"])
async def test_live_authority_change_during_browser_wait_prevents_token_dispatch(tmp_path, trusted_tls, change):
    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        manager, settings = runtime(tmp_path, native_config(peer))
        caller_allowed = True

        def authorize():
            if not caller_allowed:
                raise RuntimeError("private-caller-canary")

        async def opener(url):
            nonlocal caller_allowed
            await browser(url)
            if change == "settings":
                RuntimeSettingsState.from_settings(settings).update({"mcp_servers": {"fixture": {"oauth": {"client_id": "changed"}}}})
            elif change == "policy":
                settings.tools.network_access = "disabled"
            elif change == "caller":
                caller_allowed = False
            elif change == "logout":
                manager.oauth_logout("fixture", authorize=allowed)
            else:
                await manager.disconnect_server("fixture")

        with pytest.raises(OAuthError) as caught:
            await manager.oauth_login("fixture", authorize=authorize, browser_opener=opener)
        assert peer.token_forms == []
        assert "private-caller-canary" not in "".join(traceback.format_exception(caught.value))


async def test_concurrent_login_is_rejected_before_second_discovery_and_logout_revokes_owner(tmp_path, trusted_tls):
    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        manager, _settings = runtime(tmp_path, native_config(peer))
        entered, release = asyncio.Event(), asyncio.Event()

        async def opener(url):
            entered.set()
            await release.wait()
            await browser(url)

        owner = asyncio.create_task(manager.oauth_login("fixture", authorize=allowed, browser_opener=opener))
        try:
            await asyncio.wait_for(entered.wait(), 2)
            before = len(peer.requests)
            with pytest.raises(OAuthError, match="pending"):
                await manager.oauth_login("fixture", authorize=allowed, browser_opener=browser)
            assert len(peer.requests) == before
            manager.oauth_logout("fixture", authorize=allowed)
            release.set()
            with pytest.raises(OAuthError):
                await owner
            assert peer.token_forms == []
        finally:
            owner.cancel()
            await asyncio.gather(owner, return_exceptions=True)


async def test_refresh_rejects_stale_config_without_binding_or_http(tmp_path, trusted_tls):
    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        manager, settings = runtime(tmp_path, native_config(peer))
        await manager.oauth_login("fixture", authorize=allowed, browser_opener=browser)
        path = tmp_path / ".henchman/mcp/oauth.json"
        before = path.read_bytes(), len(peer.requests)
        settings.mcp_servers["fixture"].oauth.client_id = "other-client"
        with pytest.raises(OAuthError):
            await manager.oauth_refresh("fixture", authorize=allowed)
        assert (path.read_bytes(), len(peer.requests)) == before


async def test_fresh_manager_refreshes_matching_persisted_authority_without_discovery(tmp_path, trusted_tls):
    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        first, settings = runtime(tmp_path, native_config(peer))
        await first.oauth_login("fixture", authorize=allowed, browser_opener=browser)
        second = McpManager.create_from_settings(settings, project_root=tmp_path)
        before = len(peer.requests)
        assert (await second.oauth_refresh("fixture", authorize=allowed)).state == "ready"
        assert len(peer.requests) == before + 1
        assert peer.token_forms[-1]["grant_type"] == "refresh_token"


async def test_two_managers_cannot_dispatch_the_same_rotating_refresh_authority(tmp_path, trusted_tls):
    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        first, settings = runtime(tmp_path, native_config(peer))
        await first.oauth_login("fixture", authorize=allowed, browser_opener=browser)
        second = McpManager.create_from_settings(settings, project_root=tmp_path)
        peer.routes["/token"] = (200, peer.token_response, {}, .1)
        owner = asyncio.create_task(first.oauth_refresh("fixture", authorize=allowed))
        try:
            async with asyncio.timeout(2):
                while len(peer.token_forms) < 2:
                    await asyncio.sleep(.001)
            with pytest.raises(OAuthError, match="pending"):
                await second.oauth_refresh("fixture", authorize=allowed)
            assert (await owner).state == "ready"
            assert len(peer.token_forms) == 2
        finally:
            owner.cancel()
            await asyncio.gather(owner, return_exceptions=True)


async def test_status_publication_rechecks_exact_completed_generation(tmp_path, trusted_tls, monkeypatch):
    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        manager, _settings = runtime(tmp_path, native_config(peer))
        service = manager._oauth_runtime._store
        original = service.bound_status

        def changed_before_snapshot(binding):
            # A different process can commit revocation between any two reads.
            store(tmp_path).logout("fixture")
            return original(binding)

        monkeypatch.setattr(service, "bound_status", changed_before_snapshot)
        with pytest.raises(OAuthError, match="authority|generation"):
            await manager.oauth_login("fixture", authorize=allowed, browser_opener=browser)
        assert service.status("fixture").state == "revoked"
        assert len(peer.token_forms) == 1


def test_legacy_stdio_credentials_never_count_as_oauth_ready_or_refresh_authority(tmp_path):
    from henchman.mcp.auth import McpAuthService

    McpAuthService(tmp_path).set_token("fixture", "legacy-stdio-private-canary")
    manager, _settings = runtime(tmp_path)
    assert manager.oauth_status("fixture", authorize=allowed).state == "missing"
    assert not (tmp_path / ".henchman/mcp/oauth.json").exists()


@pytest.mark.parametrize("change", ["config", "policy", "caller"])
async def test_authority_changes_after_token_dispatch_deny_publication(tmp_path, trusted_tls, change):
    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        peer.routes["/token"] = (200, peer.token_response, {}, .1)
        manager, settings = runtime(tmp_path, native_config(peer))
        permitted = True

        def authorize():
            if not permitted:
                raise RuntimeError("private-late-caller-canary")

        owner = asyncio.create_task(manager.oauth_login("fixture", authorize=authorize, browser_opener=browser))
        try:
            async with asyncio.timeout(2):
                while not peer.token_forms:
                    await asyncio.sleep(.001)
            if change == "config":
                settings.mcp_servers["fixture"].oauth.client_id = "changed"
            elif change == "policy":
                settings.tools.network_access = "disabled"
            else:
                permitted = False
            with pytest.raises(OAuthError) as caught:
                await owner
            assert "canary" not in "".join(traceback.format_exception(caught.value))
            assert store(tmp_path).status("fixture").state == "login_started"
            assert len(peer.token_forms) == 1
        finally:
            owner.cancel()
            await asyncio.gather(owner, return_exceptions=True)


@pytest.mark.parametrize("operation", ["login", "refresh"])
async def test_disconnect_all_revokes_oauth_only_pending_and_dispatched_operations(tmp_path, trusted_tls, operation):
    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        manager, _settings = runtime(tmp_path, native_config(peer))
        entered, release = asyncio.Event(), asyncio.Event()

        async def opener(url):
            entered.set()
            await release.wait()
            await browser(url)

        if operation == "refresh":
            await manager.oauth_login("fixture", authorize=allowed, browser_opener=browser)
            peer.routes["/token"] = (200, peer.token_response, {}, .1)
            owner = asyncio.create_task(manager.oauth_refresh("fixture", authorize=allowed))
        else:
            owner = asyncio.create_task(manager.oauth_login("fixture", authorize=allowed, browser_opener=opener))
        try:
            async with asyncio.timeout(2):
                if operation == "login":
                    await entered.wait()
                else:
                    while len(peer.token_forms) < 2:
                        await asyncio.sleep(.001)
            assert manager.clients == {} and manager._connecting == {}
            await manager.disconnect_all()
            release.set()
            with pytest.raises(OAuthError):
                await owner
            assert len(peer.token_forms) == (0 if operation == "login" else 2)
            assert manager.oauth_status("fixture", authorize=allowed).state == (
                "needs_login" if operation == "login" else "refresh_started")
            assert manager.oauth_logout("fixture", authorize=allowed).state == "revoked"
        finally:
            owner.cancel()
            await asyncio.gather(owner, return_exceptions=True)


async def test_disconnect_all_invalidates_oauth_before_awaiting_other_transport_cleanup(tmp_path, trusted_tls):
    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        manager, _settings = runtime(tmp_path, native_config(peer))
        browser_entered, browser_release = asyncio.Event(), asyncio.Event()
        cleanup_entered, cleanup_release = asyncio.Event(), asyncio.Event()

        class ClosingClient:
            async def disconnect(self):
                cleanup_entered.set()
                await cleanup_release.wait()

        async def opener(url):
            browser_entered.set()
            await browser_release.wait()
            await browser(url)

        manager.clients["other-transport"] = ClosingClient()
        owner = asyncio.create_task(manager.oauth_login("fixture", authorize=allowed, browser_opener=opener))
        shutdown = None
        try:
            await asyncio.wait_for(browser_entered.wait(), 2)
            shutdown = asyncio.create_task(manager.disconnect_all())
            await asyncio.wait_for(cleanup_entered.wait(), 2)
            browser_release.set()
            with pytest.raises(OAuthError):
                await owner
            assert peer.token_forms == []
        finally:
            cleanup_release.set()
            owner.cancel()
            await asyncio.gather(owner, return_exceptions=True)
            if shutdown is not None:
                await asyncio.wait_for(shutdown, 2)


@pytest.mark.parametrize("settlement", ["success", "failure", "cancellation"])
async def test_disconnect_all_blocks_new_oauth_admission_only_until_cleanup_settles(tmp_path, trusted_tls, settlement):
    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        manager, _settings = runtime(tmp_path, native_config(peer))
        entered, release = asyncio.Event(), asyncio.Event()

        class ClosingClient:
            async def disconnect(self):
                entered.set()
                await release.wait()
                if settlement == "failure":
                    raise RuntimeError("fixture cleanup failure")

        manager.clients["other-transport"] = ClosingClient()
        shutdown = asyncio.create_task(manager.disconnect_all())
        try:
            await asyncio.wait_for(entered.wait(), 2)
            # An overlapping teardown with no remaining transport must not
            # release the first teardown's admission barrier.
            await manager.disconnect_all()
            with pytest.raises(OAuthError, match="teardown"):
                await manager.oauth_login("fixture", authorize=allowed, browser_opener=browser)
            assert peer.requests == []
            assert manager.oauth_status("fixture", authorize=allowed).state == "missing"
            assert manager.oauth_logout("fixture", authorize=allowed).state == "revoked"
        finally:
            if settlement == "cancellation":
                shutdown.cancel()
            release.set()
            if settlement == "success":
                await asyncio.wait_for(shutdown, 2)
            else:
                expected = asyncio.CancelledError if settlement == "cancellation" else RuntimeError
                with pytest.raises(expected):
                    await asyncio.wait_for(shutdown, 2)
        assert (await manager.oauth_login("fixture", authorize=allowed, browser_opener=browser)).state == "ready"
