"""Tests for error cases in session.py."""

from unittest.mock import MagicMock, patch

import pytest

from henchman.core.session import SessionManager


def test_load_ambiguous_session_id() -> None:
    """Test that load() raises ValueError for ambiguous session ID prefix."""
    manager = SessionManager()

    # Mock data_dir to return multiple matching files
    mock_file1 = MagicMock()
    mock_file1.name = "session-abc123.json"

    mock_file2 = MagicMock()
    mock_file2.name = "session-abc456.json"

    # Patch the glob method on Path
    with patch("pathlib.Path.glob") as mock_glob:
        mock_glob.return_value = [mock_file1, mock_file2]

        with pytest.raises(ValueError, match="Ambiguous session ID prefix: session-abc"):
            manager.load("session-abc")


def test_load_session_not_found() -> None:
    """Test that load() raises FileNotFoundError when session doesn't exist."""
    manager = SessionManager()

    with patch("pathlib.Path.glob") as mock_glob:
        mock_glob.return_value = []  # No matching files

        with pytest.raises(FileNotFoundError, match="Session not found: nonexistent"):
            manager.load("nonexistent")
