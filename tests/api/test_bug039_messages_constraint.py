"""Test for BUG-039: ChatRequest.messages has no min_length constraint.

The fix: add min_length=1 to the messages Field so that empty messages arrays
are rejected with 422 Unprocessable Entity.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError


def test_chat_request_model_rejects_empty_messages() -> None:
    """ChatRequest model validation should reject empty messages list."""
    from henchman.api.endpoints.chat import ChatRequest

    with pytest.raises(ValidationError):
        ChatRequest(messages=[])


def test_chat_request_model_accepts_non_empty_messages() -> None:
    """ChatRequest model should accept messages with at least one item."""
    from henchman.api.endpoints.chat import ChatMessage, ChatRequest

    request = ChatRequest(messages=[ChatMessage(role="user", content="Hello")])
    assert len(request.messages) == 1


def test_chat_completion_with_empty_messages_returns_422() -> None:
    """Chat completion with empty messages should return 422, not silently process an empty prompt."""
    from henchman.api.server import app

    with (
        patch("henchman.api.auth.state") as auth_state,
    ):
        auth_state.settings = None

        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={"messages": []},
            )

    assert response.status_code == 422, (
        f"Expected 422 but got {response.status_code}: {response.text}"
    )


def test_chat_stream_with_empty_messages_returns_422() -> None:
    """Chat stream with empty messages should return 422."""
    from henchman.api.server import app

    with (
        patch("henchman.api.auth.state") as auth_state,
    ):
        auth_state.settings = None

        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/completions/stream",
                json={"messages": []},
            )

    assert response.status_code == 422, (
        f"Expected 422 but got {response.status_code}: {response.text}"
    )
