"""Quoted verification snippets must reach the native shell unchanged."""

import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from henchman.tools.base import ToolKind
from henchman.tools.builtins.shell import ShellTool
from henchman.tools.security import CommandInjectionError, sanitize_command


@pytest.mark.parametrize("command", [
    'python -c "value = 4; print(value + 1)"',
    "python -c 'print(3 & 1); print(2 | 1)'",
    'python -c "print(\'a;b&c|d\')"',
    'echo ";"',
    'echo "a;b" && echo "c|d"',
    r'echo one\;two',
    r'echo "a\";b"',
])
def test_default_validation_preserves_quoted_payload(command: str) -> None:
    assert sanitize_command(f"  {command}  ") == command


@pytest.mark.parametrize("command", [
    'python -c "print(1); print(2)',
    'echo "safe; $(whoami)"',
    "echo 'safe; `whoami`'",
    'echo "safe; ${PATH}"',
    'echo "safe; value"\necho another',
    'echo "safe; value" |',
])
def test_whole_command_restrictions_still_reject(command: str) -> None:
    with pytest.raises(CommandInjectionError):
        sanitize_command(command)


@pytest.mark.parametrize("operator", [";", "&&", "||", "|"])
def test_explicit_prefix_policy_still_checks_subcommands(operator: str) -> None:
    allowed = f"echo first {operator} echo second"
    assert sanitize_command(allowed, allowed_commands=["echo"]) == allowed
    with pytest.raises(CommandInjectionError):
        sanitize_command(f"echo first {operator} denied second", allowed_commands=["echo"])


async def test_real_shell_executes_counter_verification(tmp_path: Path) -> None:
    """Reproduce the live rejected snippet against a real isolated fixture."""
    (tmp_path / "counter.py").write_text(
        "class Counter:\n"
        "    def __init__(self, value=0): self.value = value\n"
        "    def increment(self):\n"
        "        self.value += 1\n"
        "        return self.value\n"
        "    def get_count(self): return self.value\n"
        "    def reset(self): self.value = 0\n"
    )
    code = (
        "from counter import Counter; c1 = Counter(5); c2 = Counter(10); "
        "print(c1.increment()); print(c2.get_count()); "
        "c1.reset(); print(c1.get_count());"
    )
    argv = [sys.executable, "-c", code]
    command = subprocess.list2cmdline(argv) if os.name == "nt" else shlex.join(argv)
    tool = ShellTool()
    assert tool.kind is ToolKind.EXECUTE
    result = await tool.execute(command=command, cwd=str(tmp_path), timeout=10, background=False)
    assert result.success, result.content
    assert "6\n10\n0" in result.content.replace("\r\n", "\n")
