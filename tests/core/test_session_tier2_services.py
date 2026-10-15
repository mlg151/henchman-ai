"""Tests for Tier 2 session/context services."""

from __future__ import annotations

import json
from pathlib import Path

from henchman.core.session import SessionManager, SessionMessage
from henchman.core.session_context import SessionContextService
from henchman.core.session_memory import SessionMemoryService
from henchman.core.session_vcr import SessionVcrService


def _build_session(manager: SessionManager, *, project_hash: str = "abc123") -> tuple[str, object]:
    """Create and persist a representative Tier 2 session."""

    session = manager.create_session(project_hash=project_hash, tag="tier2")
    session.messages = [
        SessionMessage(role="user", content="Prefer JSON output."),
        SessionMessage(
            role="assistant",
            content="I will inspect the README.",
            tool_calls=[{"id": "tc1", "name": "read_file", "arguments": {"path": "README.md"}}],
        ),
        SessionMessage(role="tool", content="README contents", tool_call_id="tc1"),
        SessionMessage(role="assistant", content="Preference noted."),
        SessionMessage(role="user", content="Show me the summary."),
        SessionMessage(role="assistant", content="Summary ready."),
    ]
    manager.save(session)
    return session.id, session


def test_build_snapshot_reports_tokens_and_tool_usage(tmp_path: Path) -> None:
    """Snapshot should include turn, token, and tool-use information."""

    manager = SessionManager(data_dir=tmp_path / "sessions")
    _, session = _build_session(manager)
    service = SessionContextService(manager)

    snapshot = service.build_snapshot(session)

    assert snapshot.turn_count == 2
    assert snapshot.message_count == 6
    assert snapshot.token_estimate > 0
    assert snapshot.tool_usage.total_calls == 1
    assert snapshot.tool_usage.total_results == 1
    assert snapshot.tool_usage.calls_by_name["read_file"] == 1


def test_resolve_active_session_falls_back_to_latest_session(tmp_path: Path) -> None:
    """The latest project session should become current when no pointer exists."""

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    manager = SessionManager(data_dir=tmp_path / "sessions")
    service = SessionContextService(manager)

    older = manager.create_session(project_hash=manager.compute_project_hash(workspace), tag="older")
    older.last_updated = "2026-01-01T00:00:00+00:00"
    manager.save(older)

    latest = manager.create_session(project_hash=manager.compute_project_hash(workspace), tag="latest")
    manager.save(latest)

    project_hash, resolved = service.resolve_active_session(workspace)

    assert project_hash == manager.compute_project_hash(workspace)
    assert resolved.id == latest.id
    assert manager.get_project_current(project_hash) == latest.id


def test_compact_session_summarizes_older_turns(tmp_path: Path) -> None:
    """Compaction should preserve recent turns and append a summary record."""

    manager = SessionManager(data_dir=tmp_path / "sessions")
    _, session = _build_session(manager)
    service = SessionContextService(manager)

    result = service.compact_session(session, preserve_turns=1)

    assert result.changed is True
    assert result.removed_turns == 1
    assert len(session.turn_summaries) == 1
    assert "Prefer JSON output." in session.turn_summaries[0].summary_text
    assert [message.content for message in session.messages if message.role == "user"] == [
        "Show me the summary."
    ]


def test_rewind_session_drops_last_turns(tmp_path: Path) -> None:
    """Rewind should remove whole turns rather than individual trailing messages."""

    manager = SessionManager(data_dir=tmp_path / "sessions")
    _, session = _build_session(manager)
    service = SessionContextService(manager)

    result = service.rewind_session(session, turns=1)

    assert result.removed_turns == 1
    assert result.remaining_turns == 1
    assert [message.content for message in session.messages if message.role == "user"] == [
        "Prefer JSON output."
    ]
    assert any(message.role == "tool" for message in session.messages)


def test_memory_service_round_trips_and_extracts_preferences(tmp_path: Path) -> None:
    """Session memory should persist manual and extracted entries in session metadata."""

    manager = SessionManager(data_dir=tmp_path / "sessions")
    _, session = _build_session(manager)
    service = SessionMemoryService()

    manual = service.add_memory(session, content="Use .henchman for project config.", kind="preference")
    extracted = service.extract_memories(session)

    memories = service.list_memories(session)

    assert manual in memories
    assert any(memory.content == "Prefer JSON output." for memory in extracted)
    assert len(memories) == 2
    assert service.delete_memory(session, manual.id) is True
    assert all(memory.id != manual.id for memory in service.list_memories(session))


def test_vcr_service_records_and_loads_playback(tmp_path: Path) -> None:
    """VCR service should persist a playback recording for a session."""

    manager = SessionManager(data_dir=tmp_path / "sessions")
    _, session = _build_session(manager)
    context_service = SessionContextService(manager)
    context_service.compact_session(session, preserve_turns=1)

    vcr_service = SessionVcrService(base_dir=tmp_path / "vcr")
    recording_path = vcr_service.record_session(session)
    payload = json.loads(recording_path.read_text(encoding="utf-8"))
    loaded = vcr_service.load_recording(recording_path)

    assert recording_path.exists()
    assert payload["session_id"] == session.id
    assert loaded["session_id"] == session.id
    assert loaded["events"][0]["type"] == "message"
    assert any(event["type"] == "summary" for event in loaded["events"])
