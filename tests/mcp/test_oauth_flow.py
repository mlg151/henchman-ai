"""One-shot OAuth flows use only owned TLS peers and an injected browser."""

# ruff: noqa: F811 -- imported fixtures are resolved by pytest parameter name.

import asyncio
import logging
import traceback
from urllib.parse import urlsplit

import httpx2
import pytest

from henchman.mcp.oauth import OAuthError
from henchman.mcp.oauth_store import OAuthCredentialStore
from henchman.utils.evidence_redaction import EvidenceRedactor
from tests.mcp.oauth_fixture import OAuthPeer
from tests.mcp.test_oauth_discovery import binding, tls_contexts, trusted_tls  # noqa: F401


async def browser(url):
    # An owned synthetic user-agent, not an actual browser/account. Redirect only
    # to the specific loopback callback emitted by this independently implemented AS.
    async with httpx2.AsyncClient(trust_env=False, follow_redirects=False) as client:
        response = await client.get(url)
        assert response.status_code == 302
        callback = response.headers["location"]
        assert urlsplit(callback).hostname in {"127.0.0.1", "::1"}
        result = await client.get(callback)
        assert "canary" not in result.text


async def login(peer, tmp_path, *, opener=browser, authorize=lambda: None):
    from henchman.mcp.oauth_flow import login_oauth

    peer.enable_oauth()
    store = OAuthCredentialStore(tmp_path, clock=lambda: 100)
    evidence = EvidenceRedactor()
    authority = await login_oauth(binding(peer), store, authorize=authorize, browser_opener=opener,
                                  evidence=evidence, clock=lambda: 100)
    return store, evidence, authority


async def test_native_pkce_login_dispatches_one_code_exchange_and_projects_all_tokens(tmp_path, trusted_tls, caplog):
    caplog.set_level(logging.DEBUG)
    async with OAuthPeer(trusted_tls) as peer:
        service, evidence, authority = await login(peer, tmp_path)
        assert len(peer.token_forms) == 1
        assert peer.token_forms[0]["grant_type"] == "authorization_code"
        assert service.credentials(authority).access_token == "issued-access-private-canary"
        assert service.status("fixture").expires_at == 400
        assert evidence.text("issued-access-private-canary issued-refresh-private-canary") == "[REDACTED] [REDACTED]"
        for form in peer.token_forms:
            assert evidence.text(form["code"]) == "[REDACTED]"
            assert evidence.text(form["code_verifier"]) == "[REDACTED]"
        assert "canary" not in caplog.text and peer.origin not in caplog.text
        assert all(record.exc_info is None for record in caplog.records)
    assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("henchman-oauth-callback")]


@pytest.mark.parametrize("expiry,expected", [(None, None), (0, 100)])
async def test_missing_expiry_is_distinct_from_zero(tmp_path, trusted_tls, expiry, expected):
    async with OAuthPeer(trusted_tls) as peer:
        if expiry is None:
            peer.token_response.pop("expires_in")
        else:
            peer.token_response["expires_in"] = expiry
        service, _policy, authority = await login(peer, tmp_path)
        assert service.status("fixture").expires_at == expected
        assert (service.credentials(authority) is None) == (expiry == 0)


@pytest.mark.parametrize("rotation", [False, True])
async def test_explicit_refresh_uses_persisted_endpoint_and_preserves_omitted_fields(tmp_path, trusted_tls, rotation):
    from henchman.mcp.oauth_flow import refresh_oauth

    async with OAuthPeer(trusted_tls) as peer:
        service, evidence, authority = await login(peer, tmp_path)
        payload = {"access_token": "refreshed-access-private-canary", "token_type": "Bearer", "expires_in": 200}
        if rotation:
            payload["refresh_token"] = "rotated-refresh-private-canary"
        peer.routes["/token"] = (200, payload, {}, 0)
        before = len(peer.requests)
        updated = await refresh_oauth(service, authority, authorize=lambda: None, evidence=evidence, clock=lambda: 100)
        assert len(peer.requests) == before + 1
        assert len(peer.token_forms) == 2
        assert peer.token_forms[-1]["refresh_token"] == "issued-refresh-private-canary"
        assert service.credentials(updated).scopes == ("read",)
        assert service.credentials(updated).refresh_token == ("rotated-refresh-private-canary" if rotation else "issued-refresh-private-canary")
        assert evidence.text("issued-access-private-canary refreshed-access-private-canary") == "[REDACTED] [REDACTED]"


@pytest.mark.parametrize("status", [302, 400, 401, 403, 500])
async def test_token_failure_never_redirects_reauthenticates_or_retries(tmp_path, trusted_tls, status):
    from henchman.mcp.oauth_flow import login_oauth

    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        peer.routes["/token"] = (status, {"access_token": "failed-reply-private-canary", "error_description": "withheld-private-canary"},
                                 {"Location": "https://unapproved.example"}, 0)
        service, evidence = OAuthCredentialStore(tmp_path), EvidenceRedactor()
        with pytest.raises(OAuthError) as caught:
            await login_oauth(binding(peer), service, authorize=lambda: None, browser_opener=browser, evidence=evidence)
        assert len(peer.token_forms) == 1
        assert service.status("fixture").state == "login_started"
        assert evidence.text("failed-reply-private-canary") == "[REDACTED]"
        assert "canary" not in "".join(traceback.format_exception(caught.value))


