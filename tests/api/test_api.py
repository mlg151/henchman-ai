"""Comprehensive tests for henchman.api modules.

Covers auth, state, health, chat endpoints, and server configuration.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from henchman.api.auth import verify_api_key
from henchman.api.endpoints.health import HealthResponse, MetricsResponse, UsageResponse
from henchman.api.state import State
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import Message

# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


def _make_app_with_state(
    agent: Any = None,
    settings: Any = None,
    api_keys: set[str] | None = None,
    metrics: dict | None = None,
) -> tuple[Any, Any]:
    """Create a FastAPI TestClient with controlled state.

    Args:
        agent: Mock agent to use in state.
        settings: Mock settings to use in state.
        api_keys: Set of valid API keys.
        metrics: Metrics dict override.

    Returns:
        Tuple of (TestClient, State).
    """
    from henchman.api.server import app

    test_state = State()
    test_state.agent = agent
    test_state.settings = settings
    if api_keys is not None:
        test_state.api_keys = api_keys
    if metrics is not None:
        test_state.metrics = metrics

    return app, test_state


def _make_settings(require_auth: bool = False) -> Any:
    """Create a mock settings object.

    Args:
        require_auth: Whether authentication is required.

    Returns:
        Mock settings object.
    """
    settings = MagicMock()
    settings.api.require_auth = require_auth
    settings.providers.default = "deepseek"
    return settings


def _make_agent() -> MagicMock:
    """Create a mock agent.

    Returns:
        Mock agent object.
    """
    agent = MagicMock()
    agent.messages = []
    agent.system_prompt = ""
    agent.get_messages_for_api.return_value = []
    return agent


# ---------------------------------------------------------------------------
# State tests
# ---------------------------------------------------------------------------


class TestState:
    """Tests for the State class."""

    def test_default_state(self) -> None:
        """Test State initializes with correct defaults."""
        s = State()
        assert s.settings is None
        assert s.provider_registry is None
        assert s.agent is None
        assert s.api_keys == set()
        assert isinstance(s.metrics, dict)

    def test_metrics_keys(self) -> None:
        """Test State metrics contains all expected keys."""
        s = State()
        expected_keys = [
            "requests_total",
            "requests_successful",
            "requests_failed",
            "tokens_prompt",
            "tokens_completion",
            "tokens_total",
            "tool_calls_total",
            "tool_calls_successful",
            "tool_calls_failed",
        ]
        for key in expected_keys:
            assert key in s.metrics
            assert s.metrics[key] == 0

    def test_metrics_initial_values(self) -> None:
        """Test State metrics start at zero."""
        s = State()
        assert all(v == 0 for v in s.metrics.values())


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


class TestVerifyApiKey:
    """Tests for verify_api_key function."""

    @pytest.mark.anyio
    async def test_no_settings_allows_access(self) -> None:
        """When no settings, authentication is not required."""
        with patch("henchman.api.auth.state") as mock_state:
            mock_state.settings = None
            result = await verify_api_key("any_key")
        assert result is True

    @pytest.mark.anyio
    async def test_no_api_attr_allows_access(self) -> None:
        """When settings has no api attribute, authentication is not required."""
        with patch("henchman.api.auth.state") as mock_state:
            settings = MagicMock(spec=[])  # spec=[] means no attributes
            mock_state.settings = settings
            result = await verify_api_key("key")
        assert result is True

    @pytest.mark.anyio
    async def test_auth_disabled_allows_any_key(self) -> None:
        """When require_auth is False, any key (or no key) is accepted."""
        with patch("henchman.api.auth.state") as mock_state:
            mock_state.settings = _make_settings(require_auth=False)
            result = await verify_api_key(None)
        assert result is True

    @pytest.mark.anyio
    async def test_auth_enabled_no_key_denied(self) -> None:
        """When auth is required but no key provided, returns False."""
        with patch("henchman.api.auth.state") as mock_state:
            mock_state.settings = _make_settings(require_auth=True)
            mock_state.api_keys = {"valid-key"}
            result = await verify_api_key(None)
        assert result is False

    @pytest.mark.anyio
    async def test_auth_enabled_valid_key_accepted(self) -> None:
        """When auth is required and valid key provided, returns True."""
        with patch("henchman.api.auth.state") as mock_state:
            mock_state.settings = _make_settings(require_auth=True)
            mock_state.api_keys = {"secret-key"}
            result = await verify_api_key("secret-key")
        assert result is True

    @pytest.mark.anyio
    async def test_auth_enabled_invalid_key_denied(self) -> None:
        """When auth is required and wrong key provided, returns False."""
        with patch("henchman.api.auth.state") as mock_state:
            mock_state.settings = _make_settings(require_auth=True)
            mock_state.api_keys = {"secret-key"}
            result = await verify_api_key("wrong-key")
        assert result is False


# ---------------------------------------------------------------------------
# Health endpoint tests
# ---------------------------------------------------------------------------


class TestHealthEndpoints:
    """Tests for /v1/health, /v1/metrics, /v1/usage endpoints."""

    @pytest.fixture(autouse=True)
    def patch_state(self) -> Any:
        """Patch global state for health tests."""
        with patch("henchman.api.endpoints.health.state") as mock_state:
            mock_state.settings = _make_settings()
            mock_state.agent = _make_agent()
            mock_state.metrics = {
                "requests_total": 10,
                "requests_successful": 8,
                "requests_failed": 2,
                "tokens_prompt": 1000,
                "tokens_completion": 500,
                "tokens_total": 1500,
                "tool_calls_total": 5,
                "tool_calls_successful": 4,
                "tool_calls_failed": 1,
            }
            yield mock_state

    def test_health_ok(self, patch_state: Any) -> None:
        """Health endpoint returns ok status."""
        from henchman.api.server import app

        with TestClient(app, raise_server_exceptions=True) as client:
            with patch("henchman.api.endpoints.health.state", patch_state):
                response = client.get("/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.3.11"

    def test_health_no_settings(self, patch_state: Any) -> None:
        """Health endpoint when settings is None."""
        patch_state.settings = None
        patch_state.agent = None

        from henchman.api.server import app

        with TestClient(app) as client:
            with patch("henchman.api.endpoints.health.state", patch_state):
                response = client.get("/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["provider"] is None
        assert data["agent_ready"] is False

    def test_metrics_with_data(self, patch_state: Any) -> None:
        """Metrics endpoint returns actual metrics from state."""
        from henchman.api.server import app

        with TestClient(app) as client:
            with patch("henchman.api.endpoints.health.state", patch_state):
                response = client.get("/v1/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["requests"]["total"] == 10
        assert data["requests"]["successful"] == 8
        assert data["requests"]["failed"] == 2
        assert data["tokens"]["prompt"] == 1000
        assert data["tools"]["total_calls"] == 5

    def test_metrics_no_metrics(self, patch_state: Any) -> None:
        """Metrics endpoint returns zeros when state.metrics is empty."""
        patch_state.metrics = {}

        from henchman.api.server import app

        with TestClient(app) as client:
            with patch("henchman.api.endpoints.health.state", patch_state):
                response = client.get("/v1/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["requests"]["total"] == 0

    def test_usage_with_tokens(self, patch_state: Any) -> None:
        """Usage endpoint calculates cost from token metrics."""
        from henchman.api.server import app

        with TestClient(app) as client:
            with patch("henchman.api.endpoints.health.state", patch_state):
                response = client.get("/v1/usage")
        assert response.status_code == 200
        data = response.json()
        assert data["total_tokens"] == 1500
        assert data["total_cost"] > 0
        assert "current_session" in data["daily_usage"]

    def test_usage_no_metrics(self, patch_state: Any) -> None:
        """Usage endpoint returns zeros when state.metrics is empty."""
        patch_state.metrics = {}

        from henchman.api.server import app

        with TestClient(app) as client:
            with patch("henchman.api.endpoints.health.state", patch_state):
                response = client.get("/v1/usage")
        assert response.status_code == 200
        data = response.json()
        assert data["total_tokens"] == 0
        assert data["total_cost"] == 0.0
        assert data["daily_usage"] == {}

    def test_health_response_model(self) -> None:
        """HealthResponse model has expected defaults."""
        h = HealthResponse()
        assert h.status == "ok"
        assert h.version == "0.3.11"
        assert h.provider is None
        assert h.agent_ready is False

    def test_metrics_response_model(self) -> None:
        """MetricsResponse model has expected defaults."""
        m = MetricsResponse()
        assert m.requests == {}
        assert m.tokens == {}
        assert m.tools == {}

    def test_usage_response_model(self) -> None:
        """UsageResponse model has expected defaults."""
        u = UsageResponse()
        assert u.total_tokens == 0
        assert u.total_cost == 0.0
        assert u.daily_usage == {}


# ---------------------------------------------------------------------------
# Chat endpoint tests - helper functions
# ---------------------------------------------------------------------------


class TestChatHelpers:
    """Tests for chat endpoint helper functions."""

    def test_convert_chat_message_basic(self) -> None:
        """Convert basic chat message to internal format."""
        from henchman.api.endpoints.chat import ChatMessage, _convert_chat_message_to_internal

        msg = ChatMessage(role="user", content="Hello")
        internal = _convert_chat_message_to_internal(msg)
        assert internal.role == "user"
        assert internal.content == "Hello"
        assert internal.tool_calls is None

    def test_convert_chat_message_with_tool_calls(self) -> None:
        """Convert chat message with tool calls to internal format."""
        from henchman.api.endpoints.chat import ChatMessage, _convert_chat_message_to_internal

        msg = ChatMessage(
            role="assistant",
            content="",
            tool_calls=[{"id": "tc1", "name": "read_file", "arguments": {"path": "/f.py"}}],
        )
        internal = _convert_chat_message_to_internal(msg)
        assert internal.tool_calls is not None
        assert len(internal.tool_calls) == 1
        assert internal.tool_calls[0].id == "tc1"
        assert internal.tool_calls[0].name == "read_file"

    def test_convert_chat_message_with_tool_call_id(self) -> None:
        """Convert tool response message to internal format."""
        from henchman.api.endpoints.chat import ChatMessage, _convert_chat_message_to_internal

        msg = ChatMessage(role="tool", content="result", tool_call_id="tc1")
        internal = _convert_chat_message_to_internal(msg)
        assert internal.tool_call_id == "tc1"

    def test_setup_agent_history(self) -> None:
        """Setup agent history excludes the last user message."""
        from henchman.api.endpoints.chat import ChatMessage, _setup_agent_history

        agent = MagicMock()
        mock_messages = MagicMock()
        agent.messages = mock_messages
        messages = [
            ChatMessage(role="user", content="First"),
            ChatMessage(role="assistant", content="Response"),
            ChatMessage(role="user", content="Second"),
        ]
        _setup_agent_history(agent, messages, last_user_index=2)
        # Should have called clear() and appended first 2 messages
        mock_messages.clear.assert_called_once()

    def test_process_agent_event_content(self) -> None:
        """Process content event appends to content_parts."""
        from henchman.api.endpoints.chat import _process_agent_event

        event = AgentEvent(type=EventType.CONTENT, data="Hello", source_agent="agent")
        content_parts: list[str] = []
        tool_calls: list[dict] = []
        finish_reason, usage = _process_agent_event(
            event, content_parts, tool_calls, {"stop", "tool_calls", "length", "content_filter"}
        )
        assert finish_reason is None
        assert usage is None
        assert content_parts == ["Hello"]

    def test_process_agent_event_tool_call(self) -> None:
        """Process tool_call event appends to tool_calls."""
        from henchman.api.endpoints.chat import _process_agent_event

        tc_data = {"id": "tc1", "name": "shell", "arguments": {}}
        event = AgentEvent(type=EventType.TOOL_CALL_REQUEST, data=tc_data, source_agent="agent")
        content_parts: list[str] = []
        tool_calls: list[dict] = []
        finish_reason, usage = _process_agent_event(
            event, content_parts, tool_calls, {"stop"}
        )
        assert finish_reason is None
        assert tool_calls == [tc_data]

    def test_process_agent_event_finished_string(self) -> None:
        """Process FINISHED event with string data returns finish_reason."""
        from henchman.api.endpoints.chat import _process_agent_event

        event = AgentEvent(type=EventType.FINISHED, data="stop", source_agent="agent")
        content_parts: list[str] = []
        tool_calls: list[dict] = []
        finish_reason, usage = _process_agent_event(
            event, content_parts, tool_calls, {"stop"}
        )
        assert finish_reason == "stop"
        assert usage is None

    def test_process_agent_event_finished_dict(self) -> None:
        """Process FINISHED event with dict data returns finish_reason and usage."""
        from henchman.api.endpoints.chat import _process_agent_event

        usage_data = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        event = AgentEvent(
            type=EventType.FINISHED,
            data={"finish_reason": "stop", "usage": usage_data},
            source_agent="agent",
        )
        content_parts: list[str] = []
        tool_calls: list[dict] = []
        finish_reason, usage = _process_agent_event(
            event, content_parts, tool_calls, {"stop"}
        )
        assert finish_reason == "stop"
        assert usage == usage_data

    def test_process_agent_event_finished_invalid_reason(self) -> None:
        """Process FINISHED event with invalid reason returns None."""
        from henchman.api.endpoints.chat import _process_agent_event

        event = AgentEvent(type=EventType.FINISHED, data="invalid", source_agent="agent")
        content_parts: list[str] = []
        tool_calls: list[dict] = []
        finish_reason, usage = _process_agent_event(
            event, content_parts, tool_calls, {"stop"}
        )
        assert finish_reason is None

    def test_process_agent_event_finished_dict_invalid_reason(self) -> None:
        """Process FINISHED event with dict but invalid finish_reason returns None."""
        from henchman.api.endpoints.chat import _process_agent_event

        event = AgentEvent(
            type=EventType.FINISHED,
            data={"finish_reason": "invalid", "usage": {}},
            source_agent="agent",
        )
        content_parts: list[str] = []
        tool_calls: list[dict] = []
        finish_reason, usage = _process_agent_event(
            event, content_parts, tool_calls, {"stop"}
        )
        assert finish_reason is None

    def test_update_metrics_no_state_metrics(self) -> None:
        """Update metrics does nothing when state.metrics is falsy."""
        from henchman.api.endpoints.chat import _update_metrics

        with patch("henchman.api.endpoints.chat.state") as mock_state:
            mock_state.metrics = {}
            # Should not raise
            _update_metrics(None, [])

    def test_update_metrics_with_usage(self) -> None:
        """Update metrics increments token counters."""
        from henchman.api.endpoints.chat import _update_metrics

        metrics: dict = {
            "requests_total": 0,
            "requests_successful": 0,
            "tokens_prompt": 0,
            "tokens_completion": 0,
            "tokens_total": 0,
            "tool_calls_total": 0,
            "tool_calls_successful": 0,
        }
        with patch("henchman.api.endpoints.chat.state") as mock_state:
            mock_state.metrics = metrics
            usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
            _update_metrics(usage, [])

        assert metrics["tokens_prompt"] == 10
        assert metrics["tokens_completion"] == 5
        assert metrics["tokens_total"] == 15
        assert metrics["requests_successful"] == 1

    def test_update_metrics_with_tool_calls(self) -> None:
        """Update metrics increments tool call counters."""
        from henchman.api.endpoints.chat import _update_metrics

        metrics: dict = {
            "requests_total": 0,
            "requests_successful": 0,
            "tool_calls_total": 0,
            "tool_calls_successful": 0,
        }
        with patch("henchman.api.endpoints.chat.state") as mock_state:
            mock_state.metrics = metrics
            _update_metrics(None, [{"id": "tc1"}, {"id": "tc2"}])

        assert metrics["tool_calls_total"] == 2
        assert metrics["tool_calls_successful"] == 2

    def test_process_stream_event_content(self) -> None:
        """Process stream event for content type."""
        from henchman.api.endpoints.chat import _process_stream_event

        event = AgentEvent(type=EventType.CONTENT, data="Hello", source_agent="agent")
        chunk_type, chunk_data, new_index, tool_count = _process_stream_event(event, 0, 0)
        assert chunk_type == "content"
        assert chunk_data == {"text": "Hello"}
        assert new_index == 1
        assert tool_count == 0

    def test_process_stream_event_tool_call(self) -> None:
        """Process stream event for tool call type."""
        from henchman.api.endpoints.chat import _process_stream_event

        tc = {"id": "tc1", "name": "shell"}
        event = AgentEvent(type=EventType.TOOL_CALL_REQUEST, data=tc, source_agent="agent")
        chunk_type, chunk_data, new_index, tool_count = _process_stream_event(event, 0, 0)
        assert chunk_type == "tool_call"
        assert chunk_data == {"tool_call": tc}
        assert tool_count == 1

    def test_process_stream_event_finished(self) -> None:
        """Process stream event for finished type."""
        from henchman.api.endpoints.chat import _process_stream_event

        event = AgentEvent(type=EventType.FINISHED, data="stop", source_agent="agent")
        chunk_type, chunk_data, new_index, tool_count = _process_stream_event(event, 0, 0)
        assert chunk_type == "finished"
        assert chunk_data == {"reason": "stop"}

    def test_process_stream_event_finished_with_usage(self) -> None:
        """Process stream event for finished type with usage data updates metrics."""
        from henchman.api.endpoints.chat import _process_stream_event

        metrics: dict = {"tokens_prompt": 0, "tokens_completion": 0, "tokens_total": 0}
        usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        event = AgentEvent(
            type=EventType.FINISHED,
            data={"finish_reason": "stop", "usage": usage},
            source_agent="agent",
        )
        with patch("henchman.api.endpoints.chat.state") as mock_state:
            mock_state.metrics = metrics
            chunk_type, chunk_data, _, _ = _process_stream_event(event, 0, 0)
        assert chunk_type == "finished"
        assert metrics["tokens_prompt"] == 10

    def test_update_stream_metrics(self) -> None:
        """Update stream metrics increments successful requests."""
        from henchman.api.endpoints.chat import _update_stream_metrics

        metrics: dict = {
            "requests_successful": 0,
            "tool_calls_total": 0,
            "tool_calls_successful": 0,
        }
        with patch("henchman.api.endpoints.chat.state") as mock_state:
            mock_state.metrics = metrics
            _update_stream_metrics(tool_calls_count=3)

        assert metrics["requests_successful"] == 1
        assert metrics["tool_calls_total"] == 3
        assert metrics["tool_calls_successful"] == 3

    def test_update_stream_metrics_no_tools(self) -> None:
        """Update stream metrics with no tool calls."""
        from henchman.api.endpoints.chat import _update_stream_metrics

        metrics: dict = {"requests_successful": 0}
        with patch("henchman.api.endpoints.chat.state") as mock_state:
            mock_state.metrics = metrics
            _update_stream_metrics(tool_calls_count=0)

        assert metrics["requests_successful"] == 1
        assert "tool_calls_total" not in metrics

    def test_update_stream_metrics_no_state(self) -> None:
        """Update stream metrics does nothing when state.metrics is falsy."""
        from henchman.api.endpoints.chat import _update_stream_metrics

        with patch("henchman.api.endpoints.chat.state") as mock_state:
            mock_state.metrics = {}
            # Should not raise
            _update_stream_metrics(tool_calls_count=0)

    def test_handle_stream_error(self) -> None:
        """Handle stream error returns SSE error chunk."""
        from henchman.api.endpoints.chat import _handle_stream_error

        metrics: dict = {"requests_failed": 0}
        with patch("henchman.api.endpoints.chat.state") as mock_state:
            mock_state.metrics = metrics
            result = _handle_stream_error(ValueError("oops"), index=5)

        assert result.startswith("data: ")
        payload = json.loads(result[6:])
        assert payload["type"] == "error"
        assert "oops" in payload["data"]["error"]
        assert metrics["requests_failed"] == 1

    def test_handle_stream_error_no_metrics(self) -> None:
        """Handle stream error when state.metrics is None."""
        from henchman.api.endpoints.chat import _handle_stream_error

        with patch("henchman.api.endpoints.chat.state") as mock_state:
            mock_state.metrics = None
            # Should not raise
            result = _handle_stream_error(RuntimeError("fail"), index=0)

        assert "error" in result


# ---------------------------------------------------------------------------
# Chat endpoint - get_agent dependency
# ---------------------------------------------------------------------------


class TestGetAgent:
    """Tests for the get_agent dependency function."""

    @pytest.mark.anyio
    async def test_get_agent_returns_agent(self) -> None:
        """get_agent returns agent when state.agent is set."""
        from henchman.api.endpoints.chat import get_agent

        mock_agent = _make_agent()
        with patch("henchman.api.endpoints.chat.state") as mock_state:
            mock_state.agent = mock_agent
            result = await get_agent()
        assert result is mock_agent

    @pytest.mark.anyio
    async def test_get_agent_raises_when_none(self) -> None:
        """get_agent raises HTTPException when state.agent is None."""
        from fastapi import HTTPException

        from henchman.api.endpoints.chat import get_agent

        with patch("henchman.api.endpoints.chat.state") as mock_state:
            mock_state.agent = None
            with pytest.raises(HTTPException) as exc_info:
                await get_agent()
        assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# Chat completion endpoint tests (via TestClient)
# ---------------------------------------------------------------------------


class TestChatCompletion:
    """Integration tests for /v1/chat/completions endpoint."""

    @pytest.fixture
    def mock_agent_with_events(self) -> MagicMock:
        """Create mock agent that yields events on run()."""
        agent = _make_agent()

        async def _run(user_input: str):  # noqa: ARG001
            yield AgentEvent(type=EventType.CONTENT, data="Hello!", source_agent="agent")
            yield AgentEvent(type=EventType.FINISHED, data="stop", source_agent="agent")

        agent.run = _run
        return agent

    @pytest.fixture
    def client_with_agent(self, mock_agent_with_events: MagicMock) -> TestClient:
        """Create TestClient with mock agent in state."""
        from henchman.api.server import app

        return TestClient(app)

    def test_chat_completion_success(self, mock_agent_with_events: MagicMock) -> None:
        """Chat completion returns response when agent produces content."""
        from henchman.api.server import app

        with (
            patch("henchman.api.endpoints.chat.state") as mock_state,
            patch("henchman.api.auth.state") as auth_state,
        ):
            mock_state.agent = mock_agent_with_events
            mock_state.metrics = {
                "requests_total": 0,
                "requests_successful": 0,
                "tool_calls_total": 0,
                "tool_calls_successful": 0,
            }
            auth_state.settings = None

            with TestClient(app) as client:
                response = client.post(
                    "/v1/chat/completions",
                    json={
                        "messages": [{"role": "user", "content": "Hi"}],
                        "stream": False,
                    },
                )

        assert response.status_code == 200
        data = response.json()
        assert data["message"]["role"] == "assistant"
        assert data["message"]["content"] == "Hello!"

    def test_chat_completion_with_system_prompt(self, mock_agent_with_events: MagicMock) -> None:
        """Chat completion sets system_prompt on agent when provided."""
        from henchman.api.server import app

        with (
            patch("henchman.api.endpoints.chat.state") as mock_state,
            patch("henchman.api.auth.state") as auth_state,
        ):
            mock_state.agent = mock_agent_with_events
            mock_state.metrics = {}
            auth_state.settings = None

            with TestClient(app) as client:
                response = client.post(
                    "/v1/chat/completions",
                    json={
                        "messages": [{"role": "user", "content": "Hi"}],
                        "system_prompt": "Be helpful",
                    },
                )

        assert response.status_code == 200
        assert mock_agent_with_events.system_prompt == "Be helpful"

    def test_chat_completion_no_user_message(self, mock_agent_with_events: MagicMock) -> None:
        """Chat completion handles conversation with no user messages."""
        from henchman.api.server import app

        with (
            patch("henchman.api.endpoints.chat.state") as mock_state,
            patch("henchman.api.auth.state") as auth_state,
        ):
            mock_state.agent = mock_agent_with_events
            mock_state.metrics = {}
            auth_state.settings = None

            with TestClient(app) as client:
                response = client.post(
                    "/v1/chat/completions",
                    json={
                        "messages": [{"role": "system", "content": "You are helpful"}],
                    },
                )

        assert response.status_code == 200

    def test_chat_completion_agent_error(self) -> None:
        """Chat completion returns 500 when agent raises exception."""
        from henchman.api.server import app

        agent = _make_agent()

        async def _failing_run(user_input: str):  # noqa: ARG001
            raise RuntimeError("agent exploded")
            yield  # make it an async generator

        agent.run = _failing_run

        with (
            patch("henchman.api.endpoints.chat.state") as mock_state,
            patch("henchman.api.auth.state") as auth_state,
        ):
            mock_state.agent = agent
            mock_state.metrics = {}
            auth_state.settings = None

            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.post(
                    "/v1/chat/completions",
                    json={"messages": [{"role": "user", "content": "crash"}]},
                )

        assert response.status_code == 500

    def test_chat_completion_unauthorized(self) -> None:
        """Chat completion returns 401 when API key is invalid."""
        from henchman.api.server import app

        agent = _make_agent()

        with (
            patch("henchman.api.endpoints.chat.state") as mock_state,
            patch("henchman.api.auth.state") as auth_state,
        ):
            mock_state.agent = agent
            mock_state.metrics = {}
            auth_state.settings = _make_settings(require_auth=True)
            auth_state.api_keys = {"good-key"}

            with TestClient(app) as client:
                response = client.post(
                    "/v1/chat/completions",
                    headers={"X-API-Key": "bad-key"},
                    json={"messages": [{"role": "user", "content": "hi"}]},
                )

        assert response.status_code == 401

    def test_chat_completion_with_usage_in_finished(
        self, mock_agent_with_events: MagicMock
    ) -> None:
        """Chat completion captures usage from FINISHED event dict."""
        from henchman.api.server import app

        agent = _make_agent()

        async def _run(user_input: str):  # noqa: ARG001
            yield AgentEvent(type=EventType.CONTENT, data="Hi", source_agent="agent")
            yield AgentEvent(
                type=EventType.FINISHED,
                data={"finish_reason": "stop", "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}},
                source_agent="agent",
            )

        agent.run = _run
        metrics: dict = {
            "requests_total": 0,
            "requests_successful": 0,
            "tokens_prompt": 0,
            "tokens_completion": 0,
            "tokens_total": 0,
            "tool_calls_total": 0,
            "tool_calls_successful": 0,
        }

        with (
            patch("henchman.api.endpoints.chat.state") as mock_state,
            patch("henchman.api.auth.state") as auth_state,
        ):
            mock_state.agent = agent
            mock_state.metrics = metrics
            auth_state.settings = None

            with TestClient(app) as client:
                response = client.post(
                    "/v1/chat/completions",
                    json={"messages": [{"role": "user", "content": "hi"}]},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["usage"] == {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}

    def test_chat_completion_with_tool_calls_in_response(self) -> None:
        """Chat completion includes tool calls in response message."""
        from henchman.api.server import app

        agent = _make_agent()
        tc_data = {"id": "tc1", "name": "shell", "arguments": {"cmd": "ls"}}

        async def _run(user_input: str):  # noqa: ARG001
            yield AgentEvent(type=EventType.TOOL_CALL_REQUEST, data=tc_data, source_agent="agent")
            yield AgentEvent(type=EventType.FINISHED, data="stop", source_agent="agent")

        agent.run = _run

        with (
            patch("henchman.api.endpoints.chat.state") as mock_state,
            patch("henchman.api.auth.state") as auth_state,
        ):
            mock_state.agent = agent
            mock_state.metrics = {
                "requests_total": 0,
                "requests_successful": 0,
                "tool_calls_total": 0,
                "tool_calls_successful": 0,
            }
            auth_state.settings = None

            with TestClient(app) as client:
                response = client.post(
                    "/v1/chat/completions",
                    json={"messages": [{"role": "user", "content": "do something"}]},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["message"]["tool_calls"] == [tc_data]

    def test_chat_completion_agent_unavailable(self) -> None:
        """Chat completion returns 503 when agent is None."""
        from henchman.api.server import app

        with (
            patch("henchman.api.endpoints.chat.state") as mock_state,
            patch("henchman.api.auth.state") as auth_state,
        ):
            mock_state.agent = None
            mock_state.metrics = {}
            auth_state.settings = None

            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.post(
                    "/v1/chat/completions",
                    json={"messages": [{"role": "user", "content": "hi"}]},
                )

        assert response.status_code == 503


# ---------------------------------------------------------------------------
# Chat streaming tests
# ---------------------------------------------------------------------------


class TestChatStream:
    """Tests for /v1/chat/completions/stream endpoint."""

    def test_stream_response_content_type(self) -> None:
        """Stream endpoint returns text/event-stream content type."""
        from henchman.api.server import app

        agent = _make_agent()

        async def _run(user_input: str):  # noqa: ARG001
            yield AgentEvent(type=EventType.CONTENT, data="Hi", source_agent="agent")
            yield AgentEvent(type=EventType.FINISHED, data="stop", source_agent="agent")

        agent.run = _run

        with (
            patch("henchman.api.endpoints.chat.state") as mock_state,
            patch("henchman.api.auth.state") as auth_state,
        ):
            mock_state.agent = agent
            mock_state.metrics = {"requests_total": 0, "requests_successful": 0}
            auth_state.settings = None

            with TestClient(app) as client:
                response = client.post(
                    "/v1/chat/completions/stream",
                    json={"messages": [{"role": "user", "content": "hi"}]},
                )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

    def test_stream_response_events(self) -> None:
        """Stream endpoint yields SSE events."""
        from henchman.api.server import app

        agent = _make_agent()

        async def _run(user_input: str):  # noqa: ARG001
            yield AgentEvent(type=EventType.CONTENT, data="chunk1", source_agent="agent")
            yield AgentEvent(type=EventType.FINISHED, data="stop", source_agent="agent")

        agent.run = _run

        with (
            patch("henchman.api.endpoints.chat.state") as mock_state,
            patch("henchman.api.auth.state") as auth_state,
        ):
            mock_state.agent = agent
            mock_state.metrics = {"requests_total": 0, "requests_successful": 0}
            auth_state.settings = None

            with TestClient(app) as client:
                response = client.post(
                    "/v1/chat/completions/stream",
                    json={"messages": [{"role": "user", "content": "hi"}]},
                )

        lines = [l for l in response.text.split("\n") if l.startswith("data: ")]
        assert len(lines) >= 2  # at least content + done

    def test_stream_with_system_prompt(self) -> None:
        """Stream endpoint sets system prompt on agent."""
        from henchman.api.server import app

        agent = _make_agent()

        async def _run(user_input: str):  # noqa: ARG001
            yield AgentEvent(type=EventType.FINISHED, data="stop", source_agent="agent")

        agent.run = _run

        with (
            patch("henchman.api.endpoints.chat.state") as mock_state,
            patch("henchman.api.auth.state") as auth_state,
        ):
            mock_state.agent = agent
            mock_state.metrics = {"requests_total": 0, "requests_successful": 0}
            auth_state.settings = None

            with TestClient(app) as client:
                client.post(
                    "/v1/chat/completions/stream",
                    json={
                        "messages": [{"role": "user", "content": "hi"}],
                        "system_prompt": "Be terse",
                    },
                )

        assert agent.system_prompt == "Be terse"

    def test_stream_unauthorized(self) -> None:
        """Stream endpoint returns 401 when API key is invalid."""
        from henchman.api.server import app

        agent = _make_agent()

        with (
            patch("henchman.api.endpoints.chat.state") as mock_state,
            patch("henchman.api.auth.state") as auth_state,
        ):
            mock_state.agent = agent
            mock_state.metrics = {}
            auth_state.settings = _make_settings(require_auth=True)
            auth_state.api_keys = {"good-key"}

            with TestClient(app) as client:
                response = client.post(
                    "/v1/chat/completions/stream",
                    headers={"X-API-Key": "bad-key"},
                    json={"messages": [{"role": "user", "content": "hi"}]},
                )

        assert response.status_code == 401

    def test_stream_agent_unavailable(self) -> None:
        """Stream endpoint returns 503 when agent is None."""
        from henchman.api.server import app

        with (
            patch("henchman.api.endpoints.chat.state") as mock_state,
            patch("henchman.api.auth.state") as auth_state,
        ):
            mock_state.agent = None
            mock_state.metrics = {}
            auth_state.settings = None

            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.post(
                    "/v1/chat/completions/stream",
                    json={"messages": [{"role": "user", "content": "hi"}]},
                )

        assert response.status_code == 503

    def test_stream_error_handling(self) -> None:
        """Stream endpoint handles agent exceptions gracefully."""
        from henchman.api.server import app

        agent = _make_agent()

        async def _run(user_input: str):  # noqa: ARG001
            raise RuntimeError("stream failed")
            yield  # make async generator

        agent.run = _run

        with (
            patch("henchman.api.endpoints.chat.state") as mock_state,
            patch("henchman.api.auth.state") as auth_state,
        ):
            mock_state.agent = agent
            mock_state.metrics = {"requests_total": 0, "requests_failed": 0}
            auth_state.settings = None

            with TestClient(app) as client:
                response = client.post(
                    "/v1/chat/completions/stream",
                    json={"messages": [{"role": "user", "content": "boom"}]},
                )

        assert response.status_code == 200
        assert "error" in response.text

    def test_stream_with_tool_calls_increments_metrics(self) -> None:
        """Stream endpoint increments tool call metrics."""
        from henchman.api.server import app

        agent = _make_agent()
        metrics: dict = {
            "requests_total": 0,
            "requests_successful": 0,
            "tool_calls_total": 0,
            "tool_calls_successful": 0,
        }

        async def _run(user_input: str):  # noqa: ARG001
            yield AgentEvent(
                type=EventType.TOOL_CALL_REQUEST,
                data={"id": "tc1", "name": "shell"},
                source_agent="agent",
            )
            yield AgentEvent(type=EventType.FINISHED, data="stop", source_agent="agent")

        agent.run = _run

        with (
            patch("henchman.api.endpoints.chat.state") as mock_state,
            patch("henchman.api.auth.state") as auth_state,
        ):
            mock_state.agent = agent
            mock_state.metrics = metrics
            auth_state.settings = None

            with TestClient(app) as client:
                client.post(
                    "/v1/chat/completions/stream",
                    json={"messages": [{"role": "user", "content": "do work"}]},
                )

        assert metrics["tool_calls_total"] == 1


# ---------------------------------------------------------------------------
# Chat history tests
# ---------------------------------------------------------------------------


class TestChatHistory:
    """Tests for GET/DELETE /v1/chat/history."""

    def test_get_history_empty(self) -> None:
        """Get history returns empty list when no messages."""
        from henchman.api.server import app

        agent = _make_agent()
        agent.get_messages_for_api.return_value = []

        with (
            patch("henchman.api.endpoints.chat.state") as mock_state,
            patch("henchman.api.auth.state") as auth_state,
        ):
            mock_state.agent = agent
            auth_state.settings = None

            with TestClient(app) as client:
                response = client.get("/v1/chat/history")

        assert response.status_code == 200
        assert response.json() == []

    def test_get_history_with_messages(self) -> None:
        """Get history returns messages from agent."""
        from henchman.api.server import app

        agent = _make_agent()
        msg = Message(role="user", content="Hello")
        agent.get_messages_for_api.return_value = [msg]

        with (
            patch("henchman.api.endpoints.chat.state") as mock_state,
            patch("henchman.api.auth.state") as auth_state,
        ):
            mock_state.agent = agent
            auth_state.settings = None

            with TestClient(app) as client:
                response = client.get("/v1/chat/history")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["role"] == "user"
        assert data[0]["content"] == "Hello"

    def test_get_history_with_limit(self) -> None:
        """Get history respects limit query parameter."""
        from henchman.api.server import app

        agent = _make_agent()
        messages = [Message(role="user", content=f"msg{i}") for i in range(5)]
        agent.get_messages_for_api.return_value = messages

        with (
            patch("henchman.api.endpoints.chat.state") as mock_state,
            patch("henchman.api.auth.state") as auth_state,
        ):
            mock_state.agent = agent
            auth_state.settings = None

            with TestClient(app) as client:
                response = client.get("/v1/chat/history?limit=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_history_unauthorized(self) -> None:
        """Get history returns 401 when API key is invalid."""
        from henchman.api.server import app

        agent = _make_agent()

        with (
            patch("henchman.api.endpoints.chat.state") as mock_state,
            patch("henchman.api.auth.state") as auth_state,
        ):
            mock_state.agent = agent
            auth_state.settings = _make_settings(require_auth=True)
            auth_state.api_keys = {"good-key"}

            with TestClient(app) as client:
                response = client.get(
                    "/v1/chat/history",
                    headers={"X-API-Key": "bad-key"},
                )

        assert response.status_code == 401

    def test_clear_history(self) -> None:
        """Delete history clears agent messages."""
        from henchman.api.server import app

        agent = MagicMock()
        mock_messages = MagicMock()
        agent.messages = mock_messages

        with (
            patch("henchman.api.endpoints.chat.state") as mock_state,
            patch("henchman.api.auth.state") as auth_state,
        ):
            mock_state.agent = agent
            auth_state.settings = None

            with TestClient(app) as client:
                response = client.delete("/v1/chat/history")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Chat history cleared"
        mock_messages.clear.assert_called_once()

    def test_clear_history_unauthorized(self) -> None:
        """Delete history returns 401 when API key is invalid."""
        from henchman.api.server import app

        agent = _make_agent()

        with (
            patch("henchman.api.endpoints.chat.state") as mock_state,
            patch("henchman.api.auth.state") as auth_state,
        ):
            mock_state.agent = agent
            auth_state.settings = _make_settings(require_auth=True)
            auth_state.api_keys = {"good-key"}

            with TestClient(app) as client:
                response = client.delete(
                    "/v1/chat/history",
                    headers={"X-API-Key": "bad-key"},
                )

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Server tests
# ---------------------------------------------------------------------------


class TestServer:
    """Tests for server.py."""

    def test_root_endpoint(self) -> None:
        """Root endpoint returns version info."""
        from henchman.api.server import app

        with TestClient(app) as client:
            response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "0.3.11"
        assert "docs" in data

    def test_http_exception_handler(self) -> None:
        """HTTP exception handler returns JSON error response."""
        from henchman.api.server import app

        with TestClient(app, raise_server_exceptions=False) as client:
            # Trigger a 404 to exercise the exception handler
            response = client.get("/v1/nonexistent-path")

        assert response.status_code == 404

    def test_generic_exception_handler(self) -> None:
        """Generic exception handler returns 500 JSON response."""
        from fastapi import APIRouter

        from henchman.api.server import app

        # Add a route that raises an unhandled exception
        test_router = APIRouter()

        @test_router.get("/test-error")
        async def error_route() -> None:
            raise ValueError("unexpected error")

        app.include_router(test_router)

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/test-error")

        assert response.status_code == 500

    def test_get_provider_settings_unknown(self) -> None:
        """_get_provider_settings returns empty dict for unknown provider."""
        from henchman.api.server import _get_provider_settings

        settings = MagicMock()
        result = _get_provider_settings("unknown_provider", settings)
        assert result == {}

    def test_get_provider_settings_known(self) -> None:
        """_get_provider_settings returns settings for known provider."""
        from henchman.api.server import _get_provider_settings

        settings = MagicMock()
        settings.providers.deepseek = {"model": "deepseek-chat"}

        result = _get_provider_settings("deepseek", settings)
        assert result == {"model": "deepseek-chat"}

    def test_get_provider_settings_none_value(self) -> None:
        """_get_provider_settings returns empty dict when provider attr is None."""
        from henchman.api.server import _get_provider_settings

        settings = MagicMock()
        settings.providers.deepseek = None

        result = _get_provider_settings("deepseek", settings)
        assert result == {}

    def test_run_server_calls_uvicorn(self) -> None:
        """run_server calls uvicorn.run with correct parameters."""
        from henchman.api.server import run_server

        with patch("uvicorn.run") as mock_run:
            run_server(host="0.0.0.0", port=9000, reload=True, workers=2)

        mock_run.assert_called_once_with(
            "henchman.api.server:app",
            host="0.0.0.0",
            port=9000,
            reload=True,
            workers=2,
        )

    @pytest.mark.anyio
    async def test_lifespan_startup_success(self) -> None:
        """Lifespan creates agent successfully on startup."""
        from henchman.api.server import app, lifespan

        mock_settings = _make_settings()
        mock_settings.api = MagicMock()
        mock_settings.api.api_keys = ["key1", "key2"]
        mock_registry = MagicMock()
        mock_provider = MagicMock()
        mock_registry.create.return_value = mock_provider

        with (
            patch("henchman.api.server.load_settings", return_value=mock_settings),
            patch("henchman.api.server.get_default_registry", return_value=mock_registry),
            patch("henchman.api.server.Agent") as mock_agent_cls,
            patch("henchman.api.server.state") as mock_state,
        ):
            mock_state.settings = None
            mock_state.api_keys = set()
            async with lifespan(app):
                pass

    @pytest.mark.anyio
    async def test_lifespan_startup_agent_failure(self) -> None:
        """Lifespan handles agent creation failure gracefully."""
        from henchman.api.server import app, lifespan

        mock_settings = _make_settings()
        mock_settings.api = MagicMock()
        mock_settings.api.api_keys = []
        mock_registry = MagicMock()
        mock_registry.create.side_effect = RuntimeError("provider unavailable")

        with (
            patch("henchman.api.server.load_settings", return_value=mock_settings),
            patch("henchman.api.server.get_default_registry", return_value=mock_registry),
            patch("henchman.api.server.state") as mock_state,
        ):
            mock_state.settings = None
            mock_state.api_keys = set()
            async with lifespan(app):
                pass
            # Should set agent to None on failure
            assert mock_state.agent is None

    def test_chat_stream_increments_requests_total(self) -> None:
        """Streaming request increments requests_total metric."""
        from henchman.api.server import app

        agent = _make_agent()
        metrics: dict = {"requests_total": 0, "requests_successful": 0}

        async def _run(user_input: str):  # noqa: ARG001
            yield AgentEvent(type=EventType.FINISHED, data="stop", source_agent="agent")

        agent.run = _run

        with (
            patch("henchman.api.endpoints.chat.state") as mock_state,
            patch("henchman.api.auth.state") as auth_state,
        ):
            mock_state.agent = agent
            mock_state.metrics = metrics
            auth_state.settings = None

            with TestClient(app) as client:
                client.post(
                    "/v1/chat/completions/stream",
                    json={"messages": [{"role": "user", "content": "hi"}]},
                )

        assert metrics["requests_total"] == 1


class TestChatStreamBranchCoverage:
    """Additional streaming tests to cover missing branches in _handle_stream_chat."""

    def test_stream_no_user_message_exhausts_loop(self) -> None:
        """Branch [410->418]: for loop exhausts with no user messages (empty list)."""
        from henchman.api.server import app

        agent = _make_agent()
        metrics: dict = {"requests_total": 0}

        async def _run(user_input: str):  # noqa: ARG001
            yield AgentEvent(type=EventType.FINISHED, data="stop", source_agent="agent")

        agent.run = _run

        with (
            patch("henchman.api.endpoints.chat.state") as mock_state,
            patch("henchman.api.auth.state") as auth_state,
        ):
            mock_state.agent = agent
            mock_state.metrics = metrics
            auth_state.settings = None

            with TestClient(app) as client:
                # Empty messages — for loop exhausts without break [410->418]
                client.post(
                    "/v1/chat/completions/stream",
                    json={"messages": []},
                )

    def test_stream_non_user_message_continues_loop(self) -> None:
        """Branch [412->410]: if msg.role == 'user': False (assistant before user)."""
        from henchman.api.server import app

        agent = _make_agent()
        metrics: dict = {"requests_total": 0}

        async def _run(user_input: str):  # noqa: ARG001
            yield AgentEvent(type=EventType.FINISHED, data="stop", source_agent="agent")

        agent.run = _run

        with (
            patch("henchman.api.endpoints.chat.state") as mock_state,
            patch("henchman.api.auth.state") as auth_state,
        ):
            mock_state.agent = agent
            mock_state.metrics = metrics
            auth_state.settings = None

            with TestClient(app) as client:
                # [user, assistant]: iterating backwards: i=1 (assistant → False [412->410])
                # then i=0 (user → True → break)
                client.post(
                    "/v1/chat/completions/stream",
                    json={
                        "messages": [
                            {"role": "user", "content": "hello"},
                            {"role": "assistant", "content": "world"},
                        ]
                    },
                )

    def test_stream_no_metrics_skips_increment(self) -> None:
        """Branch [421->424]: if state.metrics: False (state.metrics is None)."""
        from henchman.api.server import app

        agent = _make_agent()

        async def _run(user_input: str):  # noqa: ARG001
            yield AgentEvent(type=EventType.FINISHED, data="stop", source_agent="agent")

        agent.run = _run

        with (
            patch("henchman.api.endpoints.chat.state") as mock_state,
            patch("henchman.api.auth.state") as auth_state,
        ):
            mock_state.agent = agent
            mock_state.metrics = None  # Falsy — exercises [421->424]
            auth_state.settings = None

            with TestClient(app) as client:
                client.post(
                    "/v1/chat/completions/stream",
                    json={"messages": [{"role": "user", "content": "hi"}]},
                )
