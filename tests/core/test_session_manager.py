"""Tests for SessionManager."""

from __future__ import annotations

from pathlib import Path

import pytest

from henchman.core.session import SessionManager, SessionMessage


class TestSessionManager:
    """Tests for SessionManager class."""

    @pytest.fixture
    def temp_data_dir(self, tmp_path: Path) -> Path:
        """Create a temporary data directory."""
        data_dir = tmp_path / "sessions"
        data_dir.mkdir()
        return data_dir

    @pytest.fixture
    def manager(self, temp_data_dir: Path) -> SessionManager:
        """Create a SessionManager with temp directory."""
        return SessionManager(data_dir=temp_data_dir)

    def test_create_manager(self, temp_data_dir: Path) -> None:
        """Test creating a session manager."""
        manager = SessionManager(data_dir=temp_data_dir)
        assert manager.data_dir == temp_data_dir

    def test_default_data_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Test default data directory is ~/.henchman/sessions."""
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        manager = SessionManager()
        assert manager.data_dir == home / ".henchman" / "sessions"

    def test_create_session(self, manager: SessionManager) -> None:
        """Test creating a new session."""
        session = manager.create_session(project_hash="abc123")
        assert session.id is not None
        assert session.project_hash == "abc123"
        assert len(session.messages) == 0

    def test_create_session_with_tag(self, manager: SessionManager) -> None:
        """Test creating a session with a tag."""
        session = manager.create_session(project_hash="abc123", tag="my-session")
        assert session.tag == "my-session"

    def test_save_session(self, manager: SessionManager) -> None:
        """Test saving a session."""
        session = manager.create_session(project_hash="abc123")
        session.messages.append(SessionMessage(role="user", content="Hello"))

        path = manager.save(session)
        assert path.exists()
        assert path.suffix == ".json"

    def test_load_session(self, manager: SessionManager) -> None:
        """Test loading a saved session."""
        session = manager.create_session(project_hash="abc123")
        session.messages.append(SessionMessage(role="user", content="Hello"))
        manager.save(session)

        loaded = manager.load(session.id)
        assert loaded.id == session.id
        assert len(loaded.messages) == 1
        assert loaded.messages[0].content == "Hello"

    def test_load_nonexistent_session(self, manager: SessionManager) -> None:
        """Test loading a nonexistent session raises error."""
        with pytest.raises(FileNotFoundError):
            manager.load("nonexistent_id")

    def test_load_by_tag(self, manager: SessionManager) -> None:
        """Test loading a session by tag."""
        session = manager.create_session(project_hash="abc123", tag="my-tag")
        manager.save(session)

        loaded = manager.load_by_tag("my-tag", project_hash="abc123")
        assert loaded is not None
        assert loaded.tag == "my-tag"

    def test_load_by_tag_not_found(self, manager: SessionManager) -> None:
        """Test loading by nonexistent tag returns None."""
        result = manager.load_by_tag("nonexistent", project_hash="abc123")
        assert result is None

    def test_load_by_tag_skips_non_matching(self, manager: SessionManager) -> None:
        """Test load_by_tag skips sessions with non-matching tags."""
        # Create target session first
        s1 = manager.create_session(project_hash="abc123", tag="target")
        manager.save(s1)

        # Create non-matching session that will be sorted first (more recent)
        s2 = manager.create_session(project_hash="abc123", tag="other")
        manager.save(s2)

        # Load by tag - should skip 'other' and find 'target'
        loaded = manager.load_by_tag("target", project_hash="abc123")
        assert loaded is not None
        assert loaded.tag == "target"

    def test_list_sessions(self, manager: SessionManager) -> None:
        """Test listing sessions."""
        # Create multiple sessions
        s1 = manager.create_session(project_hash="abc123", tag="first")
        s2 = manager.create_session(project_hash="abc123", tag="second")
        s3 = manager.create_session(project_hash="other", tag="third")

        manager.save(s1)
        manager.save(s2)
        manager.save(s3)

        # List for specific project
        sessions = manager.list_sessions(project_hash="abc123")
        assert len(sessions) == 2
        tags = [s.tag for s in sessions]
        assert "first" in tags
        assert "second" in tags

    def test_list_sessions_empty(self, manager: SessionManager) -> None:
        """Test listing sessions when none exist."""
        sessions = manager.list_sessions(project_hash="abc123")
        assert sessions == []

    def test_list_sessions_no_data_dir(self, tmp_path: Path) -> None:
        """Test listing sessions when data_dir doesn't exist."""
        nonexistent_dir = tmp_path / "nonexistent"
        manager = SessionManager(data_dir=nonexistent_dir)
        sessions = manager.list_sessions()
        assert sessions == []

    def test_list_sessions_skips_invalid_json(
        self, manager: SessionManager, temp_data_dir: Path
    ) -> None:
        """Test listing sessions skips invalid JSON files."""
        # Create a valid session
        s1 = manager.create_session(project_hash="abc123", tag="valid")
        manager.save(s1)

        # Create an invalid JSON file
        invalid_file = temp_data_dir / "invalid.json"
        invalid_file.write_text("not valid json {{{")

        sessions = manager.list_sessions()
        assert len(sessions) == 1
        assert sessions[0].tag == "valid"

    def test_list_all_sessions(self, manager: SessionManager) -> None:
        """Test listing all sessions regardless of project."""
        s1 = manager.create_session(project_hash="abc123")
        s2 = manager.create_session(project_hash="other")
        manager.save(s1)
        manager.save(s2)

        sessions = manager.list_sessions()
        assert len(sessions) == 2

    def test_delete_session(self, manager: SessionManager) -> None:
        """Test deleting a session."""
        session = manager.create_session(project_hash="abc123")
        path = manager.save(session)
        assert path.exists()

        manager.delete(session.id)
        assert not path.exists()

    def test_delete_nonexistent_session(self, manager: SessionManager) -> None:
        """Test deleting a nonexistent session raises error."""
        with pytest.raises(FileNotFoundError):
            manager.delete("nonexistent_id")

    def test_update_session(self, manager: SessionManager) -> None:
        """Test updating a session."""
        session = manager.create_session(project_hash="abc123")
        manager.save(session)

        # Add messages and update
        session.messages.append(SessionMessage(role="user", content="Hello"))
        old_updated = session.last_updated
        manager.save(session)

        # Reload and verify
        loaded = manager.load(session.id)
        assert len(loaded.messages) == 1
        assert loaded.last_updated >= old_updated

    def test_get_current_session(self, manager: SessionManager) -> None:
        """Test getting current session."""
        assert manager.current is None

        session = manager.create_session(project_hash="abc123")
        manager.set_current(session)
        assert manager.current is session

    def test_clear_current_session(self, manager: SessionManager) -> None:
        """Test clearing current session."""
        session = manager.create_session(project_hash="abc123")
        manager.set_current(session)
        manager.clear_current()
        assert manager.current is None


