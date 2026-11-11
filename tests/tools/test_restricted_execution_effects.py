"""Unmediated process arguments cannot weaken the effective execution boundary."""

import re
import shutil
from pathlib import Path

import pytest

from henchman.advanced.tasks import TaskService
from henchman.tools.base import ToolKind
from henchman.tools.builtins.python_exec import PythonExecTool
from henchman.tools.builtins.shell import ShellTool
from henchman.tools.registry import ToolRegistry
from henchman.tools.security.shell_secure import SecureShellTool, ShellSecurityConfig


@pytest.mark.parametrize("command", [
    "sort input -o output", "sort --output=output input", "sort -rooutput input",
    "sort --compress-program=helper input", "sort input",
])
def test_sort_retains_execute_effect(command):
    # Even ordinary sort may spill temporary files or invoke a compression helper.
    assert ShellTool().execution_kind({"command": command}) is ToolKind.EXECUTE


@pytest.mark.skipif(shutil.which("sort") is None, reason="sort unavailable")
async def test_plan_mode_cannot_write_through_sort_output(tmp_path):
    source = tmp_path / "input"
    destination = tmp_path / "output"
    source.write_text("b\na\n")
    registry = ToolRegistry()
    registry.register(ShellTool())
    registry.set_plan_mode(enabled=True)
    result = await registry.execute("shell", {
        "command": f'sort "{source}" -o "{destination}"', "background": False,
    })
    assert not destination.exists()
    assert not result.success
    assert result.error == "Tool disabled in Plan Mode"


@pytest.mark.parametrize("background", [False, True])
async def test_pure_python_ignores_inherited_startup_hooks(tmp_path, monkeypatch, background):
    marker = tmp_path / "startup-ran"
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    (hooks / "sitecustomize.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('startup')\n"
    )
    monkeypatch.setenv("PYTHONPATH", str(hooks))
    monkeypatch.setenv("PYTHONIOENCODING", "ascii")
    tool = PythonExecTool()
    tool.bind_runtime(project_root=tmp_path)
    registry = ToolRegistry()
    registry.register(tool)
    registry.set_plan_mode(enabled=True)
    result = await registry.execute("python_exec", {
        "code": "print('café 世界', 1 + 2)", "background": background, "cwd": str(hooks),
    })
    assert result.success, result.content
    if background:
        task_id = re.search(r"task-[0-9a-f]+", result.content).group()
        service = TaskService(tmp_path)
        record = await service.wait_for_task(task_id, timeout=5)
        assert record.status == "completed"
        output = service.tail_output(task_id)
    else:
        output = result.content
    assert "café 世界 3" in output
    assert not marker.exists()


@pytest.mark.parametrize("level", ["strict", "moderate", "permissive"])
async def test_secure_shell_level_cannot_expand_configured_commands(tmp_path: Path, level):
    marker = tmp_path / "outside-contract"
    tool = SecureShellTool(config=ShellSecurityConfig(
        allowed_commands={"cat"}, allowed_directories={str(tmp_path)},
    ))
    result = await tool.execute(
        command=f'touch "{marker}"', cwd=str(tmp_path), security_level=level, background=False,
    )
    assert not marker.exists()
    assert not result.success


async def test_comprehension_cannot_alias_open_to_a_pure_builtin(tmp_path):
    marker = tmp_path / "aliased-write"
    code = f"print([print({str(marker)!r}, 'w') for print in [open]])"
    registry = ToolRegistry()
    registry.register(PythonExecTool())
    registry.set_plan_mode(enabled=True)
    result = await registry.execute("python_exec", {"code": code, "background": False})
    assert not marker.exists()
    assert not result.success
    assert result.error == "Tool disabled in Plan Mode"
