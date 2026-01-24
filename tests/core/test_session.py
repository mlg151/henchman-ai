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
        tool_calls = [
            {"id": "call_1", "name": "read_file", "arguments": {"path": "test.txt"}}
        ]
        msg = SessionMessage(
            role="assistant",
            content=None,
            tool_calls=tool_calls,
        )
        assert msg.tool_calls == tool_calls

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
        json_str = json.dumps({
            "id": "session_123",
            "project_hash": "abc123",
            "started": "2026-01-23T12:00:00Z",
            "last_updated": "2026-01-23T12:00:00Z",
            "messages": [],
        })
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
