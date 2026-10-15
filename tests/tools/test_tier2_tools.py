"""Tests for Tier 2 builtin tools."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from henchman.cli.session_manager import ReplSessionManager
from henchman.cli.tool_manager import ToolManager
from henchman.core.session import SessionManager
from henchman.tools.builtins import EnterWorktreeTool, ExitWorktreeTool


def _init_git_repo(tmp_path: Path) -> Path:
    """Create a git repository with one commit for worktree tests."""

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test User",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-m",
            "init",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return repo


@pytest.mark.anyio
async def test_tool_manager_plan_mode_tools_toggle_runtime_state(tmp_path: Path) -> None:
    """Plan-mode tools should toggle both registry and current session state."""

    tool_manager = ToolManager()
    tool_manager.register_builtin_tools()

    backing_manager = SessionManager(data_dir=tmp_path / "sessions")
    wrapper = ReplSessionManager(session_manager=backing_manager, auto_save=False)
    session = backing_manager.create_session(project_hash="abc123")
    wrapper.set_session(session)
    tool_manager.bind_runtime(session_manager=wrapper, project_root=tmp_path)

    enabled = await tool_manager.registry.execute("enter_plan_mode", {})
    disabled = await tool_manager.registry.execute("exit_plan_mode", {})

    assert enabled.success is True
    assert disabled.success is True
    assert tool_manager.registry._plan_mode is False
    assert wrapper.current is not None
    assert wrapper.current.plan_mode is False


@pytest.mark.anyio
async def test_worktree_tools_add_and_remove_worktree(tmp_path: Path) -> None:
    """Worktree tools should create and remove an isolated git worktree."""

    repo = _init_git_repo(tmp_path)
    worktree_path = tmp_path / "repo-feature"

    enter_tool = EnterWorktreeTool(project_root=repo)
    enter_result = await enter_tool.execute(path=str(worktree_path), branch="feature/tier2")

    assert enter_result.success is True
    assert worktree_path.exists()

    exit_tool = ExitWorktreeTool(project_root=repo)
    exit_result = await exit_tool.execute(path=str(worktree_path))

    assert exit_result.success is True
    assert not worktree_path.exists()


def test_builtin_surface_includes_tier2_tools() -> None:
    """The builtin tool surface should expose the Tier 2 tools."""

    import henchman.tools.builtins as builtins_mod

    def _instantiate(tool_class: object) -> object:
        if tool_class is builtins_mod.ShellTool:
            return builtins_mod.ShellTool(default_timeout=60)
        if tool_class is builtins_mod.RagSearchTool:
            from unittest.mock import MagicMock

            return builtins_mod.RagSearchTool(store=MagicMock())
        return tool_class()

    names = {_instantiate(tool_class).name for tool_class in builtins_mod.iter_available_builtin_tool_classes()}

    assert {"enter_plan_mode", "exit_plan_mode", "enter_worktree", "exit_worktree"} <= names
