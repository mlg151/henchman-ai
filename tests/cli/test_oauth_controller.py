"""Runtime-only OAuth intent; no frontend, real browser or account is opened."""

# ruff: noqa: F811 -- imported fixtures are resolved by pytest.

import asyncio
import copy
import pickle
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from henchman.cli.oauth import OAuthController, OAuthIntent, OAuthRuntimeView
from henchman.core.session_helpers import compute_project_hash
from henchman.mcp.oauth import OAuthError
from tests.cli.test_oauth_browser import assert_joined, synthetic_launcher, wait_until  # noqa: F401
from tests.mcp.http_fixture import HttpPeer
from tests.mcp.oauth_fixture import OAuthPeer
from tests.mcp.test_oauth_discovery import tls_contexts, trusted_tls  # noqa: F401
from tests.mcp.test_oauth_flow import browser
from tests.mcp.test_oauth_manager import native_config, runtime
from tests.mcp.test_oauth_transport import native_authority


@pytest.fixture
def controller(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager, settings = runtime(tmp_path)
    current = [OAuthRuntimeView(frontend=object(), session=SimpleNamespace(id="session", project_hash=compute_project_hash(tmp_path)),
        settings=settings, project_root=tmp_path, manager=manager, agent=object(), lifecycle=object(), idle=True)]
    controller = OAuthController(lambda: current[0])
    return controller, current, manager


async def test_only_owned_single_use_runtime_intent_can_dispatch(controller):
    owner, current, manager = controller
    with pytest.raises(OAuthError):
        await owner.execute(OAuthIntent())
    ticket = owner.capture_user_intent("status", "fixture")
    for copier in (copy.copy, copy.deepcopy, pickle.dumps):
        with pytest.raises(TypeError):
            copier(ticket)
    other = OAuthController(lambda: current[0])
    with pytest.raises(OAuthError):
        await other.execute(ticket)
    assert (await owner.execute(ticket)).state == "missing"
    with pytest.raises(OAuthError):
        await owner.execute(ticket)
    assert manager.clients == {}


@pytest.mark.parametrize("change", ["frontend", "session", "session_id", "settings", "project", "manager", "agent", "lifecycle", "closed", "config"])
async def test_ticket_rejects_changed_runtime_before_any_manager_action(controller, monkeypatch, tmp_path, change):
    owner, current, manager = controller
    ticket = owner.capture_user_intent("status", "fixture")
    calls = []
    monkeypatch.setattr(manager, "oauth_status", lambda *args, **_kwargs: calls.append(args))
    if change == "session_id":
        current[0].session.id = "changed"
    elif change == "settings":
        current[0] = replace(current[0], settings=current[0].settings.model_copy(deep=True))
    elif change == "config":
        current[0].settings.mcp_servers["fixture"].oauth.client_id = "changed"
    elif change == "project":
        other = tmp_path / "other"
        other.mkdir()
        current[0] = replace(current[0], project_root=other)
    else:
        current[0] = replace(current[0], **{change: True if change == "closed" else object()})
    with pytest.raises(OAuthError):
        await owner.execute(ticket)
    assert not calls


@pytest.mark.parametrize("action", ["login", "refresh", "connect"])
async def test_network_intent_requires_idle_at_capture_and_execution(controller, action):
    owner, current, _manager = controller
    current[0] = replace(current[0], idle=False)
    with pytest.raises(OAuthError):
        owner.capture_user_intent(action, "fixture")
    current[0] = replace(current[0], idle=True)
    ticket = owner.capture_user_intent(action, "fixture")
    current[0] = replace(current[0], idle=False)
    with pytest.raises(OAuthError):
        await owner.execute(ticket)


async def test_status_and_logout_are_held_controls_while_busy(controller):
    owner, current, manager = controller
    current[0] = replace(current[0], idle=False)
    assert (await owner.execute(owner.capture_user_intent("status", "fixture"))).state == "missing"
    assert (await owner.execute(owner.capture_user_intent("logout", "fixture"))).state == "revoked"
    assert manager.clients == {}


async def test_connection_keeps_runtime_guard_after_ticket_consumption_but_not_idle_guard(controller, monkeypatch):
    owner, current, manager = controller
    held = []

    async def connect(_server, *, authorize):
        authorize()
        held.append(authorize)

    monkeypatch.setattr(manager, "connect_oauth_server", connect)
    ticket = owner.capture_user_intent("connect", "fixture")
    await owner.execute(ticket)
    current[0] = replace(current[0], idle=False)
    held[0]()
    with pytest.raises(OAuthError):
        await owner.execute(ticket)
    current[0] = replace(current[0], lifecycle=object())
    with pytest.raises(OAuthError):
        held[0]()


async def test_shutdown_cancels_and_joins_owned_action_and_revokes_tickets(controller, monkeypatch):
    owner, _current, manager = controller
    entered, settled = asyncio.Event(), asyncio.Event()

    async def refresh(_server, *, authorize):
        authorize()
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            settled.set()

    monkeypatch.setattr(manager, "oauth_refresh", refresh)
    pending = owner.capture_user_intent("status", "fixture")
    work = asyncio.create_task(owner.execute(owner.capture_user_intent("refresh", "fixture")))
    await entered.wait()
    assert owner.has_active_action()
    await owner.aclose()
    assert work.cancelled() and settled.is_set() and not owner.has_active_action()
    with pytest.raises(OAuthError):
        await owner.execute(pending)


@pytest.mark.parametrize(("revoke", "metadata_delay"), [
    pytest.param("manager", 0, id="manager"),
    pytest.param("store", 0, id="store"),
    pytest.param("manager", 2.1, id="slow-metadata"),
])
async def test_full_login_claim_guard_rechecked_after_browser_ready(
    tmp_path, monkeypatch, trusted_tls, synthetic_launcher, revoke, metadata_delay,
):
    from henchman.mcp.auth import McpAuthService

    monkeypatch.chdir(tmp_path)
    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        peer.routes[peer.resource_path] = (200, peer.resource, {}, metadata_delay)
        manager, settings = runtime(tmp_path, native_config(peer))
        view = OAuthRuntimeView(object(), None, settings, tmp_path, manager, object(), object(), True)
        owner = OAuthController(lambda: view)
        choose, _calls, processes = synthetic_launcher
        target = choose("wait_ready")
        operation = asyncio.create_task(owner.execute(owner.capture_user_intent("login", "fixture")))
        try:
            # This phase includes TLS metadata discovery before the launcher is
            # spawned; allow loaded native runners time without hiding errors.
            await wait_until(lambda: bool(processes), operation=operation, timeout=40)
            if revoke == "manager":
                manager.oauth_logout("fixture", authorize=lambda: None)
            else:
                McpAuthService(tmp_path).oauth_store().logout("fixture")
            Path(str(target) + ".ready").touch()
            with pytest.raises(OAuthError):
                await operation
            assert not target.exists() and not peer.token_forms
            assert_joined(processes)
        finally:
            try:
                await owner.aclose()
            finally:
                if not operation.done():
                    operation.cancel()
                await asyncio.gather(operation, return_exceptions=True)


def test_session_from_another_project_cannot_issue_auth_intent(controller):
    owner, current, _manager = controller
    current[0].session.project_hash = "other-project"
    with pytest.raises(OAuthError):
        owner.capture_user_intent("status", "fixture")


def test_unknown_url_cannot_become_a_persisted_logout_server(controller, tmp_path):
    owner, _current, _manager = controller
    with pytest.raises(OAuthError) as caught:
        owner.capture_user_intent("logout", "https://issuer.invalid/authorize?state=private-canary")
    assert "canary" not in str(caught.value)
    assert not (tmp_path / ".henchman/mcp/oauth.json").exists()


async def test_manager_teardown_invalidates_already_captured_intent(controller):
    owner, _current, manager = controller
    ticket = owner.capture_user_intent("status", "fixture")
    await manager.disconnect_all()
    with pytest.raises(OAuthError):
        await owner.execute(ticket)
    assert (await owner.execute(owner.capture_user_intent("status", "fixture"))).state == "missing"


async def test_logout_invalidates_a_network_ticket_captured_before_it(controller, monkeypatch):
    owner, _current, manager = controller
    calls = []

    async def connect(*_args, **_kwargs):
        calls.append(True)

    monkeypatch.setattr(manager, "connect_oauth_server", connect)
    ticket = owner.capture_user_intent("connect", "fixture")
    await owner.execute(owner.capture_user_intent("logout", "fixture"))
    with pytest.raises(OAuthError):
        await owner.execute(ticket)
    assert not calls


async def test_native_controller_login_refresh_logout_never_connects_or_retains_url(tmp_path, monkeypatch, trusted_tls, caplog):
    monkeypatch.chdir(tmp_path)
    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        manager, settings = runtime(tmp_path, native_config(peer))
        view = OAuthRuntimeView(object(), None, settings, tmp_path, manager, object(), object(), True)

        async def owned_browser(url, authorize):
            authorize()
            await browser(url)

        owner = OAuthController(lambda: view, browser_opener=owned_browser)
        try:
            assert (await owner.execute(owner.capture_user_intent("login", "fixture"))).state == "ready"
            assert (await owner.execute(owner.capture_user_intent("refresh", "fixture"))).state == "ready"
            assert (await owner.execute(owner.capture_user_intent("logout", "fixture"))).state == "revoked"
            assert manager.clients == {} and not owner._tickets and not owner._active
            assert len(peer.token_forms) == 2 and "canary" not in caplog.text
        finally:
            await owner.aclose()


async def test_native_connection_guard_outlives_ticket_but_rejects_session_switch(tmp_path, monkeypatch, trusted_tls):
    monkeypatch.chdir(tmp_path)
    async with HttpPeer(ssl_context=trusted_tls) as peer:
        manager, settings, _config = native_authority(peer, tmp_path)
        view = [OAuthRuntimeView(object(), None, settings, tmp_path, manager, object(), object(), True)]
        owner = OAuthController(lambda: view[0])
        try:
            await owner.execute(owner.capture_user_intent("connect", "fixture"))
            view[0] = replace(view[0], idle=False)
            tool, = manager.get_all_tools()
            assert (await tool.execute(region="north")).success
            view[0] = replace(view[0], session=SimpleNamespace(id="new-session", project_hash=compute_project_hash(tmp_path)))
            before = len(peer.requests)
            with pytest.raises(OAuthError):
                await tool.execute(region="north")
            assert len(peer.requests) == before and peer.effects == 1
        finally:
            await owner.aclose()
            await manager.disconnect_all()


async def test_queued_cancellation_before_execute_cannot_commit_logout(controller):
    owner, _current, manager = controller
    ticket = owner.capture_user_intent("logout", "fixture")

    async def submit():
        asyncio.current_task().cancel("cancel user submission")
        await owner.execute(ticket)
        await asyncio.sleep(0)

    task = asyncio.create_task(submit())
    with pytest.raises(asyncio.CancelledError, match="cancel user submission"):
        await task
    assert manager.oauth_status("fixture", authorize=lambda: None).state == "missing"
    with pytest.raises(OAuthError):
        await owner.execute(ticket)


@pytest.mark.parametrize("action,guard_number,expected_state", [
    ("logout", 2, "missing"), ("status", 3, "missing"), ("logout", 3, "configuration_changed"),
])
async def test_synchronous_guard_cancellation_prevents_effect_or_success_publication(controller, action, guard_number, expected_state):
    owner, current, manager = controller
    ticket = owner.capture_user_intent(action, "fixture")
    checks = 0

    def view():
        nonlocal checks
        checks += 1
        if checks == guard_number:
            asyncio.current_task().cancel("cancel synchronous OAuth guard")
        return current[0]

    owner._current = view

    async def submit():
        await owner.execute(ticket)
        pytest.fail("Queued guard cancellation cannot publish success")

    with pytest.raises(asyncio.CancelledError, match="cancel synchronous OAuth guard"):
        await asyncio.create_task(submit())
    assert checks >= guard_number
    assert manager.oauth_status("fixture", authorize=lambda: None).state == expected_state


async def test_retained_native_guard_cancellation_sends_no_rpc(tmp_path, monkeypatch, trusted_tls):
    monkeypatch.chdir(tmp_path)
    async with HttpPeer(ssl_context=trusted_tls) as peer:
        manager, settings, _config = native_authority(peer, tmp_path)
        view = OAuthRuntimeView(object(), None, settings, tmp_path, manager, object(), object(), True)
        owner = OAuthController(lambda: view)
        try:
            await owner.execute(owner.capture_user_intent("connect", "fixture"))
            tool, = manager.get_all_tools()
            before = len(peer.requests)

            def cancelled_view():
                asyncio.current_task().cancel("cancel retained OAuth request")
                return view

            owner._current = cancelled_view
            with pytest.raises(asyncio.CancelledError, match="cancel retained OAuth request"):
                await asyncio.create_task(tool.execute(region="north"))
            assert len(peer.requests) == before and peer.effects == 0
        finally:
            await owner.aclose()
            await manager.disconnect_all()
