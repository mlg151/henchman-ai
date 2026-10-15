"""Shell startup and process lifetime must not assume a Linux host."""

import builtins
import importlib.util
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, mock_open

import pytest

from henchman.tools.builtins import shell


def test_shell_import_without_unix_modules(monkeypatch):
    original_import = builtins.__import__

    def import_without_posix(name, *args, **kwargs):
        if name in {"fcntl", "pty", "termios", "tty"}:
            raise ModuleNotFoundError(f"No module named {name!r}")
        return original_import(name, *args, **kwargs)

    spec = importlib.util.spec_from_file_location("shell_without_posix", shell.__file__)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    monkeypatch.setattr(builtins, "__import__", import_without_posix)
    spec.loader.exec_module(module)
    assert module.ShellTool().name == "shell"


@pytest.mark.parametrize("platform", ["darwin", "win32"])
async def test_non_linux_waits_for_actual_exit(monkeypatch, platform):
    monkeypatch.setattr(shell.sys, "platform", platform)
    read_proc = MagicMock(side_effect=FileNotFoundError)
    monkeypatch.setattr(builtins, "open", read_proc)
    process = SimpleNamespace(pid=12345, returncode=None)

    async def complete_process(_delay):
        process.returncode = 7

    monkeypatch.setattr(shell.asyncio, "sleep", complete_process)
    timed_out, _ = await shell._poll_until_exit(process, timeout=10)
    assert not timed_out
    assert process.returncode == 7
    read_proc.assert_not_called()


def test_linux_without_proc_is_not_evidence_of_exit(monkeypatch):
    monkeypatch.setattr(shell.sys, "platform", "linux")
    monkeypatch.setattr(shell.Path, "is_dir", lambda _path: False)
    monkeypatch.setattr(builtins, "open", MagicMock(side_effect=FileNotFoundError))
    assert not shell._is_process_dead(12345)


@pytest.mark.parametrize("name", ["ordinary", "name with spaces", "name (with) brackets"])
def test_linux_zombie_stat_parses_process_names(monkeypatch, name):
    monkeypatch.setattr(shell.sys, "platform", "linux")
    monkeypatch.setattr(shell.Path, "is_dir", lambda _path: True)
    monkeypatch.setattr(builtins, "open", mock_open(read_data=f"12345 ({name}) Z 1 2 3"))
    assert shell._is_process_dead(12345)


async def test_windows_uses_native_shell_without_posix_sudo_rewrite(monkeypatch):
    monkeypatch.setattr(shell.sys, "platform", "win32")
    monkeypatch.setattr(shell.sys.stdin, "isatty", lambda: False)
    create = AsyncMock()
    monkeypatch.setattr(shell.asyncio, "create_subprocess_shell", create)
    params = shell.ShellParams("sudo echo example", {"MARKER": "kept"}, None, 10)
    await shell._create_process(params, is_sudo=True)
    assert create.call_args.args == (params.command,)
    assert create.call_args.kwargs["env"] == params.env


def test_windows_never_selects_unix_pty(monkeypatch):
    monkeypatch.setattr(shell.sys, "platform", "win32")
    monkeypatch.setattr(shell.sys.stdin, "isatty", lambda: True)
    assert not shell._should_use_interactive_mode(True, is_sudo=True)
