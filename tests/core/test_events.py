"""Tests for core event types."""

from henchman.core.events import AgentEvent, EventType


class TestEventType:
    """Tests for EventType enum."""

    def test_event_types_exist(self) -> None:
        """Test that all expected event types exist."""
        assert EventType.CONTENT is not None
        assert EventType.THOUGHT is not None
        assert EventType.TOOL_CALL_REQUEST is not None
        assert EventType.TOOL_CALL_RESULT is not None
        assert EventType.TOOL_CONFIRMATION is not None
        assert EventType.ERROR is not None
        assert EventType.FINISHED is not None

    def test_event_types_are_unique(self) -> None:
        """Test that all event types have unique values."""
        values = [e.value for e in EventType]
        assert len(values) == len(set(values))


class TestAgentEvent:
    """Tests for AgentEvent dataclass."""

    def test_content_event(self) -> None:
        """Test creating a content event."""
        event = AgentEvent(type=EventType.CONTENT, data="Hello world")
        assert event.type == EventType.CONTENT
        assert event.data == "Hello world"

    def test_thought_event(self) -> None:
        """Test creating a thought/reasoning event."""
        event = AgentEvent(type=EventType.THOUGHT, data="Let me think...")
        assert event.type == EventType.THOUGHT
        assert event.data == "Let me think..."

    def test_tool_call_request_event(self) -> None:
        """Test creating a tool call request event."""
        tool_data = {"name": "read_file", "arguments": {"path": "test.py"}}
        event = AgentEvent(type=EventType.TOOL_CALL_REQUEST, data=tool_data)
        assert event.type == EventType.TOOL_CALL_REQUEST
        assert event.data["name"] == "read_file"

    def test_tool_call_result_event(self) -> None:
        """Test creating a tool call result event."""
        result_data = {"tool_call_id": "call_1", "result": "file contents"}
        event = AgentEvent(type=EventType.TOOL_CALL_RESULT, data=result_data)
        assert event.type == EventType.TOOL_CALL_RESULT
        assert event.data["result"] == "file contents"

    def test_error_event(self) -> None:
        """Test creating an error event."""
        event = AgentEvent(type=EventType.ERROR, data="Something went wrong")
        assert event.type == EventType.ERROR
        assert event.data == "Something went wrong"

    def test_finished_event(self) -> None:
        """Test creating a finished event."""
        event = AgentEvent(type=EventType.FINISHED)
        assert event.type == EventType.FINISHED
        assert event.data is None

    def test_event_with_none_data(self) -> None:
        """Test creating an event with no data."""
        event = AgentEvent(type=EventType.CONTENT)
        assert event.type == EventType.CONTENT
        assert event.data is None

    def test_event_equality(self) -> None:
        """Test that events with same type and data are equal."""
        event1 = AgentEvent(type=EventType.CONTENT, data="Hello")
        event2 = AgentEvent(type=EventType.CONTENT, data="Hello")
        assert event1 == event2

    def test_event_inequality(self) -> None:
        """Test that events with different data are not equal."""
        event1 = AgentEvent(type=EventType.CONTENT, data="Hello")
        event2 = AgentEvent(type=EventType.CONTENT, data="World")
        assert event1 != event2
