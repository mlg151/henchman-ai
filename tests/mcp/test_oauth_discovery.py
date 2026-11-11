"""Bounded OAuth discovery against an independently implemented TLS peer."""

import asyncio
import logging
import traceback

import pytest

from henchman.config.schema import McpServerConfig
from henchman.mcp import oauth
from henchman.mcp.oauth import OAuthBinding, OAuthError, discover_oauth
from tests.mcp.oauth_fixture import OAuthPeer
from tests.mcp.test_http_transport import tls_contexts as fixture_tls_contexts

tls_contexts = fixture_tls_contexts


@pytest.fixture
def trusted_tls(request, monkeypatch):
    contexts = request.getfixturevalue("tls_contexts")
    original = oauth.httpx2.AsyncClient

    def create(**kwargs):
        assert kwargs["trust_env"] is False
        assert kwargs["follow_redirects"] is False
        assert "auth" not in kwargs
        return original(**kwargs, verify=contexts[1])

    monkeypatch.setattr(oauth.httpx2, "AsyncClient", create)
    return contexts[0]


def binding(peer, **overrides):
    return OAuthBinding.from_config("fixture", McpServerConfig(transport="streamable_http", url=peer.endpoint,
                                      oauth={"issuer": peer.issuer, "client_id": "public-client", **overrides}))


async def test_native_discovery_is_credential_free_detached_and_does_not_dispatch_rpc(trusted_tls, caplog):
    caplog.set_level(logging.DEBUG)
    async with OAuthPeer(trusted_tls) as peer:
        peer.routes[peer.resource_path][2]["Set-Cookie"] = "private-cookie-canary=present"
        guards = []
        result = await discover_oauth(binding(peer), authorize=lambda: guards.append(True), challenge='Bearer scope="write read"')
        assert result.scopes == ("write", "read")
        assert result.token_endpoint == peer.origin + "/token"
        assert result.authorization_response_iss_required
        assert len(guards) == 4  # Before handoff and after TLS for each document.
        assert [request[0] for request in peer.requests] == ["GET", "GET"]
        assert all("authorization" not in headers and "cookie" not in headers for _, _, headers in peer.requests)
        peer.metadata["token_endpoint"] = "https://changed.example/token"
        assert result.token_endpoint == peer.origin + "/token"
        assert peer.origin not in caplog.text and "private-cookie-canary" not in caplog.text


async def test_metadata_header_bound_counts_wire_bytes_not_decoded_characters(trusted_tls):
    async with OAuthPeer(trusted_tls) as peer:
        peer.routes[peer.resource_path][2]["X-Large"] = "é" * (oauth.OAUTH_HEADER_BYTES // 2 + 1)
        with pytest.raises(OAuthError, match="headers exceed"):
            await discover_oauth(binding(peer), authorize=lambda: None)
        assert len(peer.requests) == 1


@pytest.mark.parametrize("mutation", ["resource", "issuer", "pkce", "response_types", "auth_methods", "malformed_pkce", "token_origin"])
async def test_invalid_metadata_refuses_profile_without_token_or_authorize_request(trusted_tls, mutation):
    async with OAuthPeer(trusted_tls) as peer:
        if mutation == "resource":
            peer.resource["resource"] += "/other-private-canary"
        elif mutation == "issuer":
            peer.metadata["issuer"] += "/private-canary"
        elif mutation == "pkce":
            peer.metadata.pop("code_challenge_methods_supported")
        elif mutation == "response_types":
            peer.metadata.pop("response_types_supported")
        elif mutation == "auth_methods":
            peer.metadata.pop("token_endpoint_auth_methods_supported")
        elif mutation == "malformed_pkce":
            peer.metadata["code_challenge_methods_supported"] = ["S256", {}]
        else:
            peer.metadata["token_endpoint"] = "https://unapproved.example/private-canary"
        with pytest.raises(OAuthError) as caught:
            await discover_oauth(binding(peer), authorize=lambda: None)
        assert "private-canary" not in "".join(traceback.format_exception(caught.value))
        assert all(path.startswith("/.well-known/") for _, path, _ in peer.requests)


async def test_path_and_oidc_fallbacks_are_ordered_and_guarded(trusted_tls):
    async with OAuthPeer(trusted_tls) as peer:
        peer.routes.pop(peer.resource_path)
        peer.routes["/.well-known/oauth-protected-resource"] = (200, peer.resource, {}, 0)
        peer.routes.pop(peer.issuer_path)
        peer.routes["/issuer/.well-known/openid-configuration"] = (200, peer.metadata, {}, 0)
        await discover_oauth(binding(peer), authorize=lambda: None)
        assert [path for _, path, _ in peer.requests] == [peer.resource_path, "/.well-known/oauth-protected-resource",
            peer.issuer_path, "/.well-known/openid-configuration/issuer", "/issuer/.well-known/openid-configuration"]


async def test_unapproved_challenge_does_not_contact_any_destination(trusted_tls):
    async with OAuthPeer(trusted_tls) as peer:
        with pytest.raises(OAuthError):
            await discover_oauth(binding(peer), authorize=lambda: None,
                                 challenge='Bearer resource_metadata="https://unapproved.example/private-canary"')
        assert peer.requests == []


@pytest.mark.parametrize("status", [302, 401, 429, 500])
async def test_rejected_metadata_does_not_redirect_or_fallback(trusted_tls, status):
    async with OAuthPeer(trusted_tls) as peer:
        peer.routes[peer.resource_path] = (status, {}, {"Location": "https://unapproved.example/private-canary"}, 0)
        with pytest.raises(OAuthError):
            await discover_oauth(binding(peer), authorize=lambda: None)
        assert len(peer.requests) == 1


@pytest.mark.parametrize("body", [b'{"issuer":"private-canary","issuer":"duplicate"}', b'{"ignored":1e999}', b"{" + b" " * 65536])
async def test_malformed_or_oversized_json_is_value_free(trusted_tls, body):
    async with OAuthPeer(trusted_tls) as peer:
        peer.routes[peer.issuer_path] = (200, body, {}, 0)
        with pytest.raises(OAuthError) as caught:
            await discover_oauth(binding(peer), authorize=lambda: None)
        assert "private-canary" not in "".join(traceback.format_exception(caught.value))


def test_json_rejects_nonfinite_numbers_even_in_unknown_metadata_fields():
    with pytest.raises(OAuthError):
        oauth.bounded_oauth_json(b'{"ignored":1e999}')


@pytest.mark.parametrize("header", ['Bearer scope="x",scope="y"', 'Bearer scope=""', 'Bearer scope="read",',
                                   'Bearer resource_metadata=""', 'Bearer realm="x"\r\nprivate-canary'])
def test_ambiguous_challenge_rejected_without_values(header):
    with pytest.raises(OAuthError) as caught:
        oauth.parse_oauth_challenge(header)
    assert "private-canary" not in str(caught.value)


async def test_revoked_policy_between_discovery_hops_prevents_next_request(trusted_tls):
    async with OAuthPeer(trusted_tls) as peer:
        def guard():
            if peer.requests:
                raise PermissionError("private-policy-canary")

        with pytest.raises(OAuthError) as caught:
            await discover_oauth(binding(peer), authorize=guard)
        assert len(peer.requests) == 1
        assert "private-policy-canary" not in "".join(traceback.format_exception(caught.value))


async def test_whole_discovery_deadline_bounds_individually_fast_fallbacks(trusted_tls, monkeypatch):
    monkeypatch.setattr(oauth, "OAUTH_DISCOVERY_TIMEOUT", .08)
    monkeypatch.setattr(oauth, "OAUTH_REQUEST_TIMEOUT", 1)
    async with OAuthPeer(trusted_tls) as peer:
        peer.routes[peer.resource_path] = (404, {}, {}, .05)
        peer.routes["/.well-known/oauth-protected-resource"] = (200, peer.resource, {}, .05)
        with pytest.raises(OAuthError, match="deadline"):
            await asyncio.wait_for(discover_oauth(binding(peer), authorize=lambda: None), 1)
        assert len(peer.requests) <= 2


async def test_cancellation_propagates_and_closes_owned_http_request(trusted_tls):
    async with OAuthPeer(trusted_tls) as peer:
        peer.routes[peer.resource_path] = (200, peer.resource, {}, 10)
        task = asyncio.create_task(discover_oauth(binding(peer), authorize=lambda: None))
        async with asyncio.timeout(1):
            while not peer.requests:
                await asyncio.sleep(.005)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 1)


