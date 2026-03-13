"""Tests for ReplSessionManager covering previously uncovered code paths."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from henchman.cli.session_manager import ReplSessionManager
from henchman.core.session import Session, SessionManager, SessionMessage
from henchman.providers.base import Message, ToolCall


class TestReplSessionManagerDelegation:
    """Tests for ReplSessionManager delegation methods."""

    def _make_manager(self, tmp_path: Path) -> ReplSessionManager:
        sm = SessionManager(data_dir=tmp_path)
        return ReplSessionManager(session_manager=sm)

    def test_create_session(self, tmp_path: Path) -> None:
        """Test create_session creates and returns a session."""
        rsm = self._make_manager(tmp_path)
        session = rsm.create_session("hash123", tag="my-tag")
        assert isinstance(session, Session)
        assert session.tag == "my-tag"

    def test_load_session(self, tmp_path: Path) -> None:
        """Test load retrieves a saved session by ID."""
        rsm = self._make_manager(tmp_path)
        session = rsm.create_session("hash123")
        rsm.session_manager.save(session)
        loaded = rsm.load(session.id)
        assert loaded.id == session.id

    def test_load_by_tag(self, tmp_path: Path) -> None:
        """Test load_by_tag finds a session by its tag."""
        rsm = self._make_manager(tmp_path)
        session = rsm.create_session("hash123", tag="my-tag")
        rsm.session_manager.save(session)
        loaded = rsm.load_by_tag("my-tag", "hash123")
        assert loaded is not None
        assert loaded.tag == "my-tag"

    def test_load_by_tag_not_found(self, tmp_path: Path) -> None:
        """Test load_by_tag returns None when tag doesn't exist."""
        rsm = self._make_manager(tmp_path)
        result = rsm.load_by_tag("nonexistent", "hash123")
        assert result is None

    def test_save_raises_when_no_session(self, tmp_path: Path) -> None:
        """Test save raises ValueError when no session is provided."""
        rsm = self._make_manager(tmp_path)
        with pytest.raises(ValueError, match="No session to save"):
            rsm.save()

    def test_save_uses_current_session(self, tmp_path: Path) -> None:
        """Test save saves current session when none is passed."""
        rsm = self._make_manager(tmp_path)
        session = rsm.create_session("hash123")
        rsm.set_session(session)
        path = rsm.save()
        assert path.exists()

    def test_save_with_explicit_session(self, tmp_path: Path) -> None:
        """Test save accepts explicit session argument."""
        rsm = self._make_manager(tmp_path)
        session = rsm.create_session("hash123")
        path = rsm.save(session)
        assert path.exists()

    def test_list_sessions(self, tmp_path: Path) -> None:
        """Test list_sessions returns saved session metadata."""
        rsm = self._make_manager(tmp_path)
        session = rsm.create_session("hash123")
        rsm.session_manager.save(session)
        sessions = rsm.list_sessions("hash123")
        assert len(sessions) == 1

    def test_delete(self, tmp_path: Path) -> None:
        """Test delete removes a session."""
        rsm = self._make_manager(tmp_path)
        session = rsm.create_session("hash123")
        rsm.session_manager.save(session)
        rsm.delete(session.id)
        # Should no longer be loadable
        sessions = rsm.list_sessions("hash123")
        assert len(sessions) == 0


class TestReplSessionManagerRestoreHistory:
    """Tests for _sync_session_to_agent restore with tool_calls."""

    def test_restore_history_with_tool_calls(self, tmp_path: Path) -> None:
        """Test _sync_session_to_agent converts tool_calls dicts to ToolCall objects."""
        sm = SessionManager(data_dir=tmp_path)
        rsm = ReplSessionManager(session_manager=sm)

        session = sm.create_session("hash123")
        session.messages = [
            SessionMessage(
                role="assistant",
                content=None,
                tool_calls=[{"id": "call_1", "name": "read_file", "arguments": {"path": "/tmp/x"}}],
            ),
            SessionMessage(
                role="tool",
                content="file content",
                tool_call_id="call_1",
            ),
        ]

        # Mock orchestrator with tech_lead
        mock_orchestrator = MagicMock()
        mock_orchestrator.tech_lead.messages = []
        mock_orchestrator.tech_lead.clear_history = MagicMock(
            side_effect=lambda: mock_orchestrator.tech_lead.messages.clear()
        )

        rsm._sync_session_to_agent(session, mock_orchestrator)

        appended = mock_orchestrator.tech_lead.messages
        assert len(appended) == 2
        # First message should have ToolCall objects
        first = appended[0]
        assert isinstance(first, Message)
        assert first.tool_calls is not None
        assert isinstance(first.tool_calls[0], ToolCall)
        assert first.tool_calls[0].name == "read_file"

    def test_restore_history_without_tool_calls(self, tmp_path: Path) -> None:
        """Test _sync_session_to_agent handles messages without tool_calls."""
        sm = SessionManager(data_dir=tmp_path)
        rsm = ReplSessionManager(session_manager=sm)

        session = sm.create_session("hash123")
        session.messages = [
            SessionMessage(role="user", content="Hello"),
            SessionMessage(role="assistant", content="Hi"),
        ]

        mock_orchestrator = MagicMock()
        mock_orchestrator.tech_lead.messages = []
        mock_orchestrator.tech_lead.clear_history = MagicMock(
            side_effect=lambda: mock_orchestrator.tech_lead.messages.clear()
        )

        rsm._sync_session_to_agent(session, mock_orchestrator)

        appended = mock_orchestrator.tech_lead.messages
        assert len(appended) == 2
        assert all(isinstance(m, Message) for m in appended)
        assert all(m.tool_calls is None for m in appended)
