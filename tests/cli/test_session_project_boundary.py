"""Real CLI/REPL session selectors cannot cross project boundaries by ID."""

from io import StringIO
from pathlib import Path
from unittest.mock import Mock

import pytest
from click.testing import CliRunner
from rich.console import Console

from henchman.cli.app import _setup_repl_session, cli
from henchman.cli.commands import CommandContext
from henchman.cli.commands.chat import ChatCommand
from henchman.cli.commands.session import SessionCommand
from henchman.cli.session_manager import ReplSessionManager
from henchman.core.session import Session, SessionManager, SessionMessage
from henchman.core.session_memory import SessionMemoryService

Workspace = tuple[SessionManager, str, Session]


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Workspace:
    home = tmp_path / "home"
    home.mkdir()
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.chdir(project)
    manager = SessionManager()
    project_hash = manager.compute_project_hash(project)
    foreign = manager.create_session("other-project", tag="private-tag")
    foreign.messages.append(SessionMessage(role="user", content="PRIVATE OTHER PROJECT"))
    manager.save(foreign)
    return manager, project_hash, foreign


@pytest.mark.parametrize("command", [["resume"], ["session", "switch"], ["session", "delete"]])
def test_root_selectors_cannot_access_foreign_session(
    workspace: Workspace, command: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    manager, project_hash, foreign = workspace
    execute = Mock()
    monkeypatch.setattr("henchman.cli.app._execute_chat_command", execute)
    result = CliRunner().invoke(cli, [*command, foreign.id])
    assert result.exit_code != 0
    assert "current project" in result.output
    assert "PRIVATE" not in result.output
    assert manager.get_project_current(project_hash) is None
    assert manager.load(foreign.id).tag == "private-tag"
    execute.assert_not_called()


def test_startup_cannot_activate_foreign_pointer(workspace: Workspace) -> None:
    manager, project_hash, foreign = workspace
    manager.set_project_current(project_hash, foreign.id)
    repl = Mock()
    repl.session_manager = ReplSessionManager(manager)
    _setup_repl_session(repl)
    restored = repl.set_session.call_args.args[0]
    assert restored.project_hash == project_hash
    assert restored.id != foreign.id


@pytest.mark.parametrize("subcommand", ["resume", "export", "branch", "merge", "template"])
async def test_slash_commands_reject_foreign_sessions(
    workspace: Workspace, subcommand: str
) -> None:
    manager, project_hash, foreign = workspace
    output = StringIO()
    args = {
        "resume": ["resume", foreign.id],
        "export": ["export", foreign.id, "markdown"],
        "branch": ["branch", foreign.id, "1"],
        "merge": ["merge", foreign.id, foreign.id],
        "template": ["template", "save", foreign.id, "leak"],
    }[subcommand]
    ctx = CommandContext(
        args=args,
        console=Console(file=output),
        session_manager=manager,
        project_hash=project_hash,
        repl=Mock(),
        agent=Mock(),
    )
    command = ChatCommand() if subcommand == "resume" else SessionCommand()
    await command.execute(ctx)
    assert "not found" in output.getvalue().lower()
    assert "PRIVATE" not in output.getvalue()
    assert len(manager.list_sessions()) == 1
    assert not (manager.data_dir / "templates").exists()
    ctx.repl.set_session.assert_not_called()


def test_memory_command_cannot_follow_foreign_pointer(workspace: Workspace) -> None:
    manager, project_hash, foreign = workspace
    SessionMemoryService().add_memory(foreign, content="PRIVATE MEMORY CANARY")
    manager.save(foreign)
    own = manager.create_session(project_hash)
    manager.save(own)
    manager.set_project_current(project_hash, foreign.id)
    result = CliRunner().invoke(cli, ["memory", "list", "--format", "json"])
    assert result.exit_code == 0, result.output
    assert "PRIVATE" not in result.output
    assert manager.get_project_current(project_hash) == own.id


@pytest.mark.parametrize("action", ["list", "create", "delete"])
async def test_slash_templates_do_not_expose_foreign_copies(
    workspace: Workspace, action: str
) -> None:
    manager, project_hash, foreign = workspace
    template = manager.save_template(foreign.id, "PRIVATE TEMPLATE CANARY")
    output = StringIO()
    args = ["template", action] + ([] if action == "list" else [template["id"]])
    ctx = CommandContext(
        args=args, console=Console(file=output), session_manager=manager, project_hash=project_hash
    )
    await SessionCommand().execute(ctx)
    assert "PRIVATE" not in output.getvalue()
    assert len(manager.list_templates()) == 1
    assert len(manager.list_sessions()) == 1


async def test_explicit_file_import_transfers_a_copy_to_current_project(
    workspace: Workspace, tmp_path: Path
) -> None:
    manager, project_hash, foreign = workspace
    transfer = tmp_path / "export.json"
    transfer.write_text(foreign.to_json(), encoding="utf-8")
    output = StringIO()
    ctx = CommandContext(
        args=["import", str(transfer)],
        console=Console(file=output),
        session_manager=manager,
        project_hash=project_hash,
    )
    await SessionCommand().execute(ctx)
    copied = manager.list_sessions(project_hash)
    assert len(copied) == 1
    assert copied[0].id != foreign.id
    assert manager.load(copied[0].id, project_hash=project_hash).messages == foreign.messages
    assert manager.load(foreign.id).project_hash == "other-project"