@pytest.mark.parametrize("managed", [False, True])
async def test_configured_oauth_cannot_silently_use_unauthenticated_transport(trusted_tls, managed):
    from henchman.mcp.client import McpClient
    from henchman.mcp.manager import McpManager

    async with OAuthPeer(trusted_tls) as peer:
        config = McpServerConfig(transport="streamable_http", url=peer.endpoint,
                                oauth={"issuer": peer.issuer, "client_id": "public"})
        target = McpManager({"fixture": config}) if managed else McpClient("fixture", config)
        try:
            with pytest.raises(RuntimeError, match="OAuth.*not yet"):
                if managed:
                    await target.connect_server("fixture")
                else:
                    await target.connect()
            assert peer.requests == []
        finally:
            if managed:
                await target.disconnect_all()
            else:
                await target.disconnect()


def test_manager_config_identity_detaches_nested_oauth_controls():
    from henchman.mcp.manager import McpManager
    from tests.mcp.test_oauth_foundation import configuration

    config = configuration()
    before = McpManager._config_identity(config)
    config.oauth.client_id = "changed"
    assert McpManager._config_identity(config) != before


async def test_separate_resource_and_issuer_authorities_are_explicitly_bound(trusted_tls):
    async with OAuthPeer(trusted_tls) as resource, OAuthPeer(trusted_tls) as issuer:
        resource.resource["authorization_servers"] = [issuer.issuer]
        result = await discover_oauth(binding(resource, issuer=issuer.issuer), authorize=lambda: None)
        assert result.binding.resource == resource.endpoint
        assert result.binding.issuer == issuer.issuer
        assert result.token_endpoint == issuer.origin + "/token"
        assert [path for _, path, _ in resource.requests] == [resource.resource_path]
        assert [path for _, path, _ in issuer.requests] == [issuer.issuer_path]


async def test_raw_issuer_equality_does_not_normalize_trailing_slash(trusted_tls):
    async with OAuthPeer(trusted_tls) as peer:
        peer.resource["authorization_servers"] = [peer.issuer + "/"]
        with pytest.raises(OAuthError, match="issuer"):
            await discover_oauth(binding(peer, issuer=peer.issuer + "/"), authorize=lambda: None)
        assert len(peer.requests) == 2


async def test_request_deadline_precedes_whole_discovery_deadline(trusted_tls, monkeypatch):
    monkeypatch.setattr(oauth, "OAUTH_REQUEST_TIMEOUT", .03)
    monkeypatch.setattr(oauth, "OAUTH_DISCOVERY_TIMEOUT", 5)
    async with OAuthPeer(trusted_tls) as peer:
        peer.routes[peer.resource_path] = (200, peer.resource, {}, 10)
        with pytest.raises(OAuthError, match="deadline"):
            await asyncio.wait_for(discover_oauth(binding(peer), authorize=lambda: None), 1)
        assert len(peer.requests) == 1
