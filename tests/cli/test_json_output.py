"""Tests for the JSON output renderer."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from henchman.cli.json_output import JsonOutputRenderer
from henchman.core.events import AgentEvent, EventType


class TestJsonOutputRenderer:
    """Test the JsonOutputRenderer class."""

    @pytest.fixture
    def mock_console(self) -> MagicMock:
        """Return a mock console."""
        return MagicMock()

    @pytest.fixture
    def renderer(self, mock_console: MagicMock) -> JsonOutputRenderer:
        """Return a JsonOutputRenderer instance."""
        return JsonOutputRenderer(console=mock_console)

    def test_init_default_console(self) -> None:
        """Test initialization with default console."""
        renderer = JsonOutputRenderer()
        assert renderer.console is not None

    def test_init_custom_console(self, mock_console: MagicMock) -> None:
        """Test initialization with custom console."""
        renderer = JsonOutputRenderer(console=mock_console)
        assert renderer.console is mock_console

    def test_render_content_event(
        self, renderer: JsonOutputRenderer, mock_console: MagicMock
    ) -> None:
        """Test rendering a content event."""
        event = AgentEvent(EventType.CONTENT, "Hello, world!")
        renderer.render(event)

        # Verify console.print was called with JSON
        mock_console.print.assert_called_once()
        args = mock_console.print.call_args[0]
        assert len(args) == 1
        output = json.loads(args[0])
        assert output["type"] == "content"
        assert output["data"] == "Hello, world!"

    def test_render_thought_event(
        self, renderer: JsonOutputRenderer, mock_console: MagicMock
    ) -> None:
        """Test rendering a thought event."""
        event = AgentEvent(EventType.THOUGHT, "Let me think about this...")
        renderer.render(event)

        mock_console.print.assert_called_once()
        args = mock_console.print.call_args[0]
        output = json.loads(args[0])
        assert output["type"] == "thought"
        assert output["data"] == "Let me think about this..."

    def test_render_tool_call_event(
        self, renderer: JsonOutputRenderer, mock_console: MagicMock
    ) -> None:
        """Test rendering a tool call event."""
        tool_call = {"id": "123", "name": "read_file", "arguments": {"path": "test.txt"}}
        event = AgentEvent(EventType.TOOL_CALL_REQUEST, tool_call)
        renderer.render(event)

        mock_console.print.assert_called_once()
        args = mock_console.print.call_args[0]
        output = json.loads(args[0])
        assert output["type"] == "tool_call_request"
        assert output["data"] == tool_call

    def test_render_error_event(
        self, renderer: JsonOutputRenderer, mock_console: MagicMock
    ) -> None:
        """Test rendering an error event."""
        error = {"message": "Something went wrong", "code": 500}
        event = AgentEvent(EventType.ERROR, error)
        renderer.render(event)

        mock_console.print.assert_called_once()
        args = mock_console.print.call_args[0]
        output = json.loads(args[0])
        assert output["type"] == "error"
        assert output["data"] == error

    def test_render_finished_event(
        self, renderer: JsonOutputRenderer, mock_console: MagicMock
    ) -> None:
        """Test rendering a finished event."""
        event = AgentEvent(EventType.FINISHED)
        renderer.render(event)

        mock_console.print.assert_called_once()
        args = mock_console.print.call_args[0]
        output = json.loads(args[0])
        assert output["type"] == "finished"
        assert "data" not in output  # No data for finished event

    def test_render_stream_json(
        self, renderer: JsonOutputRenderer, mock_console: MagicMock
    ) -> None:
        """Test rendering with stream_json method."""
        event = AgentEvent(EventType.CONTENT, "Streaming content")
        renderer.render_stream_json(event)

        mock_console.print.assert_called_once()
        args = mock_console.print.call_args[0]
        output = json.loads(args[0])
        assert output["type"] == "content"
        assert output["data"] == "Streaming content"

    def test_render_final_json(self, renderer: JsonOutputRenderer, mock_console: MagicMock) -> None:
        """Test rendering multiple events as final JSON."""
        events = [
            AgentEvent(EventType.CONTENT, "First"),
            AgentEvent(EventType.CONTENT, "Second"),
            AgentEvent(EventType.FINISHED),
        ]
        renderer.render_final_json(events)

        mock_console.print.assert_called_once()
        args = mock_console.print.call_args[0]
        output = json.loads(args[0])
        assert len(output) == 3
        assert output[0]["type"] == "content"
        assert output[0]["data"] == "First"
        assert output[1]["type"] == "content"
        assert output[1]["data"] == "Second"
        assert output[2]["type"] == "finished"

    def test_event_to_dict_with_object(self, renderer: JsonOutputRenderer) -> None:
        """Test converting an event with an object as data."""

        class TestObject:
            def __init__(self):
                self.name = "test"
                self.value = 42

        obj = TestObject()
        event = AgentEvent(EventType.CONTENT, obj)
        result = renderer._event_to_dict(event)

        assert result["type"] == "content"
        assert result["data"] == {"name": "test", "value": 42}

    def test_event_to_dict_with_dict(self, renderer: JsonOutputRenderer) -> None:
        """Test converting an event with a dict as data."""
        data = {"key": "value", "number": 123}
        event = AgentEvent(EventType.CONTENT, data)
        result = renderer._event_to_dict(event)

        assert result["type"] == "content"
        assert result["data"] == data

    def test_event_to_dict_with_other_data(self, renderer: JsonOutputRenderer) -> None:
        """Test converting an event with other data type."""
        event = AgentEvent(EventType.CONTENT, 123)
        result = renderer._event_to_dict(event)

        assert result["type"] == "content"
        assert result["data"] == "123"


@pytest.mark.parametrize("mode", ["render", "render_stream_json", "render_final_json"])
@pytest.mark.parametrize(
    "data",
    [
        None,
        "stop",
        {"finish_reason": "stop"},
        {"finish_reason": "error"},
        {"finish_reason": "stop", "task_verified": True},
    ],
)
def test_finished_json_does_not_claim_task_verification(mode: str, data: object) -> None:
    console = MagicMock()
    renderer = JsonOutputRenderer(console=console)
    event = AgentEvent(EventType.FINISHED, data)
    getattr(renderer, mode)([event] if mode == "render_final_json" else event)
    output = json.loads(console.print.call_args.args[0])
    if mode == "render_final_json":
        output = output[0]
    assert output["task_verified"] is False
    assert output["type"] == "finished"
    assert output.get("data") == data
    assert event.data == data


@pytest.mark.parametrize("mode", ["render", "render_stream_json", "render_final_json"])
def test_json_preserves_agent_identity_for_reused_tool_ids(mode: str) -> None:
    console = MagicMock()
    renderer = JsonOutputRenderer(console=console)
    events = [
        AgentEvent(
            event_type,
            {"id": "call-1", "name": "read_file", "path": f"{agent}.py"},
            source_agent=agent,
        )
        for event_type in (EventType.TOOL_CALL_REQUEST, EventType.TOOL_CALL_RESULT)
        for agent in ("lead/implementer", "lead/reviewer")
    ]
    events.append(
        AgentEvent(
            EventType.FINISHED,
            {"finish_reason": "stop"},
            source_agent="lead/reviewer",
        )
    )

    if mode == "render_final_json":
        renderer.render_final_json(events)
        output = json.loads(console.print.call_args.args[0])
    else:
        for event in events:
            getattr(renderer, mode)(event)
        output = [json.loads(call.args[0]) for call in console.print.call_args_list]

    assert len(output) == len(events)
    for serialized, event in zip(output, events, strict=True):
        assert serialized["source_agent"] == event.source_agent
        assert serialized["type"] == event.type.name.lower()
        assert serialized["data"] == event.data
    assert output[-1]["task_verified"] is False


@pytest.mark.parametrize("source_agent", [None, ""])
def test_json_omits_only_absent_agent_identity(source_agent: str | None) -> None:
    from henchman.cli.json_output import event_to_dict

    event = AgentEvent(EventType.CONTENT, "Hello", source_agent=source_agent)
    expected = {"type": "content", "data": "Hello"}
    if source_agent is not None:
        expected["source_agent"] = source_agent
    assert event_to_dict(event) == expected