async def test_ambiguous_refresh_disconnect_keeps_claim_unavailable(tmp_path, trusted_tls):
    from henchman.mcp.oauth_flow import refresh_oauth

    async with OAuthPeer(trusted_tls) as peer:
        service, evidence, authority = await login(peer, tmp_path)
        peer.token_disconnect = True
        with pytest.raises(OAuthError):
            await refresh_oauth(service, authority, authorize=lambda: None, evidence=evidence)
        assert len(peer.token_forms) == 2
        assert service.status("fixture").state == "refresh_started"


async def test_logout_during_browser_wait_prevents_token_exchange(tmp_path, trusted_tls):
    from henchman.mcp.oauth_flow import login_oauth

    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        service = OAuthCredentialStore(tmp_path)

        async def revoked_browser(url):
            service.logout("fixture")
            await browser(url)

        with pytest.raises(OAuthError):
            await login_oauth(binding(peer), service, authorize=lambda: None, browser_opener=revoked_browser,
                              evidence=EvidenceRedactor())
        assert peer.token_forms == []
        assert service.status("fixture").state == "revoked"


@pytest.mark.parametrize("phase", ["browser", "token"])
async def test_cancelled_flow_settles_callback_and_preserves_postdispatch_uncertainty(tmp_path, trusted_tls, phase):
    from henchman.mcp.oauth_flow import login_oauth

    entered = asyncio.Event()
    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        service = OAuthCredentialStore(tmp_path)

        async def opener(url):
            if phase == "browser":
                entered.set()
                await asyncio.Event().wait()
            else:
                await browser(url)

        peer.routes["/token"] = (200, peer.token_response, {}, 10)
        owner = asyncio.create_task(login_oauth(binding(peer), service, authorize=lambda: None,
                                                browser_opener=opener, evidence=EvidenceRedactor()))
        async with asyncio.timeout(2):
            if phase == "browser":
                await entered.wait()
            else:
                while not peer.token_forms:
                    await asyncio.sleep(.005)
        owner.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(owner, 2)
        assert service.status("fixture").state == ("needs_login" if phase == "browser" else "login_started")
        assert len(peer.token_forms) == (0 if phase == "browser" else 1)
    assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("henchman-oauth-callback")]


@pytest.mark.parametrize("change", [
    {"token_type": "unknown"}, {"access_token": ""}, {"refresh_token": None},
    {"expires_in": None}, {"expires_in": True}, {"expires_in": -1},
    {"expires_in": 1.5}, {"expires_in": 2**31}, {"scope": ["read"]},
])
async def test_malformed_token_reply_registers_values_before_value_free_failure(tmp_path, trusted_tls, change):
    from henchman.mcp.oauth_flow import login_oauth

    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        payload = {**peer.token_response, **change}
        peer.routes["/token"] = (200, payload, {}, 0)
        service, evidence = OAuthCredentialStore(tmp_path), EvidenceRedactor()
        with pytest.raises(OAuthError) as caught:
            await login_oauth(binding(peer), service, authorize=lambda: None, browser_opener=browser, evidence=evidence)
        for name in ("access_token", "refresh_token"):
            if payload.get(name):
                assert evidence.text(payload[name]) == "[REDACTED]"
        assert len(peer.token_forms) == 1
        assert service.status("fixture").state == "login_started"
        assert "canary" not in "".join(traceback.format_exception(caught.value))


