"""Tests for the guided Tier 1 upgrade command."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner


def _build_system_info(install_method: str):
    from henchman.cli.system_info import RuntimeSnapshot, get_system_info

    def _resolve_command(command: str) -> str | None:
        if install_method == "uv-missing":
            return f"/usr/bin/{command}" if command == "pipx" else None
        if install_method == "pipx-missing":
            return f"/usr/bin/{command}" if command == "uv" else None
        return f"/usr/bin/{command}" if command != "pip" else None

    snapshot = RuntimeSnapshot(
        executable_path="/workspace/.venv/bin/henchman",
        python_executable="/workspace/.venv/bin/python",
        environment={},
    )

    if install_method in {"uv", "uv-missing"}:
        snapshot = RuntimeSnapshot(
            executable_path="/home/test/.local/bin/henchman",
            python_executable="/home/test/.local/share/uv/tools/henchman-ai/bin/python",
            environment={"UV_TOOL_BIN_DIR": "/home/test/.local/bin"},
        )
    elif install_method in {"pipx", "pipx-missing"}:
        snapshot = RuntimeSnapshot(
            executable_path="/home/test/.local/pipx/venvs/henchman-ai/bin/henchman",
            python_executable="/home/test/.local/pipx/venvs/henchman-ai/bin/python",
            environment={"PIPX_HOME": "/home/test/.local/pipx"},
        )
    elif install_method == "unknown":
        snapshot = RuntimeSnapshot(
            executable_path=str(Path("/usr/local/bin/henchman")),
            python_executable=str(Path("/usr/bin/python3")),
            environment={},
        )
    elif install_method == "ambiguous":
        snapshot = RuntimeSnapshot(
            executable_path="/home/test/.local/pipx/venvs/henchman-ai/bin/henchman",
            python_executable="/home/test/.local/share/uv/tools/henchman-ai/bin/python",
            environment={
                "PIPX_HOME": "/home/test/.local/pipx",
                "UV_TOOL_BIN_DIR": "/home/test/.local/bin",
            },
        )

    return get_system_info(snapshot=snapshot, command_resolver=_resolve_command)


def test_upgrade_command_explains_supported_upgrade_without_executing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from henchman.cli.commands.upgrade_command import upgrade_command

    runner = CliRunner()

    monkeypatch.setattr(
        "henchman.cli.commands.upgrade_command.get_system_info",
        lambda: _build_system_info("pip"),
    )

    def _unexpected_run(*_: object, **__: object) -> None:
        msg = "subprocess.run should not be called in explain-only mode"
        raise AssertionError(msg)

    monkeypatch.setattr("henchman.cli.commands.upgrade_command.subprocess.run", _unexpected_run)

    result = runner.invoke(upgrade_command, [])

    assert result.exit_code == 0
    assert "/workspace/.venv/bin/python -m pip install --upgrade henchman-ai" in result.output
    assert "Re-run with --run to execute this command." in result.output


def test_upgrade_command_executes_after_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from henchman.cli.commands.upgrade_command import upgrade_command

    runner = CliRunner()
    executed: list[tuple[tuple[object, ...], dict[str, object]]] = []

    monkeypatch.setattr(
        "henchman.cli.commands.upgrade_command.get_system_info",
        lambda: _build_system_info("uv"),
    )

    def _run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        executed.append((args, kwargs))
        return subprocess.CompletedProcess(args=args[0], returncode=0)

    monkeypatch.setattr("henchman.cli.commands.upgrade_command.subprocess.run", _run)

    result = runner.invoke(upgrade_command, ["--run"], input="y\n")

    assert result.exit_code == 0
    assert executed == [
        (
            (("uv", "tool", "upgrade", "henchman-ai"),),
            {"check": False, "capture_output": True, "text": True},
        )
    ]
    assert "Run this command now?" in result.output
    assert "Upgrade command completed successfully." in result.output


def test_upgrade_command_falls_back_to_manual_guidance_for_unknown_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from henchman.cli.commands.upgrade_command import upgrade_command

    runner = CliRunner()

    monkeypatch.setattr(
        "henchman.cli.commands.upgrade_command.get_system_info",
        lambda: _build_system_info("unknown"),
    )

    def _unexpected_run(*_: object, **__: object) -> None:
        msg = "subprocess.run should not be called for manual fallback"
        raise AssertionError(msg)

    monkeypatch.setattr("henchman.cli.commands.upgrade_command.subprocess.run", _unexpected_run)

    result = runner.invoke(upgrade_command, ["--run"], input="y\n")

    assert result.exit_code == 0
    assert "HMN_UPGRADE_INSTALL_METHOD_UNKNOWN" in result.output
    assert "manual upgrade guidance" in result.output.lower()
    assert "Run this command now?" not in result.output


def test_upgrade_command_emits_code_for_ambiguous_install_detection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from henchman.cli.commands.upgrade_command import upgrade_command

    runner = CliRunner()

    monkeypatch.setattr(
        "henchman.cli.commands.upgrade_command.get_system_info",
        lambda: _build_system_info("ambiguous"),
    )

    def _unexpected_run(*_: object, **__: object) -> None:
        msg = "subprocess.run should not be called for manual fallback"
        raise AssertionError(msg)

    monkeypatch.setattr("henchman.cli.commands.upgrade_command.subprocess.run", _unexpected_run)

    result = runner.invoke(upgrade_command, ["--run"], input="y\n")

    assert result.exit_code == 0
    assert "HMN_UPGRADE_INSTALL_METHOD_UNKNOWN" in result.output
    assert "manual upgrade guidance" in result.output.lower()
    assert "Run this command now?" not in result.output


@pytest.mark.parametrize("install_method", ["uv-missing", "pipx-missing"])
def test_upgrade_command_falls_back_to_manual_guidance_when_manager_is_missing(
    install_method: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from henchman.cli.commands.upgrade_command import upgrade_command

    runner = CliRunner()

    monkeypatch.setattr(
        "henchman.cli.commands.upgrade_command.get_system_info",
        lambda: _build_system_info(install_method),
    )

    def _unexpected_run(*_: object, **__: object) -> None:
        msg = "subprocess.run should not be called when the manager executable is missing"
        raise AssertionError(msg)

    monkeypatch.setattr("henchman.cli.commands.upgrade_command.subprocess.run", _unexpected_run)

    result = runner.invoke(upgrade_command, ["--run"], input="y\n")

    assert result.exit_code == 0
    assert "manual upgrade guidance" in result.output.lower()
    assert "executable is unavailable" in result.output
    assert "Run this command now?" not in result.output


def test_upgrade_command_declines_execution_without_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from henchman.cli.commands.upgrade_command import upgrade_command

    runner = CliRunner()
    executed = False

    monkeypatch.setattr(
        "henchman.cli.commands.upgrade_command.get_system_info",
        lambda: _build_system_info("pipx"),
    )

    def _run(*args: object, **__: object) -> subprocess.CompletedProcess[str]:
        nonlocal executed
        executed = True
        return subprocess.CompletedProcess(args=args[0], returncode=0)

    monkeypatch.setattr("henchman.cli.commands.upgrade_command.subprocess.run", _run)

    result = runner.invoke(upgrade_command, ["--run"], input="n\n")

    assert result.exit_code == 0
    assert executed is False
    assert "Upgrade cancelled." in result.output


def test_upgrade_command_surfaces_sanitized_failure_excerpt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from henchman.cli.commands.upgrade_command import upgrade_command

    runner = CliRunner()

    monkeypatch.setattr(
        "henchman.cli.commands.upgrade_command.get_system_info",
        lambda: _build_system_info("pip"),
    )

    def _run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert args == (
            ("/workspace/.venv/bin/python", "-m", "pip", "install", "--upgrade", "henchman-ai"),
        )
        assert kwargs == {"check": False, "capture_output": True, "text": True}
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=2,
            stdout="line one\nline two",
            stderr="bad news\twith control\x00chars",
        )

    monkeypatch.setattr("henchman.cli.commands.upgrade_command.subprocess.run", _run)

    result = runner.invoke(upgrade_command, ["--run"], input="y\n")

    assert result.exit_code == 1
    assert "Upgrade command failed with exit code 2." in result.output
    assert "stderr: bad news with control chars" in result.output
    assert "stdout: line one line two" in result.output


def test_upgrade_command_surfaces_sanitized_oserror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from henchman.cli.commands.upgrade_command import upgrade_command

    runner = CliRunner()

    monkeypatch.setattr(
        "henchman.cli.commands.upgrade_command.get_system_info",
        lambda: _build_system_info("pipx"),
    )

    def _run(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        raise OSError("missing\nbinary\x00name")

    monkeypatch.setattr("henchman.cli.commands.upgrade_command.subprocess.run", _run)

    result = runner.invoke(upgrade_command, ["--run"], input="y\n")

    assert result.exit_code == 1
    assert "Failed to execute upgrade command: missing binary name" in result.output


def test_render_update_command_uses_shared_sanitization() -> None:
    from henchman.cli.update_check import render_update_command
    from henchman.tools.security import CommandInjectionError

    with pytest.raises(CommandInjectionError, match="command substitution"):
        render_update_command(("python", "-m", "pip", "install", "--upgrade", "henchman-$(whoami)"))
