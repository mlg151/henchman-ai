"""Native Streamable HTTP tests use owned loopback JSON/SSE peers only."""

from __future__ import annotations

import asyncio
import copy

import pytest

from henchman.config.schema import McpServerConfig, Settings, ToolSettings
from henchman.mcp.client import McpClient
from henchman.mcp.manager import McpManager
from tests.mcp.http_fixture import HttpPeer


def client_for(peer, **options):
    return McpClient("http-fixture", McpServerConfig(transport="streamable_http", url=peer.url, **options))


@pytest.mark.parametrize("version", ["2025-03-26", "2025-06-18", "2025-11-25", "2026-07-28"])
@pytest.mark.parametrize("mode", ["json", "sse"])
async def test_http_profiles_negotiate_call_preserve_null_and_close_without_auth(version, mode, monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("GITHUB_TOKEN", "inherited-private-canary")
    async with HttpPeer(version=version, mode=mode) as peer:
        client = client_for(peer)
        try:
            async with asyncio.timeout(5):
                await client.connect()
                assert client.protocol_version == version
                result = await client.call_tool("effect", {"region": "north"})
            assert result.content == "http executed"
            assert result.structured_content_present and result.structured_content is None
        finally:
            await client.disconnect()
        assert peer.effects == 1
        tool = next(item for item in peer.requests if item["body"].get("method") == "tools/call")
        assert tool["headers"]["mcp-protocol-version"] == version
        if version == "2026-07-28":
            assert tool["headers"]["mcp-param-region"] == "north"
            assert tool["headers"]["mcp-method"] == "tools/call"
            assert tool["headers"]["mcp-name"] == "effect"
            assert not any(item["verb"] == "DELETE" for item in peer.requests)
        else:
            assert tool["headers"]["mcp-session-id"] == "fixture-session-private"
            assert sum(item["verb"] == "DELETE" for item in peer.requests) == 1
        for request in peer.requests:
            assert request["target"] == "/mcp"
            assert not any(key in request["headers"] for key in ("authorization", "cookie", "proxy-authorization"))
            assert "inherited-private-canary" not in str(request)


@pytest.mark.parametrize("behavior", ["drop", "oversize", "stall"])
async def test_http_failure_after_dispatch_never_replays(behavior):
    async with HttpPeer() as peer:
        client = client_for(peer, request_timeout_seconds=0.15)
        try:
            await client.connect()
            peer.behavior = behavior
            async with asyncio.timeout(2):
                with pytest.raises(Exception) as error:
                    await client.call_tool("effect", {})
            assert "private" not in str(error.value)
            assert peer.effects == 1
        finally:
            await client.disconnect()


@pytest.mark.parametrize("behavior", ["unauthorized", "redirect"])
async def test_http_auth_or_redirect_does_not_follow_retry_or_discover_untrusted_destination(behavior):
    async with HttpPeer() as peer:
        peer.behavior = behavior
        client = client_for(peer)
        try:
            async with asyncio.timeout(3):
                with pytest.raises(RuntimeError) as error:
                    await client.connect()
            assert "private-auth-error-canary" not in str(error.value)
            assert "untrusted.invalid" not in str(error.value)
            assert len(peer.requests) == 1
        finally:
            await client.disconnect()


async def test_http_refuses_legacy_server_name_stdio_token_before_any_network():
    async with HttpPeer() as peer:
        manager = McpManager({"http": McpServerConfig(transport="streamable_http", url=peer.url)})
        manager.set_auth_token("http", "stdio-token-private-canary")
        try:
            with pytest.raises(RuntimeError, match="stdio"):
                await manager.connect_server("http")
            assert peer.requests == []
        finally:
            await manager.disconnect_all()


async def test_configured_network_restriction_blocks_manager_startup_before_http(tmp_path):
    async with HttpPeer() as peer:
        settings = Settings(tools=ToolSettings(network_access="disabled"), mcp_servers={
            "http": McpServerConfig(transport="streamable_http", url=peer.url),
        })
        manager = McpManager.create_from_settings(settings, project_root=tmp_path)
        assert manager is not None
        try:
            with pytest.raises(PermissionError):
                await manager.connect_server("http")
            assert peer.requests == []
        finally:
            await manager.disconnect_all()


@pytest.mark.parametrize("behavior", [
    "chunked_oversize", "sse_oversize", "sse_aggregate", "sse_drop_with_id", "compressed", "wrong_id",
])
async def test_http_untrusted_response_bounds_and_correlation_fail_without_reconnect(behavior, caplog):
    async with HttpPeer() as peer:
        client = client_for(peer)
        try:
            await client.connect()
            peer.behavior = behavior
            async with asyncio.timeout(3):
                with pytest.raises(Exception) as error:
                    await client.call_tool("effect", {})
            assert "private-" not in str(error.value)
            assert "private-" not in caplog.text
            assert peer.effects == 1
            assert not any(item["verb"] == "GET" for item in peer.requests)
        finally:
            await client.disconnect()


async def test_cancelled_http_call_aborts_owned_request_without_replay():
    async with HttpPeer() as peer:
        client = client_for(peer)
        pending = None
        try:
            await client.connect()
            peer.behavior = "stall"
            pending = asyncio.create_task(client.call_tool("effect", {}))
            async with asyncio.timeout(2):
                while peer.effects == 0:
                    await asyncio.sleep(0.01)
                pending.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await pending
                await client.disconnect()
            assert peer.effects == 1
            assert client._owner_task is None
        finally:
            if pending is not None and not pending.done():
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
            await client.disconnect()


async def test_header_maps_change_only_with_successful_complete_catalog_publication():
    from henchman.tools.contracts import SchemaContractError

    async with HttpPeer() as peer:
        client = client_for(peer)
        try:
            await client.connect()
            changed = copy.deepcopy(peer.pages[""]["tools"][0])
            changed["inputSchema"]["properties"]["region"]["x-mcp-header"] = "zone"
            peer.pages = {"": {"tools": [changed], "nextCursor": "duplicate"},
                          "duplicate": {"tools": [changed]}}
            with pytest.raises(SchemaContractError):
                await client.discover_tools()
            await client.call_tool("effect", {"region": "north"})
            first = peer.requests[-1]["headers"]
            assert first["mcp-param-region"] == "north" and "mcp-param-zone" not in first
            peer.pages = {"": {"tools": [changed]}}
            await client.discover_tools()
            await client.call_tool("effect", {"region": "south"})
            second = peer.requests[-1]["headers"]
            assert second["mcp-param-zone"] == "south" and "mcp-param-region" not in second
        finally:
            await client.disconnect()


async def test_large_projected_parameter_headers_fail_before_http_dispatch():
    async with HttpPeer() as peer:
        client = client_for(peer)
        try:
            await client.connect()
            with pytest.raises(RuntimeError, match="header"):
                await client.call_tool("effect", {"region": "x" * 10000})
            assert peer.effects == 0
            assert not any(item["body"].get("method") == "tools/call" for item in peer.requests)
        finally:
            await client.disconnect()


async def test_endpoint_change_invalidates_manager_connection_without_contacting_either_new_or_old_endpoint():
    async with HttpPeer() as first, HttpPeer() as second:
        manager = McpManager({"http": McpServerConfig(transport="streamable_http", url=first.url)})
        try:
            await manager.connect_server("http")
            client = manager.clients["http"]
            manager.configs["http"].url = second.url
            with pytest.raises(RuntimeError, match="changed"):
                await client.call_tool("effect", {})
            assert first.effects == second.effects == 0
            assert second.requests == []
        finally:
            await manager.disconnect_all()


async def test_new_runtime_network_restriction_denies_an_existing_http_connection(tmp_path):
    async with HttpPeer() as peer:
        settings = Settings(mcp_servers={"http": McpServerConfig(transport="streamable_http", url=peer.url)})
        manager = McpManager.create_from_settings(settings, project_root=tmp_path)
        assert manager is not None
        try:
            await manager.connect_server("http")
            settings.tools.network_access = "disabled"
            with pytest.raises(PermissionError):
                await manager.clients["http"].call_tool("effect", {})
            assert peer.effects == 0
            assert not manager.clients["http"].is_connected
        finally:
            await manager.disconnect_all()


async def test_inherited_registry_restriction_cannot_use_a_preconnected_http_client():
    from henchman.tools.access_policy import ToolAccessPolicy, use_access_policies

    async with HttpPeer() as peer:
        client = client_for(peer)
        try:
            await client.connect()
            with use_access_policies((ToolAccessPolicy(network_access="disabled"),)), pytest.raises(PermissionError):
                await client.call_tool("effect", {})
            assert peer.effects == 0
        finally:
            await client.disconnect()


@pytest.mark.parametrize("behavior", ["http_error_success_body", "accepted_without_result"])
async def test_http_status_cannot_be_reported_as_success(behavior):
    async with HttpPeer() as peer:
        client = client_for(peer)
        try:
            await client.connect()
            peer.behavior = behavior
            with pytest.raises(RuntimeError):
                await client.call_tool("effect", {})
            assert peer.effects == 1
        finally:
            await client.disconnect()


@pytest.mark.parametrize("behavior", ["drop", "stall", "redirect"])
async def test_legacy_http_cleanup_failure_is_explicit_bounded_and_settled(behavior, monkeypatch):
    import traceback

    from henchman.mcp import http_transport

    monkeypatch.setattr(http_transport, "HTTP_SHUTDOWN_TIMEOUT_SECONDS", 0.1)
    async with HttpPeer(version="2025-11-25") as peer:
        client = client_for(peer)
        await client.connect()
        peer.cleanup_behavior = behavior
        try:
            async with asyncio.timeout(2):
                with pytest.raises(Exception) as error:
                    await client.disconnect()
            evidence = "".join(traceback.format_exception(error.value))
            assert "cleanup" in evidence.lower()
            assert peer.url not in evidence
            assert "private-cleanup-canary" not in evidence
            assert "httpx2." not in evidence
            assert client._owner_task is None
            assert client._exit_stack is None
            assert sum(item["verb"] == "DELETE" for item in peer.requests) == 1
        finally:
            await client.disconnect()


@pytest.fixture
def tls_contexts(tmp_path):
    import ipaddress
    import ssl
    from datetime import UTC, datetime, timedelta

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "owned-loopback-fixture")])
    now = datetime.now(UTC)
    certificate = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                   .public_key(key.public_key()).serial_number(x509.random_serial_number())
                   .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=1))
                   .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
                   .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
                   .sign(key, hashes.SHA256()))
    certificate_path = tmp_path / "fixture.pem"
    key_path = tmp_path / "fixture-key.pem"
    certificate_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                          serialization.NoEncryption()))
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.load_cert_chain(certificate_path, key_path)
    trusted = ssl.create_default_context(cafile=str(certificate_path))
    assert trusted.check_hostname and trusted.verify_mode == ssl.CERT_REQUIRED
    return server, trusted