@pytest.mark.parametrize("kind", ["oversize", "duplicate", "encoding", "headers", "utf8_headers"])
async def test_token_reply_boundaries_never_publish_credentials(tmp_path, trusted_tls, kind):
    from henchman.mcp import oauth_flow

    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        payload, headers = peer.token_response, {"Access-Token": "header-token-private-canary"}
        if kind == "oversize":
            payload = b" " * (oauth_flow.OAUTH_DOCUMENT_BYTES + 1)
        elif kind == "duplicate":
            payload = b'{"access_token":"first-private-canary","access_token":"second-private-canary"}'
        elif kind == "encoding":
            headers["Content-Encoding"] = "gzip"
        elif kind == "utf8_headers":
            headers["X-Large"] = "é" * (oauth_flow.OAUTH_HEADER_BYTES // 2 + 1)
        else:
            headers["X-Large"] = "x" * (oauth_flow.OAUTH_HEADER_BYTES + 1)
        peer.routes["/token"] = (200, payload, headers, 0)
        service, evidence = OAuthCredentialStore(tmp_path), EvidenceRedactor()
        with pytest.raises(OAuthError) as caught:
            await oauth_flow.login_oauth(binding(peer), service, authorize=lambda: None,
                                         browser_opener=browser, evidence=evidence)
        assert len(peer.token_forms) == 1
        assert service.status("fixture").state == "login_started"
        assert evidence.text("header-token-private-canary") == "[REDACTED]"
        assert "canary" not in "".join(traceback.format_exception(caught.value))


@pytest.mark.parametrize("phase", ["browser", "token"])
async def test_flow_deadline_settles_listener_and_retains_only_dispatched_uncertainty(tmp_path, trusted_tls, monkeypatch, phase):
    from henchman.mcp import oauth_flow

    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        service = OAuthCredentialStore(tmp_path)
        monkeypatch.setattr(oauth_flow, "OAUTH_LOGIN_TIMEOUT", 2 if phase == "browser" else 5)
        monkeypatch.setattr(oauth_flow, "OAUTH_TOKEN_TIMEOUT", .5)
        location = []

        async def opener(url):
            from urllib.parse import parse_qs

            location.append(parse_qs(urlsplit(url).query)["redirect_uri"][0])
            if phase == "browser":
                await asyncio.Event().wait()
            else:
                await browser(url)

        peer.routes["/token"] = (200, peer.token_response, {}, 10)
        with pytest.raises(OAuthError):
            await asyncio.wait_for(oauth_flow.login_oauth(binding(peer), service, authorize=lambda: None,
                                   browser_opener=opener, evidence=EvidenceRedactor()), 6)
        assert len(peer.token_forms) == (0 if phase == "browser" else 1)
        assert service.status("fixture").state == ("needs_login" if phase == "browser" else "login_started")
        target = urlsplit(location[0])
        with pytest.raises(OSError):
            await asyncio.open_connection(target.hostname, target.port)
    assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("henchman-oauth-callback")]


async def test_logout_after_token_dispatch_prevents_late_credential_publication(tmp_path, trusted_tls):
    from henchman.mcp.oauth_flow import login_oauth

    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        peer.routes["/token"] = (200, peer.token_response, {}, .05)
        service, evidence = OAuthCredentialStore(tmp_path), EvidenceRedactor()
        owner = asyncio.create_task(login_oauth(binding(peer), service, authorize=lambda: None,
                                                 browser_opener=browser, evidence=evidence))
        async with asyncio.timeout(2):
            while not peer.token_forms:
                await asyncio.sleep(.001)
        service.logout("fixture")
        with pytest.raises(OAuthError):
            await owner
        assert len(peer.token_forms) == 1
        assert service.status("fixture").state == "revoked"
        assert evidence.text(peer.token_response["access_token"]) == "[REDACTED]"


async def test_postcommit_ack_loss_preserves_ready_record_without_exchange_replay(tmp_path, trusted_tls, monkeypatch):
    from henchman.mcp.oauth_flow import login_oauth

    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        service = OAuthCredentialStore(tmp_path)
        original = service.complete

        def ack_lost(*args):
            original(*args)
            raise OSError("private-commit-canary")

        monkeypatch.setattr(service, "complete", ack_lost)
        with pytest.raises(OAuthError) as caught:
            await login_oauth(binding(peer), service, authorize=lambda: None, browser_opener=browser,
                              evidence=EvidenceRedactor())
        assert service.status("fixture").state == "ready"
        assert len(peer.token_forms) == 1
        assert "private-commit-canary" not in "".join(traceback.format_exception(caught.value))


async def test_changed_runtime_policy_after_callback_prevents_exchange(tmp_path, trusted_tls):
    from henchman.mcp.oauth_flow import login_oauth

    async with OAuthPeer(trusted_tls) as peer:
        peer.enable_oauth()
        service = OAuthCredentialStore(tmp_path)
        allowed = True

        def guard():
            if not allowed:
                raise RuntimeError("private-policy-canary")

        async def opener(url):
            nonlocal allowed
            await browser(url)
            allowed = False

        with pytest.raises(OAuthError) as caught:
            await login_oauth(binding(peer), service, authorize=guard, browser_opener=opener, evidence=EvidenceRedactor())
        assert peer.token_forms == []
        assert service.status("fixture").state == "needs_login"
        assert "private-policy-canary" not in "".join(traceback.format_exception(caught.value))


async def test_tls_peer_teardown_retires_joined_handlers_before_done_callbacks(trusted_tls, monkeypatch):
    calls = 0

    def gather_completed(*tasks, **_kwargs):
        nonlocal calls
        calls += 1
        assert calls == 1, "fixture attempted to rejoin completed handlers without yielding"
        assert all(task.done() for task in tasks)
        result = asyncio.get_running_loop().create_future()
        result.set_result([None for _ in tasks])
        return result

    async with OAuthPeer(trusted_tls) as peer:
        done = asyncio.create_task(asyncio.sleep(0))
        await done
        peer.tasks.add(done)
        done.add_done_callback(peer.tasks.discard)
        monkeypatch.setattr(asyncio, "gather", gather_completed)
    assert not peer.tasks
