"""Real subprocess coverage for concurrently tracked execution tools."""

from __future__ import annotations

import asyncio
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from henchman.advanced import TaskService
from henchman.tools.builtins.python_exec import PythonExecTool
from henchman.tools.builtins.shell import ShellTool


def _task_id(content: str) -> str:
    match = re.search(r"task-[0-9a-f]+", content)
    assert match is not None, content
    return match.group()


def _python_command(code: str) -> str:
    argv = [sys.executable, "-u", "-c", code]
    return subprocess.list2cmdline(argv) if os.name == "nt" else shlex.join(argv)


@pytest.mark.anyio
async def test_mixed_jobs_return_before_completion_and_remain_independent(tmp_path: Path) -> None:
    """Starting another shell/Python job must not replace or wait for an active job."""
    from henchman.cli.tool_manager import ToolManager

    manager = ToolManager()
    manager.bind_runtime(project_root=tmp_path)
    manager.register_builtin_tools()
    service = TaskService(tmp_path)
    code = "import time; print('started', flush=True); time.sleep(30)"
    command = _python_command(code)
    ids: list[str] = []
    try:
        for name, params in (("shell", {"command": command}), ("python_exec", {"code": code}),
                             ("shell", {"command": command}), ("python_exec", {"code": code})):
            result = await asyncio.wait_for(manager.registry.execute(name, params), timeout=2)
            assert result.success, result.content
            ids.append(_task_id(result.content))
        assert len(set(ids)) == 4
        assert len(service.list_tasks(status="running")) == 4
        listed = await manager.registry.execute("task_list", {})
        assert all(task_id in listed.content for task_id in ids)
        async with asyncio.timeout(5):
            while not all("started" in service.tail_output(task_id) for task_id in ids):
                await asyncio.sleep(0.01)
        await manager.registry.execute("task_stop", {"task_id": ids[0]})
        assert service.get_task(ids[0]).status == "stopped"
        assert all(service.get_task(task_id).status == "running" for task_id in ids[1:])
    finally:
        for task_id in ids:
            await service.stop_task(task_id)