async def test_https_untrusted_certificate_fails_before_protocol_dispatch(tls_contexts, caplog):
    async with HttpPeer(ssl_context=tls_contexts[0]) as peer:
        client = client_for(peer)
        try:
            with pytest.raises(RuntimeError, match="transport failed") as error:
                await client.connect()
            assert peer.requests == []
            assert peer.url not in str(error.value)
            assert peer.url not in caplog.text
            assert client._owner_task is None
        finally:
            await client.disconnect()


async def test_https_verified_fixture_negotiates_and_calls(tls_contexts, monkeypatch):
    from henchman.mcp import http_transport

    original_client = http_transport.httpx2.AsyncClient

    def trusted_fixture_client(**kwargs):
        # Only this fixture CA is injected; hostname and certificate validation remain enabled.
        assert "verify" not in kwargs
        return original_client(**kwargs, verify=tls_contexts[1])

    monkeypatch.setattr(http_transport.httpx2, "AsyncClient", trusted_fixture_client)
    async with HttpPeer(ssl_context=tls_contexts[0]) as peer:
        client = client_for(peer)
        try:
            await client.connect()
            assert (await client.call_tool("effect", {})).content == "http executed"
            assert peer.effects == 1
        finally:
            await client.disconnect()


async def test_cleanup_rechecks_live_network_policy_before_legacy_delete(tmp_path):
    async with HttpPeer(version="2025-11-25") as peer:
        settings = Settings(mcp_servers={"http": McpServerConfig(transport="streamable_http", url=peer.url)})
        manager = McpManager.create_from_settings(settings, project_root=tmp_path)
        assert manager is not None
        await manager.connect_server("http")
        client = manager.clients["http"]
        settings.tools.network_access = "disabled"
        try:
            with pytest.raises(ExceptionGroup) as error:
                await manager.disconnect_all()
            import traceback
            assert "cleanup denied" in "".join(traceback.format_exception(error.value))
            assert not any(item["verb"] == "DELETE" for item in peer.requests)
            assert client._owner_task is None
            assert client._exit_stack is None
        finally:
            await manager.disconnect_all()


