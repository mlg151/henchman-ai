"""Workflow preparation must never masquerade as command execution."""

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from henchman.team import PushNotificationService, TeamWorkspaceService, WorkflowService
from henchman.tools.builtins.tier5_tools import WorkflowTool
from henchman.tools.registry import ToolRegistry


def prepare_workflow(root: Path) -> tuple[WorkflowService, str, Path]:
    TeamWorkspaceService(project_root=root).create_workspace(name="checks", members=["engineer"])
    marker = root / "executed.txt"
    argv = [sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).touch()"]
    command = subprocess.list2cmdline(argv) if os.name == "nt" else shlex.join(argv)
    service = WorkflowService(
        project_root=root,
        notification_service=PushNotificationService(project_root=root),
    )
    service.define(
        workspace_id="checks",
        workflow_name="build",
        created_by="engineer",
        steps=[command, "inspect {{package}}"],
    )
    return service, command, marker


def test_preparation_records_no_execution_and_preserves_rendered_steps(tmp_path: Path) -> None:
    service, command, marker = prepare_workflow(tmp_path)
    record = service.run(
        workspace_id="checks",
        workflow_name="build",
        requested_by="engineer",
        inputs={"package": "example"},
    )
    assert not marker.exists()
    assert record.status == "execution_unavailable"
    assert record.executed_steps == ()
    assert record.rendered_steps == (command, "inspect example")
    payload = record.to_dict()
    assert payload["executed_steps"] == []
    assert payload["rendered_steps"] == [command, "inspect example"]
    loaded = WorkflowService(project_root=tmp_path).list_runs(
        workspace_id="checks",
        workflow_name="build",
    )
    assert loaded == [record]
    notices = PushNotificationService(project_root=tmp_path).list_notifications(
        workspace_id="checks"
    )
    assert notices[-1].event == "workflow_run"
    assert "No steps were executed" in notices[-1].message


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["run", "trigger"])
async def test_registry_reports_execution_unavailable_for_run_and_trigger(
    tmp_path: Path,
    action: str,
) -> None:
    service, command, marker = prepare_workflow(tmp_path)
    tool = WorkflowTool()
    registry = ToolRegistry()
    tool.bind_runtime(project_root=tmp_path, tool_registry=registry)
    registry.register(tool)
    created = await registry.execute(
        "workflow",
        {
            "action": "create_trigger",
            "workspace": "checks",
            "workflow": "build",
            "trigger": "manual",
            "actor": "engineer",
        },
    )
    assert created.success
    result = await registry.execute(
        "workflow",
        {
            "action": action,
            "workspace": "checks",
            "workflow": "build",
            "trigger": "manual",
            "actor": "engineer",
            "inputs": {"package": "example"},
        },
    )
    assert not marker.exists()
    assert result.success is False
    assert result.error == "Workflow execution is unavailable"
    assert "No steps were executed" in result.content
    assert command in result.content and "inspect example" in result.content
    records = service.list_runs(workspace_id="checks", workflow_name="build")
    assert len(records) == 1
    assert records[0].status == "execution_unavailable"
    assert records[0].executed_steps == ()
    assert records[0].rendered_steps == (command, "inspect example")
    notices = PushNotificationService(project_root=tmp_path).list_notifications(
        workspace_id="checks"
    )
    assert all(
        "No steps were executed" in notice.message
        for notice in notices
        if notice.event in {"workflow_run", "remote_trigger"}
    )


def test_new_preparation_does_not_rewrite_legacy_records(tmp_path: Path) -> None:
    service, _, _ = prepare_workflow(tmp_path)
    history = tmp_path / ".henchman/team/workspaces/checks/workflow_runs/build.jsonl"
    history.parent.mkdir(parents=True, exist_ok=True)
    legacy: dict[str, object] = {
        "run_id": "old-run",
        "workspace_id": "checks",
        "workflow_name": "build",
        "status": "completed",
        "requested_by": "engineer",
        "inputs": {},
        "executed_steps": ["legacy claim"],
        "trigger_name": None,
        "bridge_session_id": None,
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    original = json.dumps(legacy).encode() + b"\n"
    history.write_bytes(original)
    service.run(workspace_id="checks", workflow_name="build", requested_by="engineer")
    assert history.read_bytes().startswith(original)
    records = service.list_runs(workspace_id="checks", workflow_name="build")
    assert records[0].status == "completed"
    assert records[0].executed_steps == ("legacy claim",)
    assert records[0].rendered_steps == ()
    assert records[1].status == "execution_unavailable"
    assert records[1].executed_steps == ()
