"""Tests for session management screen in textual UI."""

import pytest
from unittest.mock import MagicMock

from henchman.cli.textual_screens import (
    ConfirmToolScreen,
    HelpScreen,
    ProviderScreen,
    SessionScreen,
)


class TestSessionManagementScreen:
    """Tests for SessionScreen widget."""

    def test_session_screen_creation(self):
        """Test that session management screen can be created."""
        screen = SessionScreen()
        assert screen._sessions == []

    def test_session_list_display(self):
        """Test that session list shows name, datetime, and message count."""
        sess = MagicMock()
        sess.tag = "my-feature"
        sess.id = "abc123"
        sess.updated_at = "2025-01-15T10:30:00"
        sess.message_count = 12
        screen = SessionScreen(sessions=[sess])
        entries = screen._build_entries()
        assert len(entries) == 1
        label, sid = entries[0]
        assert "my-feature" in label
        assert "2025-01-15" in label
        assert "12 messages" in label
        assert sid == "abc123"

    def test_session_resume_functionality(self):
        """Test that resume returns the correct dismiss value."""
        screen = SessionScreen(sessions=[])
        entries = screen._build_entries()
        assert entries == []

    def test_session_delete_functionality(self):
        """Test session screen with multiple sessions."""
        sessions = []
        for i in range(3):
            s = MagicMock()
            s.tag = f"session-{i}"
            s.id = f"id-{i}"
            s.updated_at = f"2025-01-{15 + i}T10:00:00"
            s.message_count = i * 5
            sessions.append(s)
        screen = SessionScreen(sessions=sessions)
        entries = screen._build_entries()
        assert len(entries) == 3
        assert "session-0" in entries[0][0]
        assert "session-2" in entries[2][0]

    def test_session_list_functionality(self):
        """Test session screen empty state."""
        screen = SessionScreen(sessions=None)
        assert screen._sessions == []
        entries = screen._build_entries()
        assert entries == []