async def test_http_does_not_claim_the_obsolete_http_sse_protocol():
    async with HttpPeer(version="2024-11-05") as peer:
        client = client_for(peer)
        try:
            with pytest.raises(RuntimeError, match="Unsupported protocol"):
                await client.connect()
            assert client._owner_task is None
            assert not any(item["body"].get("method") == "tools/list" for item in peer.requests)
        finally:
            await client.disconnect()


async def test_http_debug_logs_do_not_expose_endpoint_or_session_headers(caplog):
    import logging

    caplog.set_level(logging.DEBUG)
    async with HttpPeer(version="2025-11-25") as peer:
        peer.url += "/private-endpoint-canary"
        client = client_for(peer)
        try:
            await client.connect()
            await client.call_tool("effect", {})
        finally:
            await client.disconnect()
        evidence = caplog.text + "".join(logging.Formatter().format(record) for record in caplog.records)
        assert "private-endpoint-canary" not in evidence
        assert "fixture-session-private" not in evidence
        assert "private-cookie" not in evidence
    # This policy belongs to owned MCP HTTP tasks, not unrelated application traffic.
    logging.getLogger("httpx2").info("unrelated application diagnostic")
    assert "unrelated application diagnostic" in caplog.text


async def test_http_negotiation_deadline_joins_owned_transport_without_retry():
    async with HttpPeer() as peer:
        peer.delays["server/discover"] = 1
        client = client_for(peer, negotiation_timeout_seconds=0.1)
        try:
            async with asyncio.timeout(2):
                with pytest.raises(RuntimeError, match="negotiation deadline"):
                    await client.connect()
            assert client._owner_task is None
            assert client._exit_stack is None
            assert sum(item["body"].get("method") == "server/discover" for item in peer.requests) == 1
            assert not any(item["body"].get("method") == "initialize" for item in peer.requests)
        finally:
            await client.disconnect()


