"""Native TLS pauses verify OAuth authority at the actual pre-header boundary."""

# ruff: noqa: F811 -- pytest resolves imported fixtures by parameter name.

import asyncio
import traceback

import anyio
import httpx2
import pytest
from httpcore2._async.connection import AsyncHTTPConnection

from henchman.mcp.oauth import OAuthError
from tests.mcp.oauth_fixture import OAuthPeer
from tests.mcp.test_oauth_discovery import tls_contexts, trusted_tls  # noqa: F401
from tests.mcp.test_oauth_flow import browser
from tests.mcp.test_oauth_manager import allowed, native_config, runtime


class TLSGate:
    def __init__(self, monkeypatch, path):
        self.entered, self.release = asyncio.Event(), asyncio.Event()
        self.connections = 0
        original = AsyncHTTPConnection._connect

        async def paused(connection, request):
            stream = await original(connection, request)
            if request.url.target == path.encode():
                self.connections += 1
                self.entered.set()
                try:
                    await self.release.wait()
                except BaseException:
                    # The test intercepted a newly created stream before the
                    # library could own it; cancellation must close that stream.
                    with anyio.CancelScope(shield=True):
                        await stream.aclose()
                    raise
            return stream

        monkeypatch.setattr(AsyncHTTPConnection, "_connect", paused)


async def settled(peer):
    async with asyncio.timeout(2):
        while peer.tasks or peer.writers:
            await asyncio.sleep(.001)


@pytest.mark.parametrize("phase", ["resource", "issuer", "code", "refresh"])
@pytest.mark.parametrize("change", ["settings", "configuration", "project", "policy", "logout"])
async def test_authority_changes_during_tls_wait_send_zero_http_bytes(tmp_path, trusted_tls, monkeypatch, phase, change):
    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        manager, settings = runtime(tmp_path, native_config(peer))
        current = {"settings": settings, "project": tmp_path}

        def authorize():
            if current["settings"] is not settings or current["project"] != tmp_path:
                raise OAuthError("Trusted runtime owner changed")

        if phase == "refresh":
            await manager.oauth_login("fixture", authorize=authorize, browser_opener=browser)
        path = {"resource": peer.resource_path, "issuer": peer.issuer_path,
                "code": "/token", "refresh": "/token"}[phase]
        gate = TLSGate(monkeypatch, path)
        operation = asyncio.create_task(manager.oauth_refresh("fixture", authorize=authorize) if phase == "refresh"
            else manager.oauth_login("fixture", authorize=authorize, browser_opener=browser))
        try:
            await asyncio.wait_for(gate.entered.wait(), 2)
            before_bytes, before_requests, before_tokens = peer.application_bytes, len(peer.requests), len(peer.token_forms)
            if change == "settings":
                current["settings"] = settings.model_copy(deep=True)
            elif change == "configuration":
                settings.mcp_servers["fixture"].oauth.client_id = "changed-client"
            elif change == "project":
                current["project"] = tmp_path / "other"
            elif change == "policy":
                settings.tools.network_access = "disabled"
            else:
                manager.oauth_logout("fixture", authorize=allowed)
            gate.release.set()
            with pytest.raises(OAuthError) as caught:
                await asyncio.wait_for(operation, 3)
            await settled(peer)
            assert peer.application_bytes == before_bytes
            assert len(peer.requests) == before_requests and len(peer.token_forms) == before_tokens
            assert gate.connections == 1
            assert "canary" not in "".join(traceback.format_exception(caught.value))
            expected = "revoked" if change == "logout" else ("needs_login" if phase in {"code", "refresh"} else "empty")
            assert manager._oauth_runtime._store.status("fixture").state == expected
        finally:
            gate.release.set()
            operation.cancel()
            await asyncio.gather(operation, return_exceptions=True)
            await manager.disconnect_all()
    assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("henchman-oauth-callback")]


@pytest.mark.parametrize("phase", ["code", "refresh"])
async def test_cancel_before_token_headers_settles_claim_without_releasing_rotating_token(tmp_path, trusted_tls, monkeypatch, phase):
    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        manager, _settings = runtime(tmp_path, native_config(peer))
        if phase == "refresh":
            await manager.oauth_login("fixture", authorize=allowed, browser_opener=browser)
        gate = TLSGate(monkeypatch, "/token")
        operation = asyncio.create_task(manager.oauth_refresh("fixture", authorize=allowed) if phase == "refresh"
            else manager.oauth_login("fixture", authorize=allowed, browser_opener=browser))
        try:
            await asyncio.wait_for(gate.entered.wait(), 2)
            before = peer.application_bytes
            operation.cancel("pre-header cancellation")
            with pytest.raises(asyncio.CancelledError, match="pre-header cancellation"):
                await asyncio.wait_for(operation, 2)
            await settled(peer)
            assert peer.application_bytes == before
            assert manager._oauth_runtime._store.status("fixture").state == "needs_login"
            assert len(peer.token_forms) == (1 if phase == "refresh" else 0)
            with pytest.raises(OAuthError):
                await manager.oauth_refresh("fixture", authorize=allowed)
            assert peer.application_bytes == before
        finally:
            gate.release.set()
            operation.cancel()
            await asyncio.gather(operation, return_exceptions=True)
            await manager.disconnect_all()


@pytest.mark.parametrize("extension", ["trace", "target", "sni_hostname", "unknown"])
def test_guard_rejects_preexisting_transport_extensions(extension):
    from henchman.mcp.http_guard import guard_http_request

    request = httpx2.Request("GET", "https://example.invalid/metadata", extensions={extension: "private-canary"})
    with pytest.raises(OAuthError, match="extension"):
        guard_http_request(request, authorize=allowed)


