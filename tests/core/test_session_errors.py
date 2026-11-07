"""Tests for error cases in session.py."""

from pathlib import Path
from unittest.mock import patch

import pytest

from henchman.core.session import SessionManager


def test_load_ambiguous_session_id(tmp_path: Path) -> None:
    """Test that load() raises ValueError for ambiguous session ID prefix."""
    manager = SessionManager(tmp_path)
    for session_id in ("session-abc123", "session-abc456"):
        session = manager.create_session("project")
        session.id = session_id
        manager.save(session)
    with pytest.raises(ValueError, match="Ambiguous session ID prefix: session-abc"):
        manager.load("session-abc")


def test_load_session_not_found() -> None:
    """Test that load() raises FileNotFoundError when session doesn't exist."""
    manager = SessionManager()

    with patch("pathlib.Path.glob") as mock_glob:
        mock_glob.return_value = []  # No matching files

        with pytest.raises(FileNotFoundError, match="Session not found: nonexistent"):
            manager.load("nonexistent")