async def test_http_catalog_total_deadline_retains_previous_tools_and_header_maps():
    async with HttpPeer() as peer:
        client = client_for(peer, catalog_timeout_seconds=0.1)
        try:
            await client.connect()
            before = client.get_tools()
            peer.pages = {
                "": {"tools": [{"name": "replacement", "inputSchema": {"type": "object"}}], "nextCursor": "2"},
                "2": {"tools": [], "nextCursor": "3"},
                "3": {"tools": []},
            }
            peer.delays["tools/list"] = 0.06
            async with asyncio.timeout(2):
                with pytest.raises(RuntimeError, match="catalog discovery deadline"):
                    await client.discover_tools()
            assert client.get_tools() == before
            await client.call_tool("effect", {"region": "retained"})
            assert peer.requests[-1]["headers"]["mcp-param-region"] == "retained"
        finally:
            await client.disconnect()


async def test_http_endpoint_encoding_failure_withholds_the_endpoint():
    config = McpServerConfig(transport="streamable_http", url="https://private-endpoint-canary☃.invalid/mcp")
    client = McpClient("invalid-endpoint", config)
    try:
        with pytest.raises(RuntimeError, match="endpoint") as error:
            await client.connect()
        assert "private-endpoint-canary" not in str(error.value)
        assert client._owner_task is None
    finally:
        await client.disconnect()
