"""Tests for session data models."""

from __future__ import annotations

import json

from henchman.core.session import Session, SessionMessage, SessionMetadata


class TestSessionMessage:
    """Tests for SessionMessage dataclass."""

    def test_user_message(self) -> None:
        """Test creating a user message."""
        msg = SessionMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.tool_calls is None
        assert msg.tool_call_id is None

    def test_assistant_message(self) -> None:
        """Test creating an assistant message."""
        msg = SessionMessage(role="assistant", content="Hi there!")
        assert msg.role == "assistant"
        assert msg.content == "Hi there!"

    def test_tool_message(self) -> None:
        """Test creating a tool result message."""
        msg = SessionMessage(
            role="tool",
            content="File contents here",
            tool_call_id="call_123",
        )
        assert msg.role == "tool"
        assert msg.tool_call_id == "call_123"

    def test_message_with_tool_calls(self) -> None:
        """Test message with tool calls."""
        tool_calls = [{"id": "call_1", "name": "read_file", "arguments": {"path": "test.txt"}}]
        msg = SessionMessage(
            role="assistant",
            content=None,
            tool_calls=tool_calls,
        )
        assert msg.tool_calls == tool_calls

    def test_message_with_agent(self) -> None:
        """Test message with agent attribution."""
        msg = SessionMessage(
            role="assistant", content="Hello", agent_id="coder-1", agent_role="coder"
        )
        assert msg.agent_id == "coder-1"
        assert msg.agent_role == "coder"
        data = msg.to_dict()
        assert data["agent_id"] == "coder-1"
        assert data["agent_role"] == "coder"

        msg2 = SessionMessage.from_dict(data)
        assert msg2.agent_id == "coder-1"

    def test_to_dict(self) -> None:
        """Test converting message to dict."""
        msg = SessionMessage(role="user", content="Hello")
        data = msg.to_dict()
        assert data["role"] == "user"
        assert data["content"] == "Hello"

    def test_to_dict_minimal(self) -> None:
        """Test converting message with minimal fields to dict."""
        msg = SessionMessage(role="assistant")
        data = msg.to_dict()
        assert data == {"role": "assistant"}
        assert "content" not in data
        assert "tool_calls" not in data
        assert "tool_call_id" not in data

    def test_to_dict_with_tool_calls(self) -> None:
        """Test to_dict includes tool_calls."""
        tool_calls = [{"id": "call_1", "name": "test"}]
        msg = SessionMessage(role="assistant", tool_calls=tool_calls)
        data = msg.to_dict()
        assert data["tool_calls"] == tool_calls

    def test_to_dict_with_tool_call_id(self) -> None:
        """Test to_dict includes tool_call_id."""
        msg = SessionMessage(role="tool", content="result", tool_call_id="call_123")
        data = msg.to_dict()
        assert data["tool_call_id"] == "call_123"

    def test_from_dict(self) -> None:
        """Test creating message from dict."""
        data = {"role": "user", "content": "Hello"}
        msg = SessionMessage.from_dict(data)
        assert msg.role == "user"
        assert msg.content == "Hello"


class TestSessionMetadata:
    """Tests for SessionMetadata dataclass."""

    def test_create_metadata(self) -> None:
        """Test creating session metadata."""
        meta = SessionMetadata(
            id="session_123",
            tag="my-session",
            project_hash="abc123",
            started="2026-01-23T12:00:00Z",
            last_updated="2026-01-23T12:30:00Z",
            message_count=5,
        )
        assert meta.id == "session_123"
        assert meta.tag == "my-session"
        assert meta.project_hash == "abc123"
        assert meta.message_count == 5

    def test_metadata_without_tag(self) -> None:
        """Test metadata without a tag."""
        meta = SessionMetadata(
            id="session_123",
            project_hash="abc123",
            started="2026-01-23T12:00:00Z",
            last_updated="2026-01-23T12:00:00Z",
            message_count=0,
        )
        assert meta.tag is None

    def test_to_dict(self) -> None:
        """Test converting metadata to dict."""
        meta = SessionMetadata(
            id="session_123",
            tag="test",
            project_hash="abc123",
            started="2026-01-23T12:00:00Z",
            last_updated="2026-01-23T12:00:00Z",
            message_count=3,
        )
        data = meta.to_dict()
        assert data["id"] == "session_123"
        assert data["tag"] == "test"

    def test_from_dict(self) -> None:
        """Test creating metadata from dict."""
        data = {
            "id": "session_123",
            "tag": "test",
            "project_hash": "abc123",
            "started": "2026-01-23T12:00:00Z",
            "last_updated": "2026-01-23T12:00:00Z",
            "message_count": 3,
        }
        meta = SessionMetadata.from_dict(data)
        assert meta.id == "session_123"
        assert meta.tag == "test"


