"""Session memory edit/clear/opt-out controls must persist and survive reload."""

from __future__ import annotations

from pathlib import Path

from henchman.core.session import SessionManager, SessionMessage
from henchman.core.session_memory import SessionMemoryService


def _build_session(manager: SessionManager) -> object:
    """Persist a session with user messages that yield extraction candidates."""

    session = manager.create_session(project_hash="abc123", tag="memory")
    session.messages = [
        SessionMessage(role="user", content="Always prefer JSON output for reports."),
        SessionMessage(role="assistant", content="Noted."),
    ]
    manager.save(session)
    return session


def test_edit_memory_updates_content_kind_and_source(tmp_path: Path) -> None:
    """Editing a record must change only the provided fields and persist."""

    manager = SessionManager(data_dir=tmp_path / "sessions")
    session = _build_session(manager)
    service = SessionMemoryService()
    record = service.add_memory(session, content="Original content.", kind="note")

    updated = service.edit_memory(
        session,
        record.id,
        content="Edited content.",
        kind="preference",
        source="manual",
    )

    assert updated is not None
    assert updated.content == "Edited content."
    assert updated.kind == "preference"
    # created_at must be stable across edits; identity is unchanged.
    assert updated.id == record.id
    assert updated.created_at == record.created_at
    assert [memory.id for memory in service.list_memories(session)] == [record.id]
    assert service.list_memories(session)[0].content == "Edited content."


def test_edit_memory_preserves_unprovided_fields(tmp_path: Path) -> None:
    """Editing one field must not clobber the fields left untouched."""

    manager = SessionManager(data_dir=tmp_path / "sessions")
    session = _build_session(manager)
    service = SessionMemoryService()
    record = service.add_memory(
        session, content="Keep me.", kind="preference", source="extracted", message_index=3
    )

    updated = service.edit_memory(session, record.id, content="New text.")

    assert updated is not None
    assert updated.kind == "preference"
    assert updated.source == "extracted"
    assert updated.message_index == 3


def test_edit_missing_memory_returns_none(tmp_path: Path) -> None:
    """Editing an unknown id must not mutate the store."""

    manager = SessionManager(data_dir=tmp_path / "sessions")
    session = _build_session(manager)
    service = SessionMemoryService()
    service.add_memory(session, content="Existing entry.")

    updated = service.edit_memory(session, "no-such-id", content="Anything.")

    assert updated is None
    assert [memory.content for memory in service.list_memories(session)] == ["Existing entry."]


def test_clear_memories_removes_all_and_reports_count(tmp_path: Path) -> None:
    """clear_memories must empty the store and report how many were removed."""

    manager = SessionManager(data_dir=tmp_path / "sessions")
    session = _build_session(manager)
    service = SessionMemoryService()
    for content in ("First.", "Second.", "Third."):
        service.add_memory(session, content=content)

    cleared = service.clear_memories(session)

    assert cleared == 3
    assert service.list_memories(session) == []
    assert service.clear_memories(session) == 0


def test_list_memories_is_read_only(tmp_path: Path) -> None:
    """Listing memories must not mutate a session that stores none."""

    manager = SessionManager(data_dir=tmp_path / "sessions")
    session = manager.create_session(project_hash="abc123", tag="memory")
    before = dict(session.export_metadata)
    service = SessionMemoryService()

    assert service.list_memories(session) == []
    assert session.export_metadata == before


def test_extraction_opt_out_blocks_persistence(tmp_path: Path) -> None:
    """With extraction opt-out set, extract_memories persists nothing."""

    manager = SessionManager(data_dir=tmp_path / "sessions")
    session = _build_session(manager)
    service = SessionMemoryService()
    service.set_extraction_opt_out(session, True)

    created = service.extract_memories(session)

    assert created == []
    assert service.list_memories(session) == []


def test_extraction_opt_out_default_is_enabled(tmp_path: Path) -> None:
    """Legacy sessions without the flag must still extract (documented default)."""

    manager = SessionManager(data_dir=tmp_path / "sessions")
    session = _build_session(manager)
    service = SessionMemoryService()

    created = service.extract_memories(session)

    assert len(created) == 1
    assert created[0].source == "extracted"


def test_extraction_opt_out_survives_save_load(tmp_path: Path) -> None:
    """The opt-out flag must persist with the session and survive reload."""

    manager = SessionManager(data_dir=tmp_path / "sessions")
    session = _build_session(manager)
    service = SessionMemoryService()
    service.set_extraction_opt_out(session, True)
    manager.save(session)

    loaded = manager.load(session.id)

    assert service.extraction_opt_out(loaded) is True
    assert service.extract_memories(loaded) == []


def test_extraction_resumes_after_opt_out_cleared(tmp_path: Path) -> None:
    """Clearing the opt-out flag must restore normal extraction."""

    manager = SessionManager(data_dir=tmp_path / "sessions")
    session = _build_session(manager)
    service = SessionMemoryService()
    service.set_extraction_opt_out(session, True)
    service.set_extraction_opt_out(session, False)

    created = service.extract_memories(session)

    assert len(created) == 1
    assert service.extraction_opt_out(session) is False
