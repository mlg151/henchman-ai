"""Recovery from missing Python source must not interpret other arguments."""

import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from henchman.tools.builtins.python_exec import PythonExecTool


@pytest.mark.parametrize("code", [None, "", " \n\t "])
async def test_missing_source_explains_recovery_without_running_command(
    tmp_path: Path, code: str | None
) -> None:
    """A shell-shaped command remains inert and private when code is missing."""
    marker = tmp_path / "must-not-exist"
    secret = "PRIVATE_ARGUMENT_82e61"
    argv = [
        sys.executable,
        "-c",
        f"from pathlib import Path; Path({str(marker)!r}).touch(); print({secret!r})",
    ]
    command = subprocess.list2cmdline(argv) if os.name == "nt" else shlex.join(argv)
    tool = PythonExecTool()
    if code is None:
        result = await tool.execute(command=command, cwd=str(tmp_path))
    else:
        result = await tool.execute(code=code, command=command, cwd=str(tmp_path))

    assert not result.success
    assert result.error == "Empty code"
    assert result.content.startswith("Error: No code provided")
    assert not marker.exists()
    assert secret not in result.content
    assert command not in result.content
    assert "code" in result.content
    assert "Python source" in result.content
    assert "shell syntax" in result.content
    assert "cwd" in result.content
    assert "shell" in result.content and "if allowed" in result.content


async def test_valid_source_runs_with_cwd_and_stdout(tmp_path: Path) -> None:
    """The documented correction executes Python directly in the requested directory."""
    result = await PythonExecTool().execute(
        background=False,
        code=(
            "from pathlib import Path\n"
            "Path('result.txt').write_text('recovered', encoding='utf-8')\n"
            "print(Path('result.txt').read_text(encoding='utf-8'))\n"
        ),
        cwd=str(tmp_path),
    )

    assert result.success, result.content
    assert result.error is None
    assert result.content == "recovered\n"
    assert (tmp_path / "result.txt").read_text(encoding="utf-8") == "recovered"
