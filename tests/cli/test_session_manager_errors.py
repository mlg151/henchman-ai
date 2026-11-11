"""Tests for error cases in session_manager.py."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from henchman.cli.session_manager import ReplSessionManager
from henchman.core.session import SessionManager


def test_save_no_session() -> None:
    """Test that save() raises ValueError when no session exists."""
    manager = ReplSessionManager()

    # No current session and no session provided
    with pytest.raises(ValueError, match="No session to save"):
        manager.save()


def test_save_with_session(tmp_path: Path) -> None:
    """Test that save() works when session is provided."""
    mock_session_manager = MagicMock(spec=SessionManager)
    mock_session_manager.data_dir = tmp_path / "sessions"
    mock_session = MagicMock()

    manager = ReplSessionManager(session_manager=mock_session_manager)
    manager.save(session=mock_session)

    mock_session_manager.save.assert_called_once_with(mock_session)


def test_save_current_session(tmp_path: Path) -> None:
    """Test that save() works with current session."""
    mock_session_manager = MagicMock(spec=SessionManager)
    mock_session_manager.data_dir = tmp_path / "sessions"
    mock_session = MagicMock()

    manager = ReplSessionManager(session_manager=mock_session_manager)
    manager.session = mock_session
    manager.save()

    mock_session_manager.save.assert_called_once_with(mock_session)
