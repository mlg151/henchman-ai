"""Completion surfaces must preserve unsuccessful and unknown outcomes."""

from unittest.mock import MagicMock

import pytest

from henchman.cli.stream_event_handlers import _handle_agent_completed
from henchman.cli.textual_bridge import EventBridge
from henchman.cli.textual_messages import AgentStatusMessage
from henchman.core.events import AgentEvent, EventType


@pytest.mark.parametrize(
    ("status", "channel", "description"),
    [
        ("failed", "error", "failed"),
        ("stalled", "error", "stalled"),
        ("timed_out", "warning", "hit turn limit"),
        ("no_work_done", "warning", "without making changes"),
        ("future_status", "warning", "outcome unknown"),
        (None, "warning", "outcome unknown"),
    ],
)
def test_console_does_not_claim_success_for_other_outcomes(
    status: str | None, channel: str, description: str,
) -> None:
    output = MagicMock()
    data = {"agent": "engineer", "summary": "I fixed everything"}
    if status is not None:
        data["status"] = status
    _handle_agent_completed(output, AgentEvent(type=EventType.AGENT_COMPLETED, data=data))

    output.muted.assert_not_called()
    getattr(output, channel).assert_called_once()
    assert description in getattr(output, channel).call_args.args[0]


@pytest.mark.parametrize(
    ("status", "description"),
    [
        ("failed", "failed"),
        ("stalled", "stalled"),
        ("timed_out", "hit turn limit"),
        ("no_work_done", "without making changes"),
        ("future_status", "outcome unknown"),
        (None, "outcome unknown"),
    ],
)
def test_textual_does_not_claim_success_for_other_outcomes(
    status: str | None, description: str,
) -> None:
    app = MagicMock()
    data = {"agent": "engineer", "summary": "I fixed everything"}
    if status is not None:
        data["status"] = status
    EventBridge(app)._on_agent_done(AgentEvent(type=EventType.AGENT_COMPLETED, data=data))

    app.post_message.assert_called_once()
    message = app.post_message.call_args.args[0]
    assert isinstance(message, AgentStatusMessage)
    assert description in message.status
    assert "✓" not in message.status
    assert "completed" not in message.status


def test_explicit_completion_only_claims_execution_finished() -> None:
    event = AgentEvent(
        type=EventType.AGENT_COMPLETED,
        data={"agent": "engineer", "status": "completed", "summary": "Tests passed"},
    )
    output = MagicMock()
    _handle_agent_completed(output, event)
    assert "finished execution" in output.muted.call_args.args[0]
    assert "completed work" not in output.muted.call_args.args[0]
    output.warning.assert_not_called()
    output.error.assert_not_called()

    app = MagicMock()
    EventBridge(app)._on_agent_done(event)
    assert app.post_message.call_args.args[0].status == "engineer finished execution: Tests passed"


def test_response_is_displayed_neutrally() -> None:
    event = AgentEvent(
        type=EventType.AGENT_COMPLETED,
        data={"agent": "engineer", "status": "responded", "summary": "Hello"},
    )
    output = MagicMock()
    _handle_agent_completed(output, event)
    assert "responded" in output.muted.call_args.args[0]
    output.warning.assert_not_called()
    output.error.assert_not_called()

    app = MagicMock()
    EventBridge(app)._on_agent_done(event)
    assert app.post_message.call_args.args[0].status == "engineer responded: Hello"