@pytest.mark.anyio
async def test_python_background_output_environment_and_working_directory(tmp_path: Path) -> None:
    """Background Python preserves code whitespace and returns readable UTF-8 output."""
    tool = PythonExecTool()
    tool.bind_runtime(project_root=tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    result = await tool.execute(
        code="\nimport os\nprint('café 世界')\nprint(os.getcwd())\n", cwd=str(work), timeout=0,
    )
    service = TaskService(tmp_path)
    task_id = _task_id(result.content)
    record = await service.wait_for_task(task_id, timeout=5)
    assert record.status == "completed"
    output = service.tail_output(task_id)
    assert "café 世界" in output
    assert str(work) in output


@pytest.mark.anyio
async def test_background_timeout_is_recorded_and_process_reaped(tmp_path: Path) -> None:
    """A background timeout must finish the task without requiring a user stop."""
    tool = PythonExecTool()
    tool.bind_runtime(project_root=tmp_path)
    result = await tool.execute(code="import time; time.sleep(30)", timeout=1)
    service = TaskService(tmp_path)
    record = await service.wait_for_task(_task_id(result.content), timeout=5)
    assert record.status == "failed"
    assert record.pid is None
    assert "timed out" in service.tail_output(record.task_id).lower()


@pytest.mark.anyio
async def test_service_preserves_exact_arguments_and_environment(tmp_path: Path) -> None:
    """Arguments, including an empty argument, are data and cannot be stripped."""
    service = TaskService(tmp_path)
    record = await service.start_task(
        argv=[sys.executable, "-c", "import os, sys; print(repr(sys.argv[1:])); print(os.getenv('MARKER'))", " x ", ""],
        env={**os.environ, "MARKER": "kept"},
    )
    await service.wait_for_task(record.task_id, timeout=5)
    assert "[' x ', '']" in service.tail_output(record.task_id)
    assert "kept" in service.tail_output(record.task_id)


@pytest.mark.anyio
async def test_launch_failure_returns_error_and_creates_no_running_task(tmp_path: Path) -> None:
    """A failed launch must not tell the agent a job is running."""
    tool = PythonExecTool()
    tool.bind_runtime(project_root=tmp_path)
    result = await tool.execute(code="print(1)", cwd=str(tmp_path / "absent"))
    assert not result.success
    assert TaskService(tmp_path).list_tasks(status="running") == []


@pytest.mark.anyio
async def test_background_nonzero_exit_is_visible_to_tracking_tools(tmp_path: Path) -> None:
    """Task tools bound by ToolManager must see Python jobs and their failure output."""
    from henchman.cli.tool_manager import ToolManager

    manager = ToolManager()
    manager.bind_runtime(project_root=tmp_path)
    manager.register_builtin_tools()
    launched = await manager.registry.execute("python_exec", {"code": "raise ValueError('broken')"})
    task_id = _task_id(launched.content)
    record = await TaskService(tmp_path).wait_for_task(task_id, timeout=5)
    assert record.status == "failed"
    status = await manager.registry.execute("task_get", {"task_id": task_id})
    output = await manager.registry.execute("task_output", {"task_id": task_id})
    assert "failed" in status.content
    assert "ValueError: broken" in output.content


@pytest.mark.anyio
async def test_cancelled_monitor_reaps_process_and_finalizes_record(tmp_path: Path) -> None:
    """Event loop shutdown must not leave owned subprocesses running."""
    service = TaskService(tmp_path)
    record = await service.start_task(argv=[sys.executable, "-c", "import time; time.sleep(30)"])
    monitor = service._runtime.monitors[record.task_id]
    process = service._runtime.processes[record.task_id]
    monitor.cancel()
    with pytest.raises(asyncio.CancelledError):
        await monitor
    final = await service.wait_for_task(record.task_id, timeout=5)
    assert final.status == "stopped"
    assert final.pid is None
    assert process.returncode is not None


@pytest.mark.anyio
@pytest.mark.skipif(os.name != "posix", reason="POSIX process group lifecycle")
async def test_stopping_shell_also_stops_its_descendant(tmp_path: Path) -> None:
    """Stopping the shell task must stop a child that ignores SIGTERM."""
    tool = ShellTool()
    tool.bind_runtime(project_root=tmp_path)
    code = (
        "import signal,time; from pathlib import Path; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "Path('ready').touch(); time.sleep(1); Path('escaped').touch(); time.sleep(30)"
    )
    command = _python_command(code)
    result = await tool.execute(command=command)
    service = TaskService(tmp_path)
    task_id = _task_id(result.content)
    try:
        async with asyncio.timeout(5):
            while not (tmp_path / "ready").exists():
                await asyncio.sleep(0.01)
        await service.stop_task(task_id)
        await asyncio.sleep(1.1)
        assert not (tmp_path / "escaped").exists()
        assert (await service.wait_for_task(task_id)).pid is None
    finally:
        await service.stop_task(task_id)


@pytest.mark.anyio
async def test_secure_shell_uses_same_project_background_registry(tmp_path: Path) -> None:
    """The optional security wrapper must keep task IDs visible in the bound project."""
    from henchman.tools.security.shell_secure import SecureShellTool

    tool = SecureShellTool()
    tool.bind_runtime(project_root=tmp_path)
    result = await tool.execute(command="echo secure")
    service = TaskService(tmp_path)
    record = await service.wait_for_task(_task_id(result.content), timeout=5)
    assert record.status == "completed"
    assert "secure" in service.tail_output(record.task_id)


@pytest.mark.anyio
async def test_background_launch_does_not_claim_automatic_formatting(tmp_path: Path) -> None:
    """Delayed source mutations need explicit formatting after the job completes."""
    from henchman.tools.formatting import PythonAutoFormatter

    tool = PythonExecTool()
    tool.bind_runtime(project_root=tmp_path)
    code = (
        "import time\nfrom pathlib import Path\n"
        "while not Path('release').exists(): time.sleep(0.01)\n"
        "Path('generated.py').write_text('value=  1')\n"
    )
    result = await PythonAutoFormatter().run(
        tool, {"code": code, "cwd": str(tmp_path)},
        lambda: tool.execute(code=code, cwd=str(tmp_path)),
    )
    task_id = _task_id(result.content)
    try:
        assert "formatting skipped" in result.content.lower()
        assert "after" in result.content.lower()
    finally:
        (tmp_path / "release").touch()
        await TaskService(tmp_path).wait_for_task(task_id, timeout=5)
    assert (tmp_path / "generated.py").read_text() == "value=  1"


@pytest.mark.anyio
async def test_index_write_failure_cleans_up_new_process(tmp_path: Path) -> None:
    """A failed launch acknowledgement must not leave an undisclosed job alive."""
    service = TaskService(tmp_path)
    service._index_path.unlink()
    service._index_path.mkdir()
    with pytest.raises(OSError):
        await service.start_task(argv=[sys.executable, "-c", "import time; time.sleep(30)"])
    assert service.list_tasks(status="running") == []
    assert not service._runtime.processes


@pytest.mark.anyio
async def test_completion_persistence_failure_still_settles_waiter(tmp_path: Path) -> None:
    """Storage errors during completion must be reported without hanging observers."""
    service = TaskService(tmp_path)
    record = await service.start_task(argv=[sys.executable, "-c", "import time; time.sleep(0.2)"])
    service._index_path.unlink()
    service._index_path.mkdir()
    final = await service.wait_for_task(record.task_id, timeout=2)
    assert final.status == "failed"
    assert "persist" in final.metadata.get("error", "").lower()


@pytest.mark.anyio
async def test_timeout_log_failure_still_reaps_process(tmp_path: Path) -> None:
    """Writing a timeout diagnostic must never prevent process termination."""
    service = TaskService(tmp_path)
    record = await service.start_task(
        argv=[sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.1,
    )
    process = service._runtime.processes[record.task_id]
    record.output_path.unlink()
    record.output_path.mkdir()
    final = await service.wait_for_task(record.task_id, timeout=2)
    assert final.status == "failed"
    assert process.returncode is not None
    assert "timeout" in final.metadata.get("error", "").lower()


@pytest.mark.anyio
@pytest.mark.skipif(os.name != "posix", reason="POSIX process group lifecycle")
async def test_finished_parent_does_not_leave_untracked_descendant(tmp_path: Path) -> None:
    """A completed task owns its descendants until they have been stopped."""
    child = (
        "import signal,time; from pathlib import Path; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "Path('ready').touch(); time.sleep(0.5); Path('escaped').touch(); time.sleep(30)"
    )
    parent = (
        "import subprocess,sys,time\nfrom pathlib import Path\n"
        f"subprocess.Popen([sys.executable, '-c', {child!r}])\n"
        "while not Path('ready').exists(): time.sleep(0.01)\n"
    )
    service = TaskService(tmp_path)
    record = await service.start_task(argv=[sys.executable, "-c", parent])
    final = await service.wait_for_task(record.task_id, timeout=5)
    assert final.status == "completed"
    await asyncio.sleep(0.6)
    assert not (tmp_path / "escaped").exists()