class TestSession:
    """Tests for Session dataclass."""

    def test_create_session(self) -> None:
        """Test creating a session."""
        session = Session(
            id="session_123",
            project_hash="abc123",
            started="2026-01-23T12:00:00Z",
            last_updated="2026-01-23T12:00:00Z",
            messages=[],
        )
        assert session.id == "session_123"
        assert session.project_hash == "abc123"
        assert session.messages == []
        assert session.tag is None

    def test_session_with_tag(self) -> None:
        """Test session with a tag."""
        session = Session(
            id="session_123",
            project_hash="abc123",
            started="2026-01-23T12:00:00Z",
            last_updated="2026-01-23T12:00:00Z",
            messages=[],
            tag="my-session",
        )
        assert session.tag == "my-session"

    def test_session_with_messages(self) -> None:
        """Test session with messages."""
        messages = [
            SessionMessage(role="user", content="Hello"),
            SessionMessage(role="assistant", content="Hi!"),
        ]
        session = Session(
            id="session_123",
            project_hash="abc123",
            started="2026-01-23T12:00:00Z",
            last_updated="2026-01-23T12:00:00Z",
            messages=messages,
        )
        assert len(session.messages) == 2

    def test_session_with_agents_and_delegation(self) -> None:
        """Test session with multi-agent data."""
        session = Session(
            id="session_123",
            project_hash="abc123",
            started="2026-01-23T12:00:00Z",
            last_updated="2026-01-23T12:00:00Z",
            active_agents=["tech_lead", "coder"],
            delegation_log=[{"from": "tech_lead", "to": "coder", "task": "test"}],
        )
        data = session.to_dict()
        assert data["active_agents"] == ["tech_lead", "coder"]
        assert len(data["delegation_log"]) == 1

        session2 = Session.from_dict(data)
        assert session2.active_agents == ["tech_lead", "coder"]

    def test_to_dict(self) -> None:
        """Test converting session to dict."""
        session = Session(
            id="session_123",
            project_hash="abc123",
            started="2026-01-23T12:00:00Z",
            last_updated="2026-01-23T12:00:00Z",
            messages=[SessionMessage(role="user", content="Hello")],
            tag="test",
        )
        data = session.to_dict()
        assert data["id"] == "session_123"
        assert data["tag"] == "test"
        assert len(data["messages"]) == 1

    def test_from_dict(self) -> None:
        """Test creating session from dict."""
        data = {
            "id": "session_123",
            "project_hash": "abc123",
            "started": "2026-01-23T12:00:00Z",
            "last_updated": "2026-01-23T12:00:00Z",
            "messages": [{"role": "user", "content": "Hello"}],
            "tag": "test",
        }
        session = Session.from_dict(data)
        assert session.id == "session_123"
        assert session.tag == "test"
        assert len(session.messages) == 1
        assert session.messages[0].content == "Hello"

    def test_to_json(self) -> None:
        """Test serializing session to JSON."""
        session = Session(
            id="session_123",
            project_hash="abc123",
            started="2026-01-23T12:00:00Z",
            last_updated="2026-01-23T12:00:00Z",
            messages=[],
        )
        json_str = session.to_json()
        parsed = json.loads(json_str)
        assert parsed["id"] == "session_123"

    def test_from_json(self) -> None:
        """Test deserializing session from JSON."""
        json_str = json.dumps(
            {
                "id": "session_123",
                "project_hash": "abc123",
                "started": "2026-01-23T12:00:00Z",
                "last_updated": "2026-01-23T12:00:00Z",
                "messages": [],
            }
        )
        session = Session.from_json(json_str)
        assert session.id == "session_123"

    def test_get_metadata(self) -> None:
        """Test getting session metadata."""
        session = Session(
            id="session_123",
            project_hash="abc123",
            started="2026-01-23T12:00:00Z",
            last_updated="2026-01-23T12:30:00Z",
            messages=[
                SessionMessage(role="user", content="Hello"),
                SessionMessage(role="assistant", content="Hi!"),
            ],
            tag="my-session",
        )
        meta = session.get_metadata()
        assert meta.id == "session_123"
        assert meta.tag == "my-session"
        assert meta.message_count == 2

    def test_session_with_enhanced_fields(self) -> None:
        """Test session with enhanced fields (branching, templates, etc.)."""
        session = Session(
            id="session_123",
            project_hash="abc123",
            started="2026-01-23T12:00:00Z",
            last_updated="2026-01-23T12:00:00Z",
            parent_id="parent_123",
            branch_point=5,
            template_id="template_123",
            template_parameters={"project": "test"},
            export_metadata={"exported": True},
        )

        assert session.parent_id == "parent_123"
        assert session.branch_point == 5
        assert session.template_id == "template_123"
        assert session.template_parameters == {"project": "test"}
        assert session.export_metadata == {"exported": True}

    def test_session_enhanced_fields_serialization(self) -> None:
        """Test serialization/deserialization with enhanced fields."""
        session = Session(
            id="session_123",
            project_hash="abc123",
            started="2026-01-23T12:00:00Z",
            last_updated="2026-01-23T12:00:00Z",
            parent_id="parent_123",
            branch_point=3,
            template_id="template_456",
            template_parameters={"param1": "value1"},
            export_metadata={"key": "value"},
        )

        # Convert to dict and back
        data = session.to_dict()
        session2 = Session.from_dict(data)

        assert session2.parent_id == "parent_123"
        assert session2.branch_point == 3
        assert session2.template_id == "template_456"
        assert session2.template_parameters == {"param1": "value1"}
        assert session2.export_metadata == {"key": "value"}

    def test_session_enhanced_fields_json_roundtrip(self) -> None:
        """Test JSON serialization/deserialization with enhanced fields."""
        session = Session(
            id="session_123",
            project_hash="abc123",
            started="2026-01-23T12:00:00Z",
            last_updated="2026-01-23T12:00:00Z",
            parent_id="parent_123",
            template_id="template_789",
        )

        # Convert to JSON and back
        json_str = session.to_json()
        session2 = Session.from_json(json_str)

        assert session2.parent_id == "parent_123"
        assert session2.template_id == "template_789"
        assert session2.branch_point is None  # Should be None when not set
        assert session2.template_parameters == {}  # Should be empty dict when not set
        assert session2.export_metadata == {}  # Should be empty dict when not set
