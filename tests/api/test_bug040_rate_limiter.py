"""Test for BUG-040: Rate limiter uses request.client.host — ineffective behind reverse proxy.

The fix: check X-Forwarded-For or X-Real-IP headers first, fall back to request.client.host.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from henchman.api.state import State


@contextmanager
def _client_without_lifespan(app: FastAPI) -> Iterator[TestClient]:
    """Yield a client for middleware tests without replacing their seeded state."""
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()


def _build_state(tmp_path: Path, rate_limit: str = "2/minute") -> State:
    """Create a state with rate limiter configured."""
    from henchman.api.remote_sessions import RemoteSessionManager
    from henchman.api.state import State
    from henchman.ops.rate_limits import RateLimiter
    from henchman.ops.store import OpsStore

    store = OpsStore(db_path=tmp_path / "ops.db")
    api_settings = SimpleNamespace(
        require_auth=False,
        rate_limits={"default": rate_limit},
        proxy={},
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


def test_rate_limiter_uses_x_forwarded_for(tmp_path: Path) -> None:
    """Rate limiter should use X-Forwarded-For when present."""
    from henchman.api.server import app

    test_state = _build_state(tmp_path, rate_limit="2/minute")

    with (
        patch("henchman.api.server.state", test_state),
        patch("henchman.api.endpoints.remote.state", test_state),
        patch("henchman.api.endpoints.health.state", test_state),
        patch("henchman.api.auth.state", test_state),
        _client_without_lifespan(app) as client,
    ):
        # First two requests from client-ip-1 should succeed
        resp1 = client.get("/", headers={"X-Forwarded-For": "10.0.0.1"})
        assert resp1.status_code == 200

        resp2 = client.get("/", headers={"X-Forwarded-For": "10.0.0.1"})
        assert resp2.status_code == 200

        # Third request from same client should be rate limited
        resp3 = client.get("/", headers={"X-Forwarded-For": "10.0.0.1"})
        assert resp3.status_code == 429, (
            f"Expected 429 for third request from same X-Forwarded-For IP, got {resp3.status_code}"
        )


def test_rate_limiter_different_x_forwarded_for_separate_buckets(tmp_path: Path) -> None:
    """Different X-Forwarded-For IPs should have separate rate limit buckets."""
    from henchman.api.server import app

    test_state = _build_state(tmp_path, rate_limit="2/minute")

    with (
        patch("henchman.api.server.state", test_state),
        patch("henchman.api.endpoints.remote.state", test_state),
        patch("henchman.api.endpoints.health.state", test_state),
        patch("henchman.api.auth.state", test_state),
        _client_without_lifespan(app) as client,
    ):
        # Exhaust client A's budget
        assert client.get("/", headers={"X-Forwarded-For": "10.0.0.1"}).status_code == 200
        assert client.get("/", headers={"X-Forwarded-For": "10.0.0.1"}).status_code == 200
        assert client.get("/", headers={"X-Forwarded-For": "10.0.0.1"}).status_code == 429

        # Client B should still be allowed (separate bucket)
        resp_b = client.get("/", headers={"X-Forwarded-For": "10.0.0.2"})
        assert resp_b.status_code == 200, (
            f"Expected 200 for different X-Forwarded-For IP, got {resp_b.status_code}"
        )


def test_rate_limiter_uses_x_real_ip_as_fallback(tmp_path: Path) -> None:
    """Rate limiter should use X-Real-IP when X-Forwarded-For is not present."""
    from henchman.api.server import app

    test_state = _build_state(tmp_path, rate_limit="2/minute")

    with (
        patch("henchman.api.server.state", test_state),
        patch("henchman.api.endpoints.remote.state", test_state),
        patch("henchman.api.endpoints.health.state", test_state),
        patch("henchman.api.auth.state", test_state),
        _client_without_lifespan(app) as client,
    ):
        # First two requests from real-ip-1 should succeed
        assert client.get("/", headers={"X-Real-IP": "10.0.0.1"}).status_code == 200
        assert client.get("/", headers={"X-Real-IP": "10.0.0.1"}).status_code == 200

        # Third request should be rate limited
        resp = client.get("/", headers={"X-Real-IP": "10.0.0.1"})
        assert resp.status_code == 429, (
            f"Expected 429 for third request from same X-Real-IP, got {resp.status_code}"
        )


def test_rate_limiter_uses_request_client_host_without_headers(tmp_path: Path) -> None:
    """Rate limiter falls back to request.client.host when no proxy headers are present."""
    from henchman.api.server import app

    test_state = _build_state(tmp_path, rate_limit="2/minute")

    with (
        patch("henchman.api.server.state", test_state),
        patch("henchman.api.endpoints.remote.state", test_state),
        patch("henchman.api.endpoints.health.state", test_state),
        patch("henchman.api.auth.state", test_state),
        _client_without_lifespan(app) as client,
    ):
        # No proxy headers — falls back to client.host (all requests share the FP from TestClient)
        # TestClient sends from 127.0.0.1 (testclient), so we'll get rate limited
        resp1 = client.get("/")
        assert resp1.status_code == 200

        resp2 = client.get("/")
        assert resp2.status_code == 200

        resp3 = client.get("/")
        assert resp3.status_code == 429
