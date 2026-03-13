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


class TestSessionManagerEnhancedFeatures:
    """Tests for enhanced session management features."""

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

    @pytest.fixture
    def sample_session(self, manager: SessionManager) -> tuple[str, list[SessionMessage]]:
        """Create a sample session with messages."""
        session = manager.create_session(project_hash="abc123", tag="test-session")
        messages = [
            SessionMessage(role="user", content="Hello"),
            SessionMessage(role="assistant", content="Hi there!"),
            SessionMessage(role="user", content="How are you?"),
            SessionMessage(role="assistant", content="I'm good, thanks!"),
        ]
        session.messages = messages
        manager.save(session)
        return session.id, messages

    def test_branch_session(
        self, manager: SessionManager, sample_session: tuple[str, list[SessionMessage]]
    ) -> None:
        """Test branching a session."""
        session_id, messages = sample_session
        branch_point = 2  # After first user-assistant exchange

        branch = manager.branch_session(session_id, branch_point, tag="branched")
        manager.save(branch)

        assert branch.id != session_id
        assert branch.parent_id == session_id
        assert branch.branch_point == branch_point
        assert branch.tag == "branched"
        assert len(branch.messages) == branch_point
        assert branch.messages == messages[:branch_point]

    def test_branch_session_invalid_point(
        self, manager: SessionManager, sample_session: tuple[str, list[SessionMessage]]
    ) -> None:
        """Test branching with invalid branch point."""
        session_id, _ = sample_session

        with pytest.raises(ValueError, match="out of range"):
            manager.branch_session(session_id, -1)

        with pytest.raises(ValueError, match="out of range"):
            manager.branch_session(session_id, 10)  # More than message count

    def test_merge_sessions_union(self, manager: SessionManager) -> None:
        """Test merging sessions with union strategy."""
        # Create two sessions with some overlapping messages
        s1 = manager.create_session(project_hash="abc123", tag="session1")
        s1.messages = [
            SessionMessage(role="user", content="Hello"),
            SessionMessage(role="assistant", content="Hi"),
        ]
        manager.save(s1)

        s2 = manager.create_session(project_hash="abc123", tag="session2")
        s2.messages = [
            SessionMessage(role="user", content="How are you?"),
            SessionMessage(role="assistant", content="Good"),
        ]
        manager.save(s2)

        merged = manager.merge_sessions([s1.id, s2.id], strategy="union", tag="merged")

        assert merged.id is not None
        assert merged.tag == "merged"
        assert len(merged.messages) == 4  # All messages from both sessions
        assert "merged_from" in merged.export_metadata
        assert merged.export_metadata["merge_strategy"] == "union"

    def test_merge_sessions_smart(self, manager: SessionManager) -> None:
        """Test merging sessions with smart strategy (removes duplicates)."""
        # Create two sessions with duplicate messages
        common_msg = SessionMessage(role="user", content="Hello")

        s1 = manager.create_session(project_hash="abc123")
        s1.messages = [common_msg, SessionMessage(role="assistant", content="Hi")]
        manager.save(s1)

        s2 = manager.create_session(project_hash="abc123")
        s2.messages = [common_msg, SessionMessage(role="assistant", content="Hello!")]
        manager.save(s2)

        merged = manager.merge_sessions([s1.id, s2.id], strategy="smart")

        # Should have 3 unique messages (common "Hello" appears once)
        assert len(merged.messages) == 3

    def test_merge_sessions_intersection(self, manager: SessionManager) -> None:
        """Test merging sessions with intersection strategy."""
        common_msg = SessionMessage(role="user", content="Common message")

        s1 = manager.create_session(project_hash="abc123")
        s1.messages = [
            common_msg,
            SessionMessage(role="assistant", content="Response 1"),
        ]
        manager.save(s1)

        s2 = manager.create_session(project_hash="abc123")
        s2.messages = [
            common_msg,
            SessionMessage(role="assistant", content="Response 2"),
        ]
        manager.save(s2)

        merged = manager.merge_sessions([s1.id, s2.id], strategy="intersection")

        # Should only have the common message
        assert len(merged.messages) == 1
        assert merged.messages[0].content == "Common message"

    def test_merge_sessions_different_projects(self, manager: SessionManager) -> None:
        """Test merging sessions from different projects raises error."""
        s1 = manager.create_session(project_hash="abc123")
        manager.save(s1)

        s2 = manager.create_session(project_hash="different")
        manager.save(s2)

        with pytest.raises(ValueError, match="different projects"):
            manager.merge_sessions([s1.id, s2.id])

    def test_merge_sessions_insufficient_sessions(self, manager: SessionManager) -> None:
        """Test merging with insufficient sessions raises error."""
        s1 = manager.create_session(project_hash="abc123")
        manager.save(s1)

        with pytest.raises(ValueError, match="At least 2 sessions"):
            manager.merge_sessions([s1.id])

        with pytest.raises(ValueError, match="At least 2 sessions"):
            manager.merge_sessions([])

    def test_export_session_json(
        self, manager: SessionManager, sample_session: tuple[str, list[SessionMessage]]
    ) -> None:
        """Test exporting session to JSON."""
        session_id, _ = sample_session

        exported = manager.export_session(session_id, format="json")

        # Should be valid JSON
        import json

        data = json.loads(exported)
        assert data["id"] == session_id
        assert "messages" in data

    def test_export_session_markdown(
        self, manager: SessionManager, sample_session: tuple[str, list[SessionMessage]]
    ) -> None:
        """Test exporting session to Markdown."""
        session_id, messages = sample_session

        exported = manager.export_session(session_id, format="markdown")

        # Should contain session info and messages
        assert "# Session:" in exported
        assert "Hello" in exported
        assert "Hi there!" in exported

    def test_export_session_invalid_format(
        self, manager: SessionManager, sample_session: tuple[str, list[SessionMessage]]
    ) -> None:
        """Test exporting with invalid format raises error."""
        session_id, _ = sample_session

        with pytest.raises(ValueError, match="Unsupported export format"):
            manager.export_session(session_id, format="invalid")

    def test_import_session_json(
        self, manager: SessionManager, sample_session: tuple[str, list[SessionMessage]]
    ) -> None:
        """Test importing session from JSON."""
        session_id, messages = sample_session

        # Export then import
        exported = manager.export_session(session_id, format="json")
        imported = manager.import_session(exported, format="json", tag="imported")

        assert imported.id != session_id  # Should have new ID
        assert imported.tag == "imported"
        assert len(imported.messages) == len(messages)
        assert "imported_at" in imported.export_metadata

    def test_save_template(
        self, manager: SessionManager, sample_session: tuple[str, list[SessionMessage]]
    ) -> None:
        """Test saving a session as template."""
        session_id, _ = sample_session

        template = manager.save_template(
            session_id,
            name="Test Template",
            description="A test template",
            parameters={"project_name": "Project name"},
        )

        assert "id" in template
        assert template["name"] == "Test Template"
        assert template["description"] == "A test template"
        assert "project_name" in template["parameters"]

        # Check template file exists
        templates_dir = manager.data_dir / "templates"
        template_path = templates_dir / f"{template['id']}.json"
        assert template_path.exists()

    def test_create_from_template(self, manager: SessionManager) -> None:
        """Test creating session from template."""
        # First create a session and save as template
        session = manager.create_session(project_hash="abc123", tag="source")
        session.messages = [SessionMessage(role="user", content="Hello {{name}}")]
        manager.save(session)

        template = manager.save_template(
            session.id, name="Greeting Template", parameters={"name": "User name"}
        )

        # Create from template with parameters
        new_session = manager.create_from_template(
            template["id"], parameters={"name": "Alice"}, tag="greeting-alice"
        )

        assert new_session.template_id == template["id"]
        assert new_session.tag == "greeting-alice"
        assert len(new_session.messages) == 1
        assert new_session.messages[0].content == "Hello Alice"

    def test_list_templates(self, manager: SessionManager) -> None:
        """Test listing templates."""
        # Create a template
        session = manager.create_session(project_hash="abc123")
        manager.save(session)
        template = manager.save_template(session.id, name="Test Template")

        templates = manager.list_templates()

        assert len(templates) == 1
        assert templates[0]["name"] == "Test Template"
        assert templates[0]["id"] == template["id"]

    def test_delete_template(self, manager: SessionManager) -> None:
        """Test deleting a template."""
        # Create a template
        session = manager.create_session(project_hash="abc123")
        manager.save(session)
        template = manager.save_template(session.id, name="Test Template")

        # Delete it
        manager.delete_template(template["id"])

        # Should not be in list
        templates = manager.list_templates()
        assert len(templates) == 0

        # Should raise error if trying to delete again
        with pytest.raises(FileNotFoundError):
            manager.delete_template(template["id"])


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

    def test_project_hash_is_consistent(self, manager: SessionManager, tmp_path: Path) -> None:
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
