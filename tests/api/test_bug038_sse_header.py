"""Test for BUG-038: SSE endpoint missing X-Accel-Buffering header.

The fix: add X-Accel-Buffering: no to the StreamingResponse headers so that
nginx (and other proxies) pass SSE chunks through immediately instead of buffering.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from henchman.core.events import AgentEvent, EventType


def _make_agent() -> MagicMock:
    """Create a mock agent."""
    agent = MagicMock()
    agent.messages = []
    agent.system_prompt = ""
    return agent


def test_stream_response_has_x_accel_buffering_header() -> None:
    """Stream response should include X-Accel-Buffering: no header."""
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
            response = client.post(
                "/v1/chat/completions/stream",
                json={"messages": [{"role": "user", "content": "hi"}]},
            )

    assert response.status_code == 200
    assert response.headers.get("x-accel-buffering") == "no", (
        f"Expected X-Accel-Buffering: no but got: {response.headers.get('x-accel-buffering')}"
    )


def test_stream_response_still_has_standard_headers() -> None:
    """Stream response should still include standard SSE headers."""
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
            response = client.post(
                "/v1/chat/completions/stream",
                json={"messages": [{"role": "user", "content": "hi"}]},
            )

    assert "text/event-stream" in response.headers["content-type"]
    assert "no-cache" in response.headers.get("cache-control", "")
