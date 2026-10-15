"""Test for BUG-037: RemoteSessionResponse.model_validate crashes on missing required fields.

The fix: make created_at and updated_at optional (str | None = None) so that
model_validate succeeds even when the stored dict doesn't have those fields.

The OpsStore.upsert_remote_session() adds timestamps, so the bug may not crash in
all environments. The fix adds defense-in-depth at the model layer.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient


def test_remote_session_response_model_without_timestamps() -> None:
    """RemoteSessionResponse.model_validate should work without created_at/updated_at."""
    from henchman.api.endpoints.remote import RemoteSessionResponse

    session = {
        "session_id": "abc123",
        "client_id": "cli-1",
        "title": "Test",
        "status": "active",
        "last_event": None,
    }

    response = RemoteSessionResponse.model_validate(session)
    assert response.session_id == "abc123"
    assert response.created_at is None
    assert response.updated_at is None


def test_remote_session_response_model_with_timestamps() -> None:
    """RemoteSessionResponse should still accept sessions with timestamps."""
    from henchman.api.endpoints.remote import RemoteSessionResponse

    session = {
        "session_id": "abc123",
        "client_id": "cli-1",
        "title": "Test",
        "status": "active",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T01:00:00Z",
        "last_event": None,
    }

    response = RemoteSessionResponse.model_validate(session)
    assert response.created_at == "2026-01-01T00:00:00Z"
    assert response.updated_at == "2026-01-01T01:00:00Z"


def test_create_remote_session_succeeds(tmp_path: Path) -> None:
    """Creating a remote session should return 201, not 500 from ValidationError."""
    from henchman.api.remote_sessions import RemoteSessionManager
    from henchman.api.server import app
    from henchman.api.state import State
    from henchman.ops.rate_limits import RateLimiter
    from henchman.ops.store import OpsStore

    store = OpsStore(db_path=tmp_path / "ops.db")
    api_settings = SimpleNamespace(
        require_auth=False,
        rate_limits={"default": "100/hour"},
        proxy={},
        oauth={"issuer": "https://henchman.local"},
    )

    test_state = State()
    test_state.settings = SimpleNamespace(
        api=api_settings,
        providers=SimpleNamespace(default="deepseek"),
    )
    test_state.remote_session_manager = RemoteSessionManager(store=store)
    test_state.oauth_service = test_state.remote_session_manager.oauth_service
    test_state.rate_limiter = RateLimiter()

    with (
        patch("henchman.api.server.state", test_state),
        patch("henchman.api.endpoints.remote.state", test_state),
        patch("henchman.api.auth.state", test_state),
        TestClient(app) as client,
    ):
        response = client.post(
            "/v1/remote/sessions",
            json={"client_id": "cli-1", "title": "My Session"},
        )

    assert response.status_code == 201, (
        f"Expected 201 but got {response.status_code}: {response.text}"
    )
    data = response.json()
    assert data["session_id"] is not None
    assert data["client_id"] == "cli-1"
    assert data["title"] == "My Session"
    assert data["status"] == "active"


def test_remote_session_crud_operations(tmp_path: Path) -> None:
    """Full CRUD operations on remote sessions should work cleanly."""
    from henchman.api.remote_sessions import RemoteSessionManager
    from henchman.api.server import app
    from henchman.api.state import State
    from henchman.ops.rate_limits import RateLimiter
    from henchman.ops.store import OpsStore

    store = OpsStore(db_path=tmp_path / "ops.db")
    api_settings = SimpleNamespace(
        require_auth=False,
        rate_limits={"default": "100/hour"},
        proxy={},
        oauth={"issuer": "https://henchman.local"},
    )

    test_state = State()
    test_state.settings = SimpleNamespace(
        api=api_settings,
        providers=SimpleNamespace(default="deepseek"),
    )
    test_state.remote_session_manager = RemoteSessionManager(store=store)
    test_state.oauth_service = test_state.remote_session_manager.oauth_service
    test_state.rate_limiter = RateLimiter()

    with (
        patch("henchman.api.server.state", test_state),
        patch("henchman.api.endpoints.remote.state", test_state),
        patch("henchman.api.auth.state", test_state),
        TestClient(app) as client,
    ):
        # Create
        created = client.post(
            "/v1/remote/sessions",
            json={"client_id": "cli-1", "title": "Test Session"},
        )
        assert created.status_code == 201
        session_id = created.json()["session_id"]

        # Get by ID
        fetched = client.get(f"/v1/remote/sessions/{session_id}")
        assert fetched.status_code == 200
        assert fetched.json()["session_id"] == session_id

        # List
        listed = client.get("/v1/remote/sessions")
        assert listed.status_code == 200
        assert len(listed.json()) == 1

        # Get non-existent
        not_found = client.get("/v1/remote/sessions/nonexistent")
        assert not_found.status_code == 404
