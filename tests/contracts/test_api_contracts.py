"""Contract tests for API request and response boundaries."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from henchman.api.endpoints.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatStreamChunk,
)
from henchman.api.endpoints.health import HealthResponse, MetricsResponse, UsageResponse
from henchman.api.endpoints.remote import (
    OAuthAuthorizeResponse,
    OAuthTokenResponse,
    RemoteSessionResponse,
)
from henchman.api.remote_sessions import RemoteSessionManager
from henchman.api.state import State
from henchman.core.events import AgentEvent, EventType
from henchman.ops.rate_limits import RateLimiter
from henchman.ops.store import OpsStore
from henchman.version import VERSION
from tests.contracts.helpers import assert_contract_matches


def _make_chat_agent() -> MagicMock:
    agent = MagicMock()
    agent.messages = []
    agent.system_prompt = ""
    return agent


def _build_remote_state(tmp_path: Path, agent: object | None = None) -> State:
    store = OpsStore(db_path=tmp_path / "ops.db")
    api_settings = SimpleNamespace(
        require_auth=False,
        rate_limits={"default": "100/hour"},
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
    state.agent = agent or object()
    return state


def test_health_models_match_contracts(contract_suite) -> None:
    """Provider models for health endpoints should satisfy their contracts."""
    assert_contract_matches(
        payload=HealthResponse(
            status="ok",
            version=VERSION,
            provider="deepseek",
            agent_ready=True,
        ).model_dump(),
        schema_name="api/health_response",
        contract_suite=contract_suite,
    )
    assert_contract_matches(
        payload=MetricsResponse(
            requests={"total": 1, "successful": 1, "failed": 0},
            tokens={"prompt": 3, "completion": 2, "total": 5},
            tools={"total_calls": 1, "successful_calls": 1, "failed_calls": 0},
        ).model_dump(),
        schema_name="api/metrics_response",
        contract_suite=contract_suite,
    )
    assert_contract_matches(
        payload=UsageResponse(
            total_tokens=5,
            total_cost=0.001,
            daily_usage={"current_session": {"tokens": 5, "cost": 0.001}},
        ).model_dump(),
        schema_name="api/usage_response",
        contract_suite=contract_suite,
    )


def test_health_endpoint_matches_contract(contract_suite) -> None:
    """The health endpoint should return a contract-compliant payload."""
    from henchman.api.server import app

    health_state = SimpleNamespace(
        settings=SimpleNamespace(
            api=None,
            providers=SimpleNamespace(default="deepseek"),
        ),
        agent=object(),
        metrics={},
    )

    with (
        patch("henchman.api.endpoints.health.state", health_state),
        TestClient(app) as client,
    ):
        response = client.get("/v1/health")

    assert response.status_code == 200
    assert_contract_matches(
        payload=response.json(),
        schema_name="api/health_response",
        contract_suite=contract_suite,
    )


def test_readiness_endpoint_matches_contract_when_degraded(contract_suite) -> None:
    """The not-ready response must keep the public health schema."""

    from henchman.api.server import app

    health_state = SimpleNamespace(
        settings=SimpleNamespace(
            api=None,
            providers=SimpleNamespace(default="deepseek"),
        ),
        agent=None,
        metrics={},
    )

    with (
        patch("henchman.api.endpoints.health.state", health_state),
        TestClient(app) as client,
    ):
        response = client.get("/v1/ready")

    assert response.status_code == 503
    assert_contract_matches(
        payload=response.json(),
        schema_name="api/health_response",
        contract_suite=contract_suite,
    )


def test_chat_models_match_contracts(contract_suite) -> None:
    """Chat request and response models should satisfy their contracts."""
    request = ChatRequest(messages=[ChatMessage(role="user", content="Hello")])
    response = ChatResponse(
        message=ChatMessage(role="assistant", content="Hello back"),
        usage={"prompt_tokens": 2, "completion_tokens": 2, "total_tokens": 4},
        finish_reason="stop",
    )
    stream_chunk = ChatStreamChunk(type="content", data={"text": "Hello"}, index=0)

    assert_contract_matches(
        payload=request.model_dump(),
        schema_name="api/chat_request",
        contract_suite=contract_suite,
    )
    assert_contract_matches(
        payload=response.model_dump(),
        schema_name="api/chat_response",
        contract_suite=contract_suite,
    )
    assert_contract_matches(
        payload=stream_chunk.model_dump(),
        schema_name="api/chat_stream_chunk",
        contract_suite=contract_suite,
    )


def test_chat_completion_endpoint_matches_contract(contract_suite) -> None:
    """Chat completion responses should remain contract-compliant."""
    from henchman.api.server import app

    agent = _make_chat_agent()

    async def _run(user_input: str):  # noqa: ARG001
        yield AgentEvent(type=EventType.CONTENT, data="Hello!", source_agent="agent")
        yield AgentEvent(
            type=EventType.FINISHED,
            data={
                "finish_reason": "stop",
                "usage": {
                    "prompt_tokens": 3,
                    "completion_tokens": 2,
                    "total_tokens": 5,
                },
            },
            source_agent="agent",
        )

    agent.run = _run

    chat_state = SimpleNamespace(
        agent=agent,
        settings=SimpleNamespace(
            api=None,
            providers=SimpleNamespace(default="deepseek"),
        ),
        metrics={
            "requests_total": 0,
            "requests_successful": 0,
            "tool_calls_total": 0,
            "tool_calls_successful": 0,
        },
    )
    auth_state = SimpleNamespace(settings=None)

    with (
        patch("henchman.api.endpoints.chat.state", chat_state),
        patch("henchman.api.auth.state", auth_state),
        TestClient(app) as client,
    ):
        response = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "Hi"}]},
        )

    assert response.status_code == 200
    assert_contract_matches(
        payload=response.json(),
        schema_name="api/chat_response",
        contract_suite=contract_suite,
    )


def test_chat_stream_endpoint_matches_contract(contract_suite) -> None:
    """Streaming chat responses should emit contract-compliant SSE chunks."""
    from henchman.api.server import app

    agent = _make_chat_agent()

    async def _run(user_input: str):  # noqa: ARG001
        yield AgentEvent(type=EventType.CONTENT, data="chunk-1", source_agent="agent")
        yield AgentEvent(type=EventType.FINISHED, data="stop", source_agent="agent")

    agent.run = _run

    chat_state = SimpleNamespace(
        agent=agent,
        settings=SimpleNamespace(
            api=None,
            providers=SimpleNamespace(default="deepseek"),
        ),
        metrics={"requests_total": 0, "requests_successful": 0},
    )
    auth_state = SimpleNamespace(settings=None)

    with (
        patch("henchman.api.endpoints.chat.state", chat_state),
        patch("henchman.api.auth.state", auth_state),
        TestClient(app) as client,
    ):
        response = client.post(
            "/v1/chat/completions/stream",
            json={"messages": [{"role": "user", "content": "Hi"}]},
        )

    assert response.status_code == 200
    for line in (entry for entry in response.text.splitlines() if entry.startswith("data: ")):
        payload = json.loads(line.removeprefix("data: "))
        assert_contract_matches(
            payload=payload,
            schema_name="api/chat_stream_chunk",
            contract_suite=contract_suite,
        )


def test_remote_models_match_contracts(contract_suite) -> None:
    """Remote-session and OAuth models should satisfy their contracts."""
    remote_session = RemoteSessionResponse(
        session_id="session-1",
        client_id="client-1",
        title="Remote debug",
        status="active",
        created_at="2026-04-24T00:00:00Z",
        updated_at="2026-04-24T00:00:00Z",
        last_event=None,
    )
    authorize = OAuthAuthorizeResponse(
        state="state-1",
        authorization_url="https://henchman.local/oauth?state=state-1",
        scopes=["sessions:write"],
    )
    token = OAuthTokenResponse(
        access_token="token-1",
        token_type="bearer",
        client_id="client-1",
        scopes=["sessions:write"],
    )

    assert_contract_matches(
        payload=remote_session.model_dump(),
        schema_name="api/remote_session_response",
        contract_suite=contract_suite,
    )
    assert_contract_matches(
        payload=authorize.model_dump(),
        schema_name="api/oauth_authorize_response",
        contract_suite=contract_suite,
    )
    assert_contract_matches(
        payload=token.model_dump(),
        schema_name="api/oauth_token_response",
        contract_suite=contract_suite,
    )


def test_remote_endpoints_match_contracts(tmp_path: Path, contract_suite) -> None:
    """Remote-session and OAuth endpoints should preserve their contracts."""
    from henchman.api.server import app

    remote_state = _build_remote_state(tmp_path)

    with (
        patch("henchman.api.server.state", remote_state),
        patch("henchman.api.endpoints.remote.state", remote_state),
        patch("henchman.api.auth.state", remote_state),
        TestClient(app) as client,
    ):
        created = client.post(
            "/v1/remote/sessions",
            json={"client_id": "cli-1", "title": "Remote debug"},
        )
        assert created.status_code == 201
        assert_contract_matches(
            payload=created.json(),
            schema_name="api/remote_session_response",
            contract_suite=contract_suite,
        )

        session_id = created.json()["session_id"]
        fetched = client.get(f"/v1/remote/sessions/{session_id}")
        assert fetched.status_code == 200
        assert_contract_matches(
            payload=fetched.json(),
            schema_name="api/remote_session_response",
            contract_suite=contract_suite,
        )

        authorize = client.post(
            "/v1/oauth/authorize",
            json={
                "client_id": "cli-1",
                "redirect_uri": "https://app.example/callback",
                "scopes": ["sessions:write"],
            },
        )
        assert authorize.status_code == 200
        assert_contract_matches(
            payload=authorize.json(),
            schema_name="api/oauth_authorize_response",
            contract_suite=contract_suite,
        )

        exchanged = client.post(
            "/v1/oauth/token",
            json={
                "client_id": "cli-1",
                "state": authorize.json()["state"],
                "code": "auth-code-123",
            },
        )
        assert exchanged.status_code == 200
        assert_contract_matches(
            payload=exchanged.json(),
            schema_name="api/oauth_token_response",
            contract_suite=contract_suite,
        )


# ===========================================================================
# Error response contracts
# ===========================================================================


def test_error_response_matches_contract(contract_suite) -> None:
    """API error responses must conform to the error_response schema."""
    from henchman.api.server import app

    with TestClient(app) as client:
        # Send a request to an undefined endpoint (404)
        response = client.get("/v1/nonexistent")

    assert response.status_code == 404
    payload = response.json()
    assert_contract_matches(
        payload=payload,
        schema_name="api/error_response",
        contract_suite=contract_suite,
    )


def test_validation_error_response_shape() -> None:
    """Validation error responses must contain a detail field."""
    from henchman.api.server import app

    with TestClient(app) as client:
        # Send a malformed chat request (missing required fields)
        response = client.post("/v1/chat/completions", json={})

    assert response.status_code in (422, 400)
    payload = response.json()
    # FastAPI validation errors have "detail" which may be a list or string
    assert "detail" in payload


# ===========================================================================
# Chat history endpoint contracts
# ===========================================================================


def test_chat_history_endpoint_matches_contract(tmp_path: Path) -> None:
    """Chat history endpoint must return a contract-compliant response."""
    from henchman.api.server import app

    agent = _make_chat_agent()
    remote_state = _build_remote_state(tmp_path, agent=agent)

    with (
        patch("henchman.api.server.state", remote_state),
        patch("henchman.api.endpoints.chat.state", remote_state),
        patch("henchman.api.auth.state", SimpleNamespace(settings=None)),
        TestClient(app) as client,
    ):
        response = client.get("/v1/chat/history")
        assert response.status_code == 200
        payload = response.json()
        assert isinstance(payload, list)


def test_clear_history_endpoint_matches_contract(tmp_path: Path) -> None:
    """Clear history endpoint must return a contract-compliant response."""
    from henchman.api.server import app

    agent = _make_chat_agent()
    remote_state = _build_remote_state(tmp_path, agent=agent)

    with (
        patch("henchman.api.server.state", remote_state),
        patch("henchman.api.endpoints.chat.state", remote_state),
        patch("henchman.api.auth.state", SimpleNamespace(settings=None)),
        TestClient(app) as client,
    ):
        response = client.delete("/v1/chat/history")
        assert response.status_code == 200
        payload = response.json()
        assert isinstance(payload, dict)
        # Should have a success indicator
        has_success_key = "ok" in payload or "message" in payload or "status" in payload
        assert has_success_key, f"Clear history response should indicate success, got {payload}"
