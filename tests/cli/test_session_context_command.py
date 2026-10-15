"""Tests for Tier 2 root session/context commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from henchman.cli.app import cli
from henchman.core.session import SessionManager, SessionMessage


def _configure_workspace(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Create an isolated HOME/workspace pair."""

    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    home_dir.mkdir()
    project_root.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.chdir(project_root)
    return project_root


def _create_saved_session(project_root: Path) -> tuple[SessionManager, str]:
    """Create and persist a representative Tier 2 session."""

    manager = SessionManager()
    project_hash = manager.compute_project_hash(project_root)
    session = manager.create_session(project_hash=project_hash, tag="active")
    session.messages = [
        SessionMessage(role="user", content="Prefer JSON output."),
        SessionMessage(
            role="assistant",
            content="Inspecting README.",
            tool_calls=[{"id": "tc1", "name": "read_file", "arguments": {"path": "README.md"}}],
        ),
        SessionMessage(role="tool", content="README contents", tool_call_id="tc1"),
        SessionMessage(role="assistant", content="Preference noted."),
        SessionMessage(role="user", content="Show me the summary."),
        SessionMessage(role="assistant", content="Summary ready."),
    ]
    manager.save(session)
    manager.set_project_current(project_hash, session.id)
    return manager, session.id


def test_context_command_reports_current_session_as_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Context should report snapshot information for the active session."""

    runner = CliRunner()
    project_root = _configure_workspace(monkeypatch, tmp_path)
    _, session_id = _create_saved_session(project_root)

    result = runner.invoke(cli, ["context", "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["session_id"] == session_id
    assert payload["turn_count"] == 2
    assert payload["tool_usage"]["calls_by_name"]["read_file"] == 1


def test_context_playback_renders_recorded_events_as_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Playback should expose the session VCR event stream."""

    runner = CliRunner()
    project_root = _configure_workspace(monkeypatch, tmp_path)
    _, session_id = _create_saved_session(project_root)

    result = runner.invoke(cli, ["context", "playback", "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["session_id"] == session_id
    assert payload["events"][0]["type"] == "message"


def test_compact_command_summarizes_older_turns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compact should preserve recent turns and store a turn summary."""

    runner = CliRunner()
    project_root = _configure_workspace(monkeypatch, tmp_path)
    manager, session_id = _create_saved_session(project_root)

    result = runner.invoke(cli, ["compact", "--preserve-turns", "1", "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["changed"] is True
    assert payload["removed_turns"] == 1
    session = manager.load(session_id)
    assert len(session.turn_summaries) == 1
    assert [message.content for message in session.messages if message.role == "user"] == [
        "Show me the summary."
    ]


def test_rewind_command_removes_the_last_turn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rewind should truncate the active session by complete turns."""

    runner = CliRunner()
    project_root = _configure_workspace(monkeypatch, tmp_path)
    manager, session_id = _create_saved_session(project_root)

    result = runner.invoke(cli, ["rewind", "1", "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["remaining_turns"] == 1
    session = manager.load(session_id)
    assert [message.content for message in session.messages if message.role == "user"] == [
        "Prefer JSON output."
    ]


def test_memory_command_extracts_lists_and_deletes_session_memories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Memory command should manage per-session memories."""

    runner = CliRunner()
    project_root = _configure_workspace(monkeypatch, tmp_path)
    _, _ = _create_saved_session(project_root)

    extracted = runner.invoke(cli, ["memory", "extract", "--format", "json"])
    assert extracted.exit_code == 0
    extracted_payload = json.loads(extracted.output)
    memory_id = extracted_payload["memories"][0]["id"]

    listed = runner.invoke(cli, ["memory", "list", "--format", "json"])
    assert listed.exit_code == 0
    listed_payload = json.loads(listed.output)
    assert listed_payload["memories"][0]["id"] == memory_id

    deleted = runner.invoke(cli, ["memory", "delete", memory_id, "--format", "json"])
    assert deleted.exit_code == 0
    deleted_payload = json.loads(deleted.output)
    assert deleted_payload["deleted"] is True


def test_teleport_command_branches_and_switches_current_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Teleport should branch the session to the requested turn and select it."""

    runner = CliRunner()
    project_root = _configure_workspace(monkeypatch, tmp_path)
    manager, original_session_id = _create_saved_session(project_root)
    project_hash = manager.compute_project_hash(project_root)

    result = runner.invoke(cli, ["teleport", "1", "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["operation"] == "teleport"
    assert payload["session_id"] != original_session_id
    assert manager.get_project_current(project_hash) == payload["session_id"]
    session = manager.load(payload["session_id"])
    assert [message.content for message in session.messages if message.role == "user"] == [
        "Prefer JSON output."
    ]
