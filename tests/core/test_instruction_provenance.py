"""Persisted instruction provenance for sessions and delegation handoffs."""

from pathlib import Path

import pytest

from henchman.config.context import ContextLoader, ContextSnapshot
from henchman.core.instruction_provenance import (
    INSTRUCTION_PROVENANCE_KEY,
    InstructionProvenanceService,
    render_delegation_appendix,
)
from henchman.core.session_data import Session


def _session() -> Session:
    return Session(
        id="session_provenance",
        project_hash="abc123",
        started="2026-11-04T00:00:00Z",
        last_updated="2026-11-04T00:00:00Z",
    )


@pytest.fixture
def snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ContextSnapshot:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    project = (tmp_path / "project").resolve()
    project.mkdir()
    (project / ".git").mkdir()
    (project / "HENCHMAN.md").write_text("Root project instructions", encoding="utf-8")
    child = project / "child"
    child.mkdir()
    (child / "AGENTS.md").write_text("Child agent instructions", encoding="utf-8")
    return ContextLoader(start_dir=child).load_snapshot()


def test_capture_persists_provenance_without_content(snapshot: ContextSnapshot) -> None:
    session = _session()
    service = InstructionProvenanceService()

    record = service.capture(session, snapshot)

    stored = session.export_metadata[INSTRUCTION_PROVENANCE_KEY]
    assert stored == record
    assert record["version"] == 1
    assert record["digest"] == snapshot.digest
    assert [source["path"] for source in record["sources"]] == [
        str(source.path) for source in snapshot.sources
    ]
    # Provenance records carry hashes and sizes, never instruction text.
    assert all("content" not in source for source in record["sources"])
    assert "Root project instructions" not in str(stored)


def test_captured_provenance_survives_serialization_roundtrip(snapshot: ContextSnapshot) -> None:
    session = _session()
    InstructionProvenanceService().capture(session, snapshot)

    restored = Session.from_dict(session.to_dict())

    record = InstructionProvenanceService().get(restored)
    assert record is not None
    assert record["digest"] == snapshot.digest
    assert [source["order"] for source in record["sources"]] == [0, 1]


def test_get_returns_none_when_absent(snapshot: ContextSnapshot) -> None:
    del snapshot
    assert InstructionProvenanceService().get(_session()) is None


def test_get_rejects_malformed_record() -> None:
    session = _session()
    session.export_metadata[INSTRUCTION_PROVENANCE_KEY] = {"version": 2}

    with pytest.raises(ValueError, match="version"):
        InstructionProvenanceService().get(session)


def test_capture_overwrites_stale_provenance(snapshot: ContextSnapshot) -> None:
    session = _session()
    service = InstructionProvenanceService()
    service.capture(session, snapshot)

    session.export_metadata[INSTRUCTION_PROVENANCE_KEY]["digest"] = "stale"
    service.capture(session, snapshot)

    assert session.export_metadata[INSTRUCTION_PROVENANCE_KEY]["digest"] == snapshot.digest


def test_delegation_appendix_lists_provenance_not_content(snapshot: ContextSnapshot) -> None:
    appendix = render_delegation_appendix(snapshot)

    assert "Project instruction provenance" in appendix
    for source in snapshot.sources:
        assert str(source.path) in appendix
    assert "Root project instructions" not in appendix
    assert "Child agent instructions" not in appendix
    assert "tool policy" in appendix