class TestSessionManagerProjectHash:
    """Tests for project hash functionality."""

    @pytest.fixture
    def temp_data_dir(self, tmp_path: Path) -> Path:
        """Create a temporary data directory."""
        data_dir = tmp_path / "sessions"
        data_dir.mkdir()
        return data_dir

    @pytest.fixture
    def manager(self, temp_data_dir: Path) -> SessionManager:
        """Create a SessionManager with temp directory."""
        return SessionManager(data_dir=temp_data_dir)

    def test_compute_project_hash(self, manager: SessionManager, tmp_path: Path) -> None:
        """Test computing project hash from directory."""
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        hash1 = manager.compute_project_hash(project_dir)
        assert hash1 is not None
        assert len(hash1) > 0

    def test_project_hash_is_consistent(
        self, manager: SessionManager, tmp_path: Path
    ) -> None:
        """Test that project hash is consistent for same directory."""
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        hash1 = manager.compute_project_hash(project_dir)
        hash2 = manager.compute_project_hash(project_dir)
        assert hash1 == hash2

    def test_project_hash_differs_for_different_dirs(
        self, manager: SessionManager, tmp_path: Path
    ) -> None:
        """Test that different directories have different hashes."""
        dir1 = tmp_path / "project1"
        dir2 = tmp_path / "project2"
        dir1.mkdir()
        dir2.mkdir()

        hash1 = manager.compute_project_hash(dir1)
        hash2 = manager.compute_project_hash(dir2)
        assert hash1 != hash2
