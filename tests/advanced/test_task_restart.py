"""Persisted process metadata never establishes live child ownership after restart."""

import json
import os
from pathlib import Path

import pytest

from henchman.advanced.tasks import TaskRecord, TaskService


def saved_task(project: Path, *, status: str = "running") -> tuple[str, Path]:
    task_id = "task-012345abcdef"
    directory = project / ".henchman/tasks"
    directory.mkdir(parents=True)
    output = directory / f"{task_id}.log"
    output.write_text("Observed output before interruption\n", encoding="utf-8")
    record = TaskRecord(task_id=task_id, title="Interrupted process", argv=("never-replay",),
        cwd=str(project), status=status, created_at="2026-01-01T00:00:00+00:00",
        started_at="2026-01-01T00:00:01+00:00", finished_at=None, output_path=output,
        pid=os.getpid(), return_code=None, metadata={})
    index = directory / "index.json"
    index.write_text(json.dumps([record.to_dict()]), encoding="utf-8")
    return task_id, index


def test_restart_reports_unknown_outcome_without_inventing_exit_evidence(tmp_path):
    task_id, index = saved_task(tmp_path)
    service = TaskService(tmp_path)
    record = service.get_task(task_id)
    assert record.status == "outcome_unknown"
    assert record.finished_at is None and record.return_code is None
    assert record.pid == os.getpid()  # Historical evidence only, never authority.
    assert service.list_tasks(status="outcome_unknown") == [record]
    assert "before interruption" in service.tail_output(task_id)
    assert not service._runtime.processes and not service._runtime.waiters
    # Observing another runtime must not mutate its authoritative lifecycle.
    assert json.loads(index.read_text())[0]["status"] == "running"
    TaskService._runtimes.pop(service._storage_dir)
    assert TaskService(tmp_path).get_task(task_id) == record


@pytest.mark.parametrize("action", ["stop_task", "wait_for_task"])
async def test_unknown_saved_pid_cannot_be_signalled_or_claimed_stopped(tmp_path, monkeypatch, action):
    task_id, _ = saved_task(tmp_path)
    service = TaskService(tmp_path)

    async def forbidden(_process):
        pytest.fail("Persisted PID is not an owned Process")

    monkeypatch.setattr(service, "_terminate_process", forbidden)
    before = service.get_task(task_id)
    with pytest.raises(RuntimeError, match="not owned|ownership"):
        await getattr(service, action)(task_id)
    assert service.get_task(task_id) == before
    assert before.finished_at is None


def test_recovered_unknown_record_remains_loadable_and_does_not_launch(tmp_path):
    task_id, _ = saved_task(tmp_path, status="outcome_unknown")
    service = TaskService(tmp_path)
    assert service.get_task(task_id).status == "outcome_unknown"
    assert not service._runtime.processes


async def test_public_tools_report_unknown_and_refuse_unowned_stop(tmp_path, monkeypatch):
    from henchman.tools.builtins.tier6_tools import TaskGetTool, TaskListTool, TaskStopTool

    task_id, _ = saved_task(tmp_path)
    monkeypatch.chdir(tmp_path)
    for tool in (TaskGetTool(), TaskListTool()):
        result = await tool.execute(task_id=task_id, status="outcome_unknown")
        assert result.success and "outcome_unknown" in result.content
        assert "not owned" in result.content
    result = await TaskStopTool().execute(task_id=task_id)
    assert not result.success and "not owned" in result.error
