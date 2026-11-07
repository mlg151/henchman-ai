"""Startup must surface storage failures instead of silently abandoning history."""

import json
from pathlib import Path
from unittest.mock import Mock

import click
import pytest

from henchman.cli.app import _setup_repl_session
from henchman.cli.session_manager import ReplSessionManager
from henchman.core.session import SessionManager


@pytest.mark.parametrize("damage", ["corrupt", "future-version"])
def test_startup_reports_unrecoverable_session_without_new_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str
) -> None:
    monkeypatch.chdir(tmp_path)
    manager = SessionManager(tmp_path / "sessions")
    project_hash = manager.compute_project_hash(tmp_path)
    session = manager.create_session(project_hash)
    path = manager.save(session)
    manager.set_project_current(project_hash, session.id)
    if damage == "corrupt":
        path.write_text('{"id":', encoding="utf-8")
    else:
        payload = json.loads(path.read_text())
        payload["_storage"]["version"] = 999
        path.write_text(json.dumps(payload), encoding="utf-8")
    original = path.read_bytes()
    repl = Mock()
    repl.session_manager = ReplSessionManager(manager)
    with pytest.raises(click.ClickException, match="Cannot resume saved session"):
        _setup_repl_session(repl)
    repl.set_session.assert_not_called()
    assert path.read_bytes() == original
    assert manager.get_project_current(project_hash) == session.id
