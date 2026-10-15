"""Test for BUG-036: Chat endpoints double-verify API key causing auth to always fail.

The fix: chat endpoints should use `api_key_valid: Annotated[bool, Depends(verify_api_key)]`
and check `if not api_key_valid:` directly, matching the remote.py pattern.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def _make_settings(require_auth: bool = False) -> MagicMock:
    """Create a mock settings object."""
    settings = MagicMock()
    settings.api.require_auth = require_auth
    settings.providers.default = "deepseek"
    return settings


def _make_agent() -> MagicMock:
    """Create a mock agent."""
    agent = MagicMock()
    agent.messages = []
    agent.system_prompt = ""
    agent.get_messages_for_api.return_value = []
    return agent


def test_chat_completion_with_valid_key_succeeds() -> None:
    """Chat completion with a valid API key should return 200, not 401."""
    from henchman.api.server import app

    agent = _make_agent()

    async def _run(user_input: str):  # noqa: ARG001
        yield MagicMock()
        yield MagicMock()

    # Mock the AgentEvent imports for the generator
    from henchman.core.events import AgentEvent, EventType

    async def _run_with_events(user_input: str):  # noqa: ARG001
        yield AgentEvent(type=EventType.CONTENT, data="Hello!", source_agent="agent")
        yield AgentEvent(type=EventType.FINISHED, data="stop", source_agent="agent")

    agent.run = _run_with_events

    with (
        patch("henchman.api.endpoints.chat.state") as mock_state,
        patch("henchman.api.auth.state") as auth_state,
    ):
        mock_state.agent = agent
        mock_state.metrics = {
            "requests_total": 0,
            "requests_successful": 0,
        }
        # Auth is enabled with a known good key
        auth_state.settings = _make_settings(require_auth=True)
        auth_state.api_keys = {"valid-key-123"}

        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                headers={"X-API-Key": "valid-key-123"},
                json={"messages": [{"role": "user", "content": "Hi"}]},
            )

    assert response.status_code == 200, (
        f"Expected 200 but got {response.status_code}: {response.text}"
    )


def test_chat_completion_with_invalid_key_returns_401() -> None:
    """Chat completion with an invalid API key should return 401."""
    from henchman.api.server import app

    agent = _make_agent()

    async def _run_with_events(user_input: str):  # noqa: ARG001
        yield MagicMock()
        yield MagicMock()

    from henchman.core.events import AgentEvent, EventType

    async def _run_with_events_real(user_input: str):  # noqa: ARG001
        yield AgentEvent(type=EventType.CONTENT, data="Hello!", source_agent="agent")
        yield AgentEvent(type=EventType.FINISHED, data="stop", source_agent="agent")

    agent.run = _run_with_events_real

    with (
        patch("henchman.api.endpoints.chat.state") as mock_state,
        patch("henchman.api.auth.state") as auth_state,
    ):
        mock_state.agent = agent
        mock_state.metrics = {}
        auth_state.settings = _make_settings(require_auth=True)
        auth_state.api_keys = {"valid-key-123"}

        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                headers={"X-API-Key": "wrong-key"},
                json={"messages": [{"role": "user", "content": "Hi"}]},
            )

    assert response.status_code == 401


def test_chat_stream_with_valid_key_succeeds() -> None:
    """Chat stream with a valid API key should return 200, not 401."""
    from henchman.api.server import app

    agent = _make_agent()

    from henchman.core.events import AgentEvent, EventType

    async def _run_with_events(user_input: str):  # noqa: ARG001
        yield AgentEvent(type=EventType.FINISHED, data="stop", source_agent="agent")

    agent.run = _run_with_events

    with (
        patch("henchman.api.endpoints.chat.state") as mock_state,
        patch("henchman.api.auth.state") as auth_state,
    ):
        mock_state.agent = agent
        mock_state.metrics = {"requests_total": 0, "requests_successful": 0}
        auth_state.settings = _make_settings(require_auth=True)
        auth_state.api_keys = {"valid-key-123"}

        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/completions/stream",
                headers={"X-API-Key": "valid-key-123"},
                json={"messages": [{"role": "user", "content": "Hi"}]},
            )

    assert response.status_code == 200, (
        f"Expected 200 but got {response.status_code}: {response.text}"
    )


def test_get_chat_history_with_valid_key_succeeds() -> None:
    """GET chat history with a valid API key should return 200, not 401."""
    from henchman.api.server import app

    agent = _make_agent()
    agent.get_messages_for_api.return_value = []

    with (
        patch("henchman.api.endpoints.chat.state") as mock_state,
        patch("henchman.api.auth.state") as auth_state,
    ):
        mock_state.agent = agent
        auth_state.settings = _make_settings(require_auth=True)
        auth_state.api_keys = {"valid-key-123"}

        with TestClient(app) as client:
            response = client.get(
                "/v1/chat/history",
                headers={"X-API-Key": "valid-key-123"},
            )

    assert response.status_code == 200, (
        f"Expected 200 but got {response.status_code}: {response.text}"
    )


def test_clear_chat_history_with_valid_key_succeeds() -> None:
    """DELETE chat history with a valid API key should return 200, not 401."""
    from henchman.api.server import app

    agent = MagicMock()
    mock_messages = MagicMock()
    agent.messages = mock_messages

    with (
        patch("henchman.api.endpoints.chat.state") as mock_state,
        patch("henchman.api.auth.state") as auth_state,
    ):
        mock_state.agent = agent
        auth_state.settings = _make_settings(require_auth=True)
        auth_state.api_keys = {"valid-key-123"}

        with TestClient(app) as client:
            response = client.delete(
                "/v1/chat/history",
                headers={"X-API-Key": "valid-key-123"},
            )

    assert response.status_code == 200, (
        f"Expected 200 but got {response.status_code}: {response.text}"
    )
