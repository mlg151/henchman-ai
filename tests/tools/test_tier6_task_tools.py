"""Tests for Tier 6 task-management builtin tools."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from henchman.cli.tool_manager import ToolManager


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