async def test_guard_is_immutable_single_use_and_checks_the_actual_wire_destination():
    import httpcore2

    from henchman.mcp.http_guard import guard_http_request

    request = httpx2.Request("POST", "https://example.invalid/token")
    checked, dispatched = [], []
    guard_http_request(request, authorize=lambda: checked.append(True), dispatched=lambda: dispatched.append(True))
    with pytest.raises(TypeError):
        request.extensions["trace"] = lambda *_: None
    trace = request.extensions["trace"]
    core = httpcore2.Request("POST", "https://example.invalid/token")
    await trace("http11.send_request_headers.started", {"request": core})
    assert len(checked) == 2 and dispatched == [True]
    with pytest.raises(OAuthError, match="replay"):
        await trace("http11.send_request_headers.started", {"request": core})
    assert dispatched == [True]
    other = httpx2.Request("POST", "https://example.invalid/token")
    guard_http_request(other, authorize=allowed)
    with pytest.raises(OAuthError, match="destination"):
        await other.extensions["trace"]("http11.send_request_headers.started", {"request": httpcore2.Request("POST", "https://example.invalid/outside")})


@pytest.mark.parametrize("phase", ["code", "refresh"])
async def test_transport_failure_after_dispatch_boundary_retains_uncertain_claim(tmp_path, trusted_tls, monkeypatch, phase):
    from httpcore2._async.http11 import AsyncHTTP11Connection

    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        manager, _settings = runtime(tmp_path, native_config(peer))
        if phase == "refresh":
            await manager.oauth_login("fixture", authorize=allowed, browser_opener=browser)
        original = AsyncHTTP11Connection._send_request_headers
        attempts = []

        async def fail_header_write(connection, request):
            if request.url.target == b"/token":
                attempts.append(True)
                raise ConnectionResetError("private-header-write-canary")
            return await original(connection, request)

        monkeypatch.setattr(AsyncHTTP11Connection, "_send_request_headers", fail_header_write)
        with pytest.raises(OAuthError) as caught:
            if phase == "refresh":
                await manager.oauth_refresh("fixture", authorize=allowed)
            else:
                await manager.oauth_login("fixture", authorize=allowed, browser_opener=browser)
        await settled(peer)
        assert attempts == [True]
        assert "canary" not in "".join(traceback.format_exception(caught.value))
        expected = "refresh_started" if phase == "refresh" else "login_started"
        assert manager._oauth_runtime._store.status("fixture").state == expected
        assert len(peer.token_forms) == (1 if phase == "refresh" else 0)
        before = peer.application_bytes
        with pytest.raises(OAuthError):
            await manager.oauth_refresh("fixture", authorize=allowed)
        assert peer.application_bytes == before
        await manager.disconnect_all()


@pytest.mark.parametrize("phase", ["code", "refresh"])
async def test_token_expiry_origin_is_captured_at_dispatch_after_tls_wait(tmp_path, trusted_tls, monkeypatch, phase):
    from henchman.mcp.oauth_flow import login_oauth, refresh_oauth
    from henchman.mcp.oauth_store import OAuthCredentialStore
    from henchman.utils.evidence_redaction import EvidenceRedactor
    from tests.mcp.test_oauth_discovery import binding
    from tests.mcp.test_oauth_flow import login

    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        service, evidence, authority = ((await login(peer, tmp_path)) if phase == "refresh"
                                       else (OAuthCredentialStore(tmp_path, clock=lambda: 250), EvidenceRedactor(), None))
        service._clock = lambda: 250
        clock = [100]
        gate = TLSGate(monkeypatch, "/token")
        operation = asyncio.create_task(refresh_oauth(service, authority, authorize=allowed, evidence=evidence, clock=lambda: clock[0])
            if phase == "refresh" else login_oauth(binding(peer), service, authorize=allowed, evidence=evidence,
                                                    browser_opener=browser, clock=lambda: clock[0]))
        try:
            await asyncio.wait_for(gate.entered.wait(), 2)
            clock[0] = 250
            gate.release.set()
            result = await asyncio.wait_for(operation, 3)
            credentials = service.credentials(result)
            assert credentials.issued_at == 250 and credentials.expires_at == 550
        finally:
            gate.release.set()
            operation.cancel()
            await asyncio.gather(operation, return_exceptions=True)


@pytest.mark.parametrize("package", ["httpx2", "httpcore2"])
@pytest.mark.parametrize("phase", ["code", "refresh"])
async def test_unknown_http_profile_cannot_consume_a_claim_or_send_http(tmp_path, trusted_tls, monkeypatch, package, phase):
    from henchman.mcp import http_guard

    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        manager, _settings = runtime(tmp_path, native_config(peer))
        if phase == "refresh":
            await manager.oauth_login("fixture", authorize=allowed, browser_opener=browser)
        before = peer.application_bytes
        status = manager._oauth_runtime._store.status("fixture")
        original = http_guard.version
        monkeypatch.setattr(http_guard, "version", lambda name: "0.0.0" if name == package else original(name))
        with pytest.raises(OAuthError, match="runtime profile"):
            if phase == "refresh":
                await manager.oauth_refresh("fixture", authorize=allowed)
            else:
                await manager.oauth_login("fixture", authorize=allowed, browser_opener=browser)
        assert peer.application_bytes == before and manager._oauth_runtime._store.status("fixture") == status
