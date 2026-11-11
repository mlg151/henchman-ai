"""User review commands exercise persisted content and conflict authority."""

import asyncio
import json
import os
import threading
from io import StringIO
from types import SimpleNamespace

import pytest
from click.testing import CliRunner
from rich.console import Console

from henchman.advanced.checkpoints import CheckpointService
from henchman.cli.commands import CommandContext
from henchman.cli.commands.checkpoint import CheckpointCommand, create_checkpoint_command
from henchman.config.schema import Settings

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX content restore backend")


def captured(tmp_path):
    (tmp_path / "file.txt").write_text("first\nunchanged\nlast\n")
    service = CheckpointService(tmp_path)
    record = service.begin(["file.txt"], actor="engineer")
    (tmp_path / "file.txt").write_text("FIRST\nunchanged\nLAST\n")
    service.complete(record.checkpoint_id)
    return service, record.checkpoint_id


def invoke(command, *args):
    result = CliRunner().invoke(command, list(args))
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_cli_file_hunk_preview_apply_preserves_unselected_edit(tmp_path):
    _, identity = captured(tmp_path)
    command = create_checkpoint_command(project_root=tmp_path)
    assert invoke(command, "list")["checkpoints"][0]["checkpoint_id"] == identity
    review = invoke(command, "show", identity)
    assert len(review["files"][0]["hunks"]) == 2
    plan = invoke(command, "preview", identity, "reject", "--path", "file.txt", "--hunk", "0")
    assert (tmp_path / "file.txt").read_text().startswith("FIRST")
    outcome = invoke(command, "apply", plan["plan_id"])
    assert outcome["invalidate_checks"] is True
    assert (tmp_path / "file.txt").read_text() == "first\nunchanged\nLAST\n"


def test_cli_conflict_is_explicit_and_preserves_user_edit(tmp_path):
    _, identity = captured(tmp_path)
    command = create_checkpoint_command(project_root=tmp_path)
    plan = invoke(command, "preview", identity, "reject")
    (tmp_path / "file.txt").write_text("user edit")
    result = CliRunner().invoke(command, ["apply", plan["plan_id"]])
    assert result.exit_code != 0
    assert "file.txt" in result.output and "conflict" in result.output.lower()
    assert (tmp_path / "file.txt").read_text() == "user edit"


@pytest.mark.parametrize("textual", [False, True])
async def test_interactive_adapter_uses_same_catalog_and_redacts_current_settings(tmp_path, monkeypatch, textual):
    monkeypatch.chdir(tmp_path)
    _, identity = captured(tmp_path)
    (tmp_path / "secret.txt").write_text("rotated-canary")
    service = CheckpointService(tmp_path)
    secret = service.begin(["secret.txt"], actor="engineer")
    service.complete(secret.checkpoint_id)
    runtime = SimpleNamespace(settings=Settings(providers={"deepseek": {"api_key": "rotated-canary"}}))
    if textual:
        runtime.core_context = SimpleNamespace()
    output = StringIO()
    command = CheckpointCommand()
    await command.execute(CommandContext(console=Console(file=output, width=160), repl=runtime,
                                         args=["show", secret.checkpoint_id]))
    assert "rotated-canary" not in output.getvalue()
    assert '"status": "secret"' in output.getvalue()
    output.seek(0)
    output.truncate()
    await command.execute(CommandContext(console=Console(file=output, width=160), repl=runtime,
                                         args=["show", identity]))
    assert identity in output.getvalue()


def test_cli_validation_prevents_ambiguous_hunk_scope_and_discard_is_explicit(tmp_path):
    service, identity = captured(tmp_path)
    command = create_checkpoint_command(project_root=tmp_path)
    result = CliRunner().invoke(command, ["preview", identity, "reject", "--hunk", "0"])
    assert result.exit_code != 0 and "one --path" in result.output
    assert len(service.list_checkpoints()) == 1
    invoke(command, "discard", identity)
    assert service.list_checkpoints() == ()


def test_cli_pending_restore_recovers_after_process_reopen(tmp_path):
    service, identity = captured(tmp_path)
    plan = service.preview(identity, decision="reject")
    service._fault = lambda stage: (_ for _ in ()).throw(RuntimeError("crash")) if stage == "prepared" else None
    with pytest.raises(RuntimeError, match="crash"):
        service.apply(plan.plan_id)
    command = create_checkpoint_command(project_root=tmp_path)
    assert invoke(command, "list")["pending_restores"] == [plan.plan_id]
    assert invoke(command, "recover", plan.plan_id)["changed_paths"] == ["file.txt"]


def test_registered_cli_resolves_project_at_invocation_and_preserves_preview_only(tmp_path, monkeypatch):
    from henchman.cli.app import cli
    from henchman.cli.commands.builtins import get_builtin_commands

    _, identity = captured(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["checkpoint", "show", identity])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["checkpoint_id"] == identity
    assert any(command.name == "checkpoint" for command in get_builtin_commands())


def test_large_review_has_visible_text_truncation_without_changing_plan(tmp_path):
    path = tmp_path / "long.txt"
    path.write_text("a" * 70000)
    service = CheckpointService(tmp_path)
    record = service.begin(["long.txt"], actor="engineer")
    path.write_text("b" * 70000)
    service.complete(record.checkpoint_id)
    command = create_checkpoint_command(project_root=tmp_path)
    review = invoke(command, "show", record.checkpoint_id)
    assert review["files"][0]["hunks"][0]["text_truncated"] is True
    assert len(json.dumps(review)) < 68000
    plan = invoke(command, "preview", record.checkpoint_id, "reject")
    invoke(command, "apply", plan["plan_id"])
    assert path.read_text() == "a" * 70000


async def test_interactive_help_uses_frontend_console(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    output = StringIO()
    await CheckpointCommand().execute(CommandContext(console=Console(file=output), args=["preview", "--help"]))
    assert "--hunk" in output.getvalue()
    assert capsys.readouterr().out == ""


async def test_interactive_cancellation_joins_authorized_restore_worker(monkeypatch):
    from henchman.cli.commands import checkpoint

    entered = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    def apply(**_kwargs):
        entered.set()
        assert release.wait(5)
        finished.set()

    monkeypatch.setattr(checkpoint, "create_checkpoint_command", lambda **_kw: SimpleNamespace(main=apply))
    task = asyncio.create_task(CheckpointCommand().execute(CommandContext(console=Console(file=StringIO()), args=["apply", "id"])))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished.is_set()
