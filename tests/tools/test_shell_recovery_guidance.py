"""Rejected multiline commands receive actionable guidance without execution."""

import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from henchman.tools.builtins.shell import ShellTool


def python_command(code: str) -> str:
    argv = [sys.executable, "-c", code]
    return subprocess.list2cmdline(argv) if os.name == "nt" else shlex.join(argv)


@pytest.mark.parametrize(
    ("separator", "category"),
    [("\n", "control characters"), (r"\n", "embedded newline")],
)
async def test_newline_rejection_guides_recovery_without_echo_or_side_effects(
    tmp_path: Path,
    separator: str,
    category: str,
) -> None:
    marker = tmp_path / "should-not-exist"
    private_text = "PRIVATE_COMMAND_ARGUMENT"
    prefix = python_command(
        f"from pathlib import Path; Path('should-not-exist').touch(); print('{private_text}')"
    )
    command = prefix + separator + "echo never-run"

    result = await ShellTool().execute(command, cwd=str(tmp_path), timeout=5, background=False)

    assert result.success is False
    assert result.error == "Command validation failed"
    assert result.content.startswith("Security validation failed:")
    assert category in result.content
    assert "single line" in result.content
    assert "literal and escaped newlines" in result.content
    assert "python_exec" in result.content and "if allowed" in result.content
    assert command not in result.content
    assert private_text not in result.content
    assert not marker.exists()


@pytest.mark.parametrize(
    ("command", "message"),
    [
        ("", "Command must be a non-empty string"),
        ("echo $(whoami)", "Dangerous pattern detected: command substitution"),
    ],
)
async def test_other_validation_failures_retain_existing_response(
    command: str, message: str
) -> None:
    result = await ShellTool().execute(command)
    assert result.success is False
    assert result.error == "Command validation failed"
    assert result.content == f"Security validation failed: {message}"


async def test_quoted_single_line_command_still_executes_exact_payload(tmp_path: Path) -> None:
    code = "from pathlib import Path; Path('accepted').write_text('a;b&c|d'); print('a;b&c|d')"
    result = await ShellTool().execute(python_command(code), cwd=str(tmp_path), timeout=5, background=False)
    assert result.success, result
    assert result.error is None
    assert result.content.strip() == "a;b&c|d"
    assert (tmp_path / "accepted").read_text() == "a;b&c|d"
