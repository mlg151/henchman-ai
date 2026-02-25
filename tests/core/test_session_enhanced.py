"""Additional tests for enhanced session management features."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from henchman.core.session import Session, SessionManager, SessionMessage, TurnSummaryRecord


class TestSessionEnhancedCoverage:
    """Additional tests to improve coverage for enhanced session features."""

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

    def test_export_session_markdown_no_metadata(self, manager: SessionManager) -> None:
        """Test exporting session to Markdown without metadata."""
        session = manager.create_session(project_hash="abc123", tag="test")
        session.messages = [
            SessionMessage(role="user", content="Hello"),
            SessionMessage(role="assistant", content="Hi!"),
        ]
        manager.save(session)
        
        exported = manager.export_session(session.id, format="markdown", include_metadata=False)
        
        # Should not contain metadata section
        assert "## Metadata" not in exported
        # Should still contain conversation
        assert "Hello" in exported
        assert "Hi!" in exported

    def test_export_session_with_tool_calls(self, manager: SessionManager) -> None:
        """Test exporting session with tool calls to Markdown."""
        session = manager.create_session(project_hash="abc123")
        session.messages = [
            SessionMessage(
                role="assistant",
                content=None,
                tool_calls=[{"id": "call_1", "name": "read_file", "arguments": {"path": "test.txt"}}]
            ),
            SessionMessage(
                role="tool",
                content="File contents",
                tool_call_id="call_1"
            ),
        ]
        manager.save(session)
        
        exported = manager.export_session(session.id, format="markdown")
        
        # Should contain tool call information
        assert "Tool Calls" in exported
        assert "read_file" in exported

    def test_export_session_with_turn_summaries(self, manager: SessionManager) -> None:
        """Test exporting session with turn summaries to Markdown."""
        session = manager.create_session(project_hash="abc123")
        session.turn_summaries = [
            TurnSummaryRecord(
                turn_number=1,
                summary_text="User asked about project structure",
                files_modified=["src/main.py"],
                tool_count=3,
                timestamp="2026-01-23T12:00:00Z"
            )
        ]
        manager.save(session)
        
        exported = manager.export_session(session.id, format="markdown")
        
        # Should contain turn summaries section
        assert "## Turn Summaries" in exported
        assert "User asked about project structure" in exported

    def test_export_session_with_agent_info(self, manager: SessionManager) -> None:
        """Test exporting session with agent information to Markdown."""
        session = manager.create_session(project_hash="abc123")
        session.messages = [
            SessionMessage(
                role="assistant",
                content="I'll help with that",
                agent_id="coder-1",
                agent_role="coder"
            ),
        ]
        manager.save(session)
        
        exported = manager.export_session(session.id, format="markdown")
        
        # Should contain agent information
        assert "Agent:" in exported
        assert "coder-1" in exported

    def test_import_session_markdown_error(self, manager: SessionManager) -> None:
        """Test importing markdown format raises appropriate error."""
        markdown_content = "# Test Session\n\nSome content"
        
        with pytest.raises(ValueError, match="Markdown import not fully implemented"):
            manager.import_session(markdown_content, format="markdown")

    def test_import_session_invalid_format(self, manager: SessionManager) -> None:
        """Test importing with invalid format raises error."""
        with pytest.raises(ValueError, match="Unsupported import format"):
            manager.import_session("{}", format="invalid")

    def test_save_template_without_parameters(self, manager: SessionManager) -> None:
        """Test saving template without parameters."""
        session = manager.create_session(project_hash="abc123")
        manager.save(session)
        
        template = manager.save_template(session.id, name="Simple Template")
        
        assert template["name"] == "Simple Template"
        assert template["parameters"] == {}

    def test_create_from_template_without_parameters(self, manager: SessionManager) -> None:
        """Test creating session from template without parameters."""
        # Create a session and save as template
        session = manager.create_session(project_hash="abc123", tag="source")
        session.messages = [SessionMessage(role="user", content="Simple message")]
        manager.save(session)
        
        template = manager.save_template(session.id, name="Simple Template")
        
        # Create from template without parameters
        new_session = manager.create_from_template(template["id"])
        
        assert new_session.template_id == template["id"]
        assert len(new_session.messages) == 1
        assert new_session.messages[0].content == "Simple message"

    def test_create_from_template_nonexistent(self, manager: SessionManager) -> None:
        """Test creating from nonexistent template raises error."""
        with pytest.raises(FileNotFoundError, match="Template not found"):
            manager.create_from_template("nonexistent-template")

    def test_delete_template_nonexistent(self, manager: SessionManager) -> None:
        """Test deleting nonexistent template raises error."""
        with pytest.raises(FileNotFoundError, match="Template not found"):
            manager.delete_template("nonexistent-template")

    def test_session_with_all_enhanced_fields(self) -> None:
        """Test session with all enhanced fields set."""
        session = Session(
            id="session_123",
            project_hash="abc123",
            started="2026-01-23T12:00:00Z",
            last_updated="2026-01-23T12:00:00Z",
            messages=[SessionMessage(role="user", content="Hello")],
            tag="test-session",
            plan_mode=True,
            turn_summaries=[
                TurnSummaryRecord(
                    turn_number=1,
                    summary_text="Test summary",
                    files_modified=[],
                    tool_count=0,
                    timestamp="2026-01-23T12:00:00Z"
                )
            ],
            active_agents=["tech_lead", "coder"],
            delegation_log=[{"task": "test"}],
            parent_id="parent_123",
            branch_point=5,
            template_id="template_123",
            template_parameters={"param1": "value1", "param2": "value2"},
            export_metadata={"key1": "value1", "key2": "value2"},
        )
        
        # Test serialization roundtrip
        data = session.to_dict()
        session2 = Session.from_dict(data)
        
        # Verify all fields
        assert session2.id == "session_123"
        assert session2.tag == "test-session"
        assert session2.plan_mode is True
        assert len(session2.turn_summaries) == 1
        assert session2.turn_summaries[0].summary_text == "Test summary"
        assert session2.active_agents == ["tech_lead", "coder"]
        assert len(session2.delegation_log) == 1
        assert session2.parent_id == "parent_123"
        assert session2.branch_point == 5
        assert session2.template_id == "template_123"
        assert session2.template_parameters == {"param1": "value1", "param2": "value2"}
        assert session2.export_metadata == {"key1": "value1", "key2": "value2"}

    def test_merge_sessions_with_turn_summaries(self, manager: SessionManager) -> None:
        """Test merging sessions with turn summaries."""
        # Create first session with turn summary
        s1 = manager.create_session(project_hash="abc123")
        s1.turn_summaries = [
            TurnSummaryRecord(
                turn_number=1,
                summary_text="First session summary",
                files_modified=[],
                tool_count=0,
                timestamp="2026-01-23T12:00:00Z"
            )
        ]
        manager.save(s1)
        
        # Create second session with turn summary
        s2 = manager.create_session(project_hash="abc123")
        s2.turn_summaries = [
            TurnSummaryRecord(
                turn_number=1,
                summary_text="Second session summary",
                files_modified=[],
                tool_count=0,
                timestamp="2026-01-23T12:30:00Z"
            )
        ]
        manager.save(s2)
        
        # Merge sessions
        merged = manager.merge_sessions([s1.id, s2.id], strategy="union")
        
        # Should have both turn summaries
        assert len(merged.turn_summaries) == 2
        summaries_text = [ts.summary_text for ts in merged.turn_summaries]
        assert "First session summary" in summaries_text
        assert "Second session summary" in summaries_text

    def test_branch_session_with_all_metadata(self, manager: SessionManager) -> None:
        """Test branching session preserves all metadata."""
        # Create parent session with various metadata
        parent = manager.create_session(project_hash="abc123", tag="parent")
        parent.messages = [
            SessionMessage(role="user", content="Message 1"),
            SessionMessage(role="assistant", content="Response 1"),
            SessionMessage(role="user", content="Message 2"),
        ]
        parent.plan_mode = True
        parent.turn_summaries = [
            TurnSummaryRecord(
                turn_number=1,
                summary_text="Turn 1 summary",
                files_modified=[],
                tool_count=0,
                timestamp="2026-01-23T12:00:00Z"
            )
        ]
        parent.active_agents = ["tech_lead"]
        parent.delegation_log = [{"task": "initial"}]
        parent.template_id = "some_template"
        parent.template_parameters = {"param": "value"}
        parent.export_metadata = {"exported": True}
        manager.save(parent)
        
        # Branch from the session
        branch = manager.branch_session(parent.id, branch_point=2, tag="branch")
        
        # Verify metadata is preserved
        assert branch.parent_id == parent.id
        assert branch.branch_point == 2
        assert branch.tag == "branch"
        assert branch.plan_mode is True
        assert branch.template_id == "some_template"
        assert branch.template_parameters == {"param": "value"}
        assert branch.export_metadata == {"exported": True}
        assert branch.active_agents == ["tech_lead"]
        assert branch.delegation_log == [{"task": "initial"}]
        assert len(branch.turn_summaries) == 1
        assert branch.turn_summaries[0].summary_text == "Turn 1 summary"
        
        # Verify messages are copied up to branch point
        assert len(branch.messages) == 2
        assert branch.messages[0].content == "Message 1"
        assert branch.messages[1].content == "Response 1"

    def test_export_import_preserves_enhanced_fields(self, manager: SessionManager) -> None:
        """Test export/import preserves enhanced session fields."""
        # Create session with enhanced fields
        session = manager.create_session(project_hash="abc123", tag="original")
        session.parent_id = "parent_123"
        session.branch_point = 3
        session.template_id = "template_456"
        session.template_parameters = {"project": "test"}
        session.export_metadata = {"custom": "data"}
        manager.save(session)
        
        # Export to JSON
        exported = manager.export_session(session.id, format="json")
        
        # Import with new tag
        imported = manager.import_session(exported, format="json", tag="imported")
        
        # Verify enhanced fields are preserved
        assert imported.parent_id == "parent_123"
        assert imported.branch_point == 3
        assert imported.template_id == "template_456"
        assert imported.template_parameters == {"project": "test"}
        assert imported.export_metadata["custom"] == "data"
        assert "imported_at" in imported.export_metadata
        assert imported.tag == "imported"