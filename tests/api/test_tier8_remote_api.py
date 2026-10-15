"""Tier 8 API and remote session integration tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from henchman.api.proxy import build_proxy_config
from henchman.api.remote_sessions import RemoteSessionManager
from henchman.api.state import State
from henchman.ops.rate_limits import RateLimiter
from henchman.ops.store import OpsStore


def _build_state(tmp_path: Path, *, rate_limit: str = "100/hour") -> State:
    """Create a fully wired API state for Tier 8 tests."""
    store = OpsStore(db_path=tmp_path / "ops.db")
    api_settings = SimpleNamespace(
        require_auth=False,
        rate_limits={"default": rate_limit},
        proxy={"base_url": "https://proxy.example", "headers": {"x-test": "1"}},
        oauth={"issuer": "https://henchman.local"},
    )

    state = State()
    state.settings = SimpleNamespace(
        api=api_settings, providers=SimpleNamespace(default="deepseek")
    )
    state.remote_session_manager = RemoteSessionManager(store=store)
    state.oauth_service = state.remote_session_manager.oauth_service
    state.rate_limiter = RateLimiter()
    state._rate_limits = api_settings.rate_limits  # type: ignore[attr-defined]
    return state


def test_remote_session_crud_and_websocket_echo(tmp_path: Path) -> None:
    """Remote session endpoints should persist state and stream websocket events."""
    from henchman.api.server import app

    test_state = _build_state(tmp_path)

    with (
        patch("henchman.api.server.state", test_state),
        patch("henchman.api.endpoints.remote.state", test_state),
        patch("henchman.api.auth.state", test_state),
        TestClient(app) as client,
    ):
        created = client.post(
            "/v1/remote/sessions",
            json={"client_id": "cli-1", "title": "Remote debug"},
        )
        assert created.status_code == 201
        session_id = created.json()["session_id"]

        fetched = client.get(f"/v1/remote/sessions/{session_id}")
        assert fetched.status_code == 200
        assert fetched.json()["title"] == "Remote debug"

        listed = client.get("/v1/remote/sessions")
        assert listed.status_code == 200
        assert listed.json()[0]["session_id"] == session_id

        with client.websocket_connect(f"/v1/remote/sessions/{session_id}/ws") as websocket:
            websocket.send_json({"event": "client_message", "payload": {"text": "hello"}})
            event = websocket.receive_json()

            assert event["session_id"] == session_id
            assert event["event"] == "client_message"
            assert event["payload"]["text"] == "hello"


def test_oauth_flow_and_proxy_config_round_trip(tmp_path: Path) -> None:
    """OAuth endpoints and proxy configuration should expose deterministic metadata."""
    from henchman.api.server import app

    test_state = _build_state(tmp_path)

    # Verify proxy config round-trip before TestClient lifespan modifies settings
    proxy_config = build_proxy_config(test_state.settings.api)
    assert proxy_config is not None
    assert proxy_config.base_url == "https://proxy.example"
    assert proxy_config.headers["x-test"] == "1"

    with (
        patch("henchman.api.server.state", test_state),
        patch("henchman.api.endpoints.remote.state", test_state),
        patch("henchman.api.auth.state", test_state),
        TestClient(app) as client,
    ):
        authorize = client.post(
            "/v1/oauth/authorize",
            json={
                "client_id": "cli-1",
                "redirect_uri": "https://app.example/callback",
                "scopes": ["sessions:write"],
            },
        )
        assert authorize.status_code == 200
        auth_payload = authorize.json()
        assert "state=" in auth_payload["authorization_url"]

        exchanged = client.post(
            "/v1/oauth/token",
            json={
                "client_id": "cli-1",
                "state": auth_payload["state"],
                "code": "auth-code-123",
            },
        )
        assert exchanged.status_code == 200
        token_payload = exchanged.json()
        assert token_payload["token_type"] == "bearer"
        assert token_payload["client_id"] == "cli-1"


def test_rate_limit_policy_exempts_probes_but_blocks_other_routes(tmp_path: Path) -> None:
    """Operational probes should not consume limits enforced on other routes."""
    from henchman.api.server import app

    test_state = _build_state(tmp_path, rate_limit="1/minute")
    test_state.agent = object()

    with (
        patch("henchman.api.server.state", test_state),
        patch("henchman.api.endpoints.remote.state", test_state),
        patch("henchman.api.endpoints.health.state", test_state),
        patch("henchman.api.auth.state", test_state),
    ):
        client = TestClient(app)
        try:
            assert client.get("/v1/health").status_code == 200
            assert client.get("/v1/ready").status_code == 200
            assert client.get("/").status_code == 200
            limited = client.get("/")
        finally:
            client.close()

    assert limited.status_code == 429
    assert limited.json()["code"] == "RATE_LIMIT_EXCEEDED"
