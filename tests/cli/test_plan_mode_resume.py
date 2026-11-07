"""Resuming a Plan Mode session must keep the live registry read-only (#18).

A session persisted with ``plan_mode=True`` carries its read-only boundary
across restarts. Interactive startup re-applies the persisted boundary to
the live tool registry and agent prompt; re-applying is not a new
transition, so the persisted ``plan_mode_origin`` must be preserved.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from henchman.cli.app import RunConfig, _apply_interactive_plan_mode, _setup_repl_session
from henchman.cli.commands.plan import PLAN_MODE_PROMPT
from henchman.cli.session_manager import ReplSessionManager
from henchman.core.session import SessionManager


def _configure_workspace(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Create a deterministic HOME and workspace for CLI session tests."""

    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    home_dir.mkdir()
    project_root.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.chdir(project_root)
    return project_root


def _saved_plan_session(
    project_root: Path, *, origin: str = "user"
) -> tuple[SessionManager, str]:
    """Persist one plan-mode session as the current session for the project."""

    manager = SessionManager()
    project_hash = manager.compute_project_hash(project_root)
    session = manager.create_session(project_hash=project_hash)
    session.plan_mode = True
    session.plan_mode_origin = origin
    manager.save(session)
    manager.set_project_current(project_hash, session.id)
    return manager, session.id


class _FakeToolManager:
    def __init__(self) -> None:
        self.plan_mode_calls: list[bool] = []

    def set_plan_mode(self, *, plan_mode: bool) -> None:
        self.plan_mode_calls.append(plan_mode)


class _FakeAgent:
    def __init__(self) -> None:
        self.system_prompt = "base system prompt"


class _FakeRepl:
    def __init__(self, wrapper: ReplSessionManager) -> None:
        self.session_manager = wrapper
        self.tool_manager = _FakeToolManager()
        self.agent = _FakeAgent()
        self.selected_session: object | None = None

    def set_session(self, session: object) -> None:
        self.selected_session = session
        self.session_manager.set_session(session)


def test_resumed_plan_mode_session_reapplies_read_only_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Restarting into a plan-mode session must re-enable the registry gate."""

    project_root = _configure_workspace(monkeypatch, tmp_path)
    manager, _ = _saved_plan_session(project_root)
    wrapper = ReplSessionManager(session_manager=manager, auto_save=False)
    repl = _FakeRepl(wrapper)

    _setup_repl_session(repl)
    _apply_interactive_plan_mode(repl, RunConfig())  # no --plan flag on restart

    assert repl.selected_session is not None
    assert repl.selected_session.plan_mode is True
    assert repl.tool_manager.plan_mode_calls == [True]
    assert PLAN_MODE_PROMPT in repl.agent.system_prompt


def test_resume_reapply_preserves_persisted_plan_mode_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-applying a persisted boundary must not rewrite its origin."""

    project_root = _configure_workspace(monkeypatch, tmp_path)
    manager, _ = _saved_plan_session(project_root, origin="model")
    wrapper = ReplSessionManager(session_manager=manager, auto_save=False)
    repl = _FakeRepl(wrapper)

    _setup_repl_session(repl)
    _apply_interactive_plan_mode(repl, RunConfig())

    assert repl.selected_session is not None
    assert repl.selected_session.plan_mode_origin == "model"


def test_fresh_session_without_plan_flag_leaves_registry_unrestricted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A new session started without --plan must not gain a plan boundary."""

    _configure_workspace(monkeypatch, tmp_path)
    manager = SessionManager()
    wrapper = ReplSessionManager(session_manager=manager, auto_save=False)
    repl = _FakeRepl(wrapper)

    _setup_repl_session(repl)
    _apply_interactive_plan_mode(repl, RunConfig())

    assert repl.selected_session is not None
    assert repl.selected_session.plan_mode is False
    assert repl.tool_manager.plan_mode_calls == []
    assert PLAN_MODE_PROMPT not in repl.agent.system_prompt
