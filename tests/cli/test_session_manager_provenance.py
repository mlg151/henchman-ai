"""ReplSessionManager captures instruction provenance when sessions attach."""

from pathlib import Path

import pytest

from henchman.cli.session_manager import ReplSessionManager
from henchman.config.context import ContextLoader, ContextSnapshot
from henchman.core.instruction_provenance import INSTRUCTION_PROVENANCE_KEY
from henchman.core.session_manager import SessionManager


@pytest.fixture
def snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ContextSnapshot:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    project = (tmp_path / "project").resolve()
    project.mkdir()
    (project / ".git").mkdir()
    (project / "AGENTS.md").write_text("Repository instructions", encoding="utf-8")
    return ContextLoader(start_dir=project).load_snapshot()


def test_set_session_captures_instruction_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, snapshot: ContextSnapshot,
) -> None:
    home = tmp_path / "home2"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    core = SessionManager(data_dir=tmp_path / "sessions")
    manager = ReplSessionManager(
        session_manager=core, auto_save=False, instruction_snapshot=snapshot,
    )
    session = core.create_session("project-hash")

    manager.set_session(session)

    record = session.export_metadata.get(INSTRUCTION_PROVENANCE_KEY)
    assert record is not None
    assert record["digest"] == snapshot.digest


def test_set_session_without_snapshot_leaves_metadata(
    tmp_path: Path, snapshot: ContextSnapshot,
) -> None:
    del snapshot
    core = SessionManager(data_dir=tmp_path / "sessions")
    manager = ReplSessionManager(session_manager=core, auto_save=False)
    session = core.create_session("project-hash")

    manager.set_session(session)

    assert INSTRUCTION_PROVENANCE_KEY not in session.export_metadata
