"""Tests for the root Tier 2 session and resume commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from henchman.cli.app import _setup_repl_session, cli
from henchman.cli.session_manager import ReplSessionManager
from henchman.core.session import SessionManager, SessionMessage


def _configure_workspace(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Create a deterministic HOME and workspace for CLI session tests."""

    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    home_dir.mkdir()
    project_root.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.chdir(project_root)
    return project_root


def _create_saved_session(*, project_root: Path, tag: str | None = None) -> tuple[SessionManager, str]:
    """Create one saved session for the current project and return its id."""

    manager = SessionManager()
    project_hash = manager.compute_project_hash(project_root)
    session = manager.create_session(project_hash=project_hash, tag=tag)
    session.messages.append(SessionMessage(role="user", content="hello"))
    manager.save(session)
    return manager, session.id


def test_session_list_reports_only_current_project_sessions_as_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The root session list command should default to the current project."""

    runner = CliRunner()
    project_root = _configure_workspace(monkeypatch, tmp_path)
    manager, session_id = _create_saved_session(project_root=project_root, tag="current-project")

    other_project = tmp_path / "other-project"
    other_project.mkdir()
    other_session = manager.create_session(
        project_hash=manager.compute_project_hash(other_project),
        tag="other-project",
    )
    manager.save(other_session)

    result = runner.invoke(cli, ["session", "list", "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["project_hash"] == manager.compute_project_hash(project_root)
    assert [entry["id"] for entry in payload["sessions"]] == [session_id]
    assert payload["sessions"][0]["tag"] == "current-project"


def test_session_switch_marks_the_selected_session_current(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The root session switch command should persist the current session selection."""

    runner = CliRunner()
    project_root = _configure_workspace(monkeypatch, tmp_path)
    manager, session_id = _create_saved_session(project_root=project_root, tag="target")
    project_hash = manager.compute_project_hash(project_root)

    result = runner.invoke(cli, ["session", "switch", session_id, "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["operation"] == "switch"
    assert payload["session_id"] == session_id
    assert manager.get_project_current(project_hash) == session_id


def test_session_delete_removes_the_session_and_clears_current_pointer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deleting a switched session should also clear the stored current-session pointer."""

    runner = CliRunner()
    project_root = _configure_workspace(monkeypatch, tmp_path)
    manager, session_id = _create_saved_session(project_root=project_root, tag="delete-me")
    project_hash = manager.compute_project_hash(project_root)
    manager.set_project_current(project_hash, session_id)

    result = runner.invoke(cli, ["session", "delete", session_id, "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["operation"] == "delete"
    assert payload["session_id"] == session_id
    with pytest.raises(FileNotFoundError):
        manager.load(session_id)
    assert manager.get_project_current(project_hash) is None


def test_resume_marks_the_session_current_and_invokes_chat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The root resume command should select the session and delegate to chat execution."""

    runner = CliRunner()
    project_root = _configure_workspace(monkeypatch, tmp_path)
    manager, session_id = _create_saved_session(project_root=project_root, tag="resume-me")
    project_hash = manager.compute_project_hash(project_root)
    observed: dict[str, Any] = {}

    def _fake_execute_chat_command(config: Any) -> None:
        observed["config"] = config

    monkeypatch.setattr("henchman.cli.app._execute_chat_command", _fake_execute_chat_command)

    result = runner.invoke(cli, ["resume", session_id])

    assert result.exit_code == 0
    assert "config" in observed
    assert manager.get_project_current(project_hash) == session_id


def test_setup_repl_session_uses_the_switched_project_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Interactive startup should reuse the persisted current session when one is selected."""

    project_root = _configure_workspace(monkeypatch, tmp_path)
    manager, session_id = _create_saved_session(project_root=project_root, tag="reused")
    project_hash = manager.compute_project_hash(project_root)
    manager.set_project_current(project_hash, session_id)
    wrapper = ReplSessionManager(session_manager=manager, auto_save=False)

    class FakeRepl:
        def __init__(self) -> None:
            self.session_manager = wrapper
            self.selected_session: Any | None = None

        def set_session(self, session: Any) -> None:
            self.selected_session = session

    repl = FakeRepl()

    _setup_repl_session(repl)

    assert repl.selected_session is not None
    assert repl.selected_session.id == session_id
