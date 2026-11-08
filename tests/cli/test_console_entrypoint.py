"""Regression tests for the installed console entry-point boundary."""

from __future__ import annotations

import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

from henchman.cli import app as cli_app


def _invoke_main(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> tuple[list[str], MagicMock]:
    """Invoke ``main`` with controlled argv and return the parsed boundary state."""

    controlled_argv = list(argv)
    monkeypatch.setattr(sys, "argv", controlled_argv)
    cli = MagicMock()
    cli.commands = cli_app.cli.commands
    with patch.object(cli_app, "cli", cli):
        cli_app.main()
    return controlled_argv, cli


def test_main_routes_no_arguments_to_interactive_chat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No-argument entry points must invoke Click with the chat command."""

    argv, cli = _invoke_main(monkeypatch, ["henchman"])

    assert argv == ["henchman", "chat"]
    cli.assert_called_once_with()


def test_main_routes_no_arguments_through_real_click(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No-argument startup should reach the real chat command parser."""
    monkeypatch.setattr(sys, "argv", ["henchman"])

    with (
        patch.object(cli_app, "_execute_chat_command") as execute_chat,
        pytest.raises(SystemExit) as raised,
    ):
        cli_app.main()

    assert raised.value.code == 0
    config = execute_chat.call_args.args[0]
    assert config.prompt is None


@pytest.mark.parametrize(
    "arguments",
    [
        ["-p", "hello"],
        ["--prompt", "hello"],
        ["--tui"],
        ["--plan"],
    ],
)
def test_main_routes_legacy_chat_options(
    monkeypatch: pytest.MonkeyPatch,
    arguments: list[str],
) -> None:
    """Legacy chat options must be parsed by the chat command."""

    argv, cli = _invoke_main(monkeypatch, ["henchman", *arguments])

    assert argv == ["henchman", "chat", *arguments]
    cli.assert_called_once_with()


def test_main_routes_attached_short_prompt_through_real_click(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The legacy ``-pVALUE`` spelling should reach the real chat parser."""
    monkeypatch.setattr(sys, "argv", ["henchman", "-phello"])

    with (
        patch.object(cli_app, "_execute_chat_command") as execute_chat,
        pytest.raises(SystemExit) as raised,
    ):
        cli_app.main()

    assert raised.value.code == 0
    config = execute_chat.call_args.args[0]
    assert config.prompt == "hello"


def test_main_supports_short_root_help_through_real_click(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The root ``-h`` spelling should render Click help successfully."""
    monkeypatch.setattr(sys, "argv", ["henchman", "-h"])

    with pytest.raises(SystemExit) as raised:
        cli_app.main()

    assert raised.value.code == 0
    output = capsys.readouterr().out
    assert "Usage:" in output
    assert "Henchman-AI" in output


def test_main_preserves_explicit_command_through_real_click(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Explicit subcommands should remain owned by Click's root parser."""
    monkeypatch.setattr(sys, "argv", ["henchman", "doctor", "--help"])

    with pytest.raises(SystemExit) as raised:
        cli_app.main()

    assert raised.value.code == 0
    output = capsys.readouterr().out
    assert "doctor [OPTIONS]" in output
    assert "Inspect environment, configuration, and tool health." in output


@pytest.mark.parametrize("arguments", [["--help"], ["--version"], ["doctor"]])
def test_main_preserves_root_options_and_explicit_commands(
    monkeypatch: pytest.MonkeyPatch,
    arguments: list[str],
) -> None:
    """Root options and explicit commands must reach Click unchanged."""

    argv, cli = _invoke_main(monkeypatch, ["henchman", *arguments])

    assert argv == ["henchman", *arguments]
    cli.assert_called_once_with()


def test_main_preserves_unknown_command_for_click_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown command names must not be silently reinterpreted as chat."""

    argv, cli = _invoke_main(monkeypatch, ["henchman", "not-a-command"])

    assert argv == ["henchman", "not-a-command"]
    cli.assert_called_once_with()


def test_module_entrypoint_rejects_unknown_command() -> None:
    """The real module entry point must return Click's unknown-command error."""

    result = subprocess.run(
        [sys.executable, "-m", "henchman", "not-a-command"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert result.returncode != 0
    assert "No such command 'not-a-command'" in result.stderr


def test_public_cli_does_not_expose_local_xyztest_command() -> None:
    """Diagnostic-only commands must not ship in the user-facing CLI."""

    assert "xyztest" not in cli_app.cli.commands


def test_bootstrap_delegates_legacy_arguments_without_rewriting(monkeypatch):
    from henchman import entrypoint

    argv = ["mlg", "-phello"]
    monkeypatch.setattr(sys, "argv", argv)
    with patch.object(cli_app, "main") as main:
        entrypoint.main()
    main.assert_called_once_with()
    assert sys.argv == argv


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX descriptor isolation")
def test_protocol_bootstrap_isolates_fds_before_cli_import():
    script = r'''
import builtins, json, os, sys, types
from henchman import entrypoint
assert "henchman.cli" not in sys.modules
original = builtins.__import__
def intercept(name, *args, **kwargs):
    if name == "henchman.cli.app":
        pipes = entrypoint.protocol_pipes()
        assert not os.get_inheritable(pipes.input_fd)
        assert not os.get_inheritable(pipes.output_fd)
        assert os.read(0, 100) == b""
        assert sys.stdin.read() == ""
        print("python startup diagnostic")
        os.write(1, b"native startup diagnostic\n")
        assert os.read(pipes.input_fd, 100) == b"owned input\n"
        os.write(pipes.output_fd, b'{"isolated":true}\n')
        return types.SimpleNamespace(main=lambda: None)
    return original(name, *args, **kwargs)
builtins.__import__ = intercept
sys.argv = ["henchman", "headless", "--protocol-version", "1", "--project", "."]
entrypoint.main()
'''
    result = subprocess.run([sys.executable, "-c", script], input=b"owned input\n",
                            capture_output=True, timeout=20, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout == b'{"isolated":true}\n'
    assert b"python startup diagnostic" in result.stderr
    assert b"native startup diagnostic" in result.stderr


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX PTY rejection")
def test_protocol_rejects_tty_before_provider_construction(tmp_path):
    import os
    import pty

    master, slave = pty.openpty()
    try:
        result = subprocess.run([sys.executable, "-m", "henchman", "headless", "--protocol-version", "1", "--project", str(tmp_path)],
                                stdin=slave, capture_output=True, timeout=20, check=False)
    finally:
        os.close(master)
        os.close(slave)
    assert result.returncode == 2 and result.stdout == b""
    assert b"requires piped stdin and stdout" in result.stderr


def test_protocol_explicitly_rejects_unsupported_platform_before_cli_import():
    script = '''
import sys, types
from henchman import entrypoint
entrypoint.os = types.SimpleNamespace(name="nt")
sys.argv = ["henchman", "headless", "--protocol-version", "1", "--project", "."]
try:
    entrypoint.main()
finally:
    assert "henchman.cli" not in sys.modules
'''
    result = subprocess.run([sys.executable, "-c", script], input=b"", capture_output=True, timeout=20, check=False)
    assert result.returncode == 2 and result.stdout == b""
    assert b"requires POSIX pipes" in result.stderr
