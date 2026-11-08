"""Tests for Tier 6 task-management builtin tools."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

from henchman.cli.tool_manager import ToolManager
from henchman.tools.base import ConfirmationRequest


async def _approve(request: ConfirmationRequest) -> bool:  # noqa: ARG001
    return True


@pytest.mark.parametrize('status', ['stopped', 'completed', 'failed', 'cancelled', 'outcome_unknown', 'running'])
async def test_task_stop_reports_only_observed_stopped_state_as_success(tmp_path, monkeypatch, status):
    from henchman.advanced.tasks import TaskRecord
    from henchman.tools.builtins.tier6_tools import TaskStopTool

    monkeypatch.chdir(tmp_path)
    tool = TaskStopTool()
    record = TaskRecord(task_id='task-0123456789ab', title='fixture', argv=('fixture',), cwd=str(tmp_path),
                        status='stopped', created_at='2026-01-01T00:00:00Z', started_at=None,
                        finished_at=None, output_path=tmp_path/'task.log', pid=None, return_code=None,
                        metadata={'error': 'cleanup incomplete'} if status == 'outcome_unknown' else {})

    async def observed(_identity):
        return replace(record, status=status)

    monkeypatch.setattr(tool._task_service, 'stop_task', observed)
    result = await tool.execute(task_id=record.task_id)
    assert result.success is (status == 'stopped')
    assert f'[{status}]' in result.content
    if status != 'stopped':
        assert result.error and 'did not establish' in result.error
        assert not result.content.startswith('Stopped task')
    if status == 'outcome_unknown':
        assert 'cleanup incomplete' in result.content


async def test_task_stop_does_not_claim_a_completed_task_was_stopped(tmp_path, monkeypatch):
    from henchman.tools.builtins.tier6_tools import TaskStopTool

    monkeypatch.chdir(tmp_path)
    tool = TaskStopTool()
    record = await tool._task_service.start_task(argv=[sys.executable, '-c', 'pass'])
    assert (await tool._task_service.wait_for_task(record.task_id, timeout=15)).status == 'completed'
    result = await tool.execute(task_id=record.task_id)
    assert not result.success and '[completed]' in result.content
    assert 'did not establish' in result.error


async def test_task_stop_reports_uncertain_cleanup_without_claiming_success(tmp_path, monkeypatch):
    from henchman.tools.builtins.tier6_tools import TaskStopTool

    monkeypatch.chdir(tmp_path)
    tool = TaskStopTool()
    service = tool._task_service
    original = service._finish_capture

    async def fail_after_cleanup(process, output):
        await original(process, output)
        raise OSError('cleanup observation unavailable')

    monkeypatch.setattr(service, '_finish_capture', fail_after_cleanup)
    record = await service.start_task(argv=[sys.executable, '-c', 'import time; time.sleep(30)'])
    process = service._runtime.processes[record.task_id]
    try:
        result = await tool.execute(task_id=record.task_id)
        assert not result.success and '[outcome_unknown]' in result.content
        assert 'cleanup observation unavailable' in result.content
        assert process.returncode is not None and record.task_id not in service._runtime.monitors
    finally:
        if process.returncode is None:
            await service._terminate_process(process)


def test_builtin_surface_includes_tier6_task_tools() -> None:
    """The builtin surface should expose the Tier 6 task tool exports."""

    import henchman.tools.builtins as builtins_mod

    assert {
        "TaskCreateTool",
        "TaskGetTool",
        "TaskListTool",
        "TaskOutputTool",
        "TaskStopTool",
        "TaskUpdateTool",
    } <= set(builtins_mod.__all__)

    def _instantiate(tool_class: object) -> object:
        if tool_class is builtins_mod.ShellTool:
            return builtins_mod.ShellTool(default_timeout=60)
        if tool_class is builtins_mod.RagSearchTool:
            from unittest.mock import MagicMock

            return builtins_mod.RagSearchTool(store=MagicMock())
        return tool_class()

    names = {_instantiate(tool_class).name for tool_class in builtins_mod.iter_available_builtin_tool_classes()}

    assert {
        "task_create",
        "task_get",
        "task_list",
        "task_output",
        "task_stop",
        "task_update",
    } <= names


@pytest.mark.anyio
async def test_task_tools_manage_background_processes_and_persist_output(
    tmp_path: Path,
) -> None:
    """Tier 6 task tools should manage background task lifecycle and output."""

    from henchman.advanced import TaskService

    manager = ToolManager()
    manager.set_confirmation_handler(_approve)
    manager.bind_runtime(project_root=tmp_path)
    manager.register_builtin_tools()

    created = await manager.registry.execute(
        "task_create",
        {
            "argv": [sys.executable, "-c", "print('alpha')"],
            "title": "short-task",
        },
    )

    assert created.success is True

    service = TaskService(project_root=tmp_path)
    short_task = next(record for record in service.list_tasks() if record.title == "short-task")
    completed = await service.wait_for_task(short_task.task_id, timeout=5.0)

    got = await manager.registry.execute("task_get", {"task_id": short_task.task_id})
    listed = await manager.registry.execute("task_list", {})
    output = await manager.registry.execute(
        "task_output",
        {"task_id": short_task.task_id, "lines": 10},
    )
    updated = await manager.registry.execute(
        "task_update",
        {
            "task_id": short_task.task_id,
            "title": "short-task-renamed",
            "metadata": {"owner": "copilot"},
        },
    )

    refreshed = service.get_task(short_task.task_id)

    assert completed.status == "completed"
    assert got.success is True
    assert listed.success is True
    assert output.success is True
    assert updated.success is True
    assert refreshed is not None
    assert refreshed.title == "short-task-renamed"
    assert refreshed.metadata["owner"] == "copilot"
    assert short_task.task_id in got.content
    assert short_task.task_id in listed.content
    assert "alpha" in output.content
    assert (tmp_path / ".henchman" / "tasks" / "index.json").exists()
    assert (tmp_path / ".henchman" / "tasks" / f"{short_task.task_id}.log").exists()

    created_long = await manager.registry.execute(
        "task_create",
        {
            "argv": [
                sys.executable,
                "-c",
                "import time; print('started'); time.sleep(30)",
            ],
            "title": "long-task",
        },
    )

    assert created_long.success is True

    long_task = next(record for record in service.list_tasks() if record.title == "long-task")
    stopped = await manager.registry.execute("task_stop", {"task_id": long_task.task_id})
    stopped_record = await service.wait_for_task(long_task.task_id, timeout=5.0)

    assert stopped.success is True
    assert stopped_record.status == "stopped"
