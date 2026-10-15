"""Tests for Tier 6 REPL and plan-verification builtin tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from henchman.cli.tool_manager import ToolManager


def test_builtin_surface_includes_tier6_repl_and_plan_tools() -> None:
    """The builtin surface should expose Tier 6 REPL and plan tools."""

    import henchman.tools.builtins as builtins_mod

    assert {"REPLTool", "VerifyPlanExecutionTool"} <= set(builtins_mod.__all__)

    def _instantiate(tool_class: object) -> object:
        if tool_class is builtins_mod.ShellTool:
            return builtins_mod.ShellTool(default_timeout=60)
        if tool_class is builtins_mod.RagSearchTool:
            from unittest.mock import MagicMock

            return builtins_mod.RagSearchTool(store=MagicMock())
        return tool_class()

    names = {_instantiate(tool_class).name for tool_class in builtins_mod.iter_available_builtin_tool_classes()}

    assert {"repl", "verify_plan_execution"} <= names


@pytest.mark.anyio
async def test_repl_tool_persists_session_state_and_history(tmp_path: Path) -> None:
    """REPLTool should preserve execution state across session inputs."""

    from henchman.advanced import ExperimentReplService

    manager = ToolManager()
    manager.bind_runtime(project_root=tmp_path)
    manager.register_builtin_tools()

    started = await manager.registry.execute(
        "repl",
        {"action": "start", "name": "scratch"},
    )
    assert started.success is True

    service = ExperimentReplService(project_root=tmp_path)
    session = service.list_sessions()[0]

    assigned = await manager.registry.execute(
        "repl",
        {"action": "input", "session_id": session.session_id, "code": "value = 2 + 2"},
    )
    echoed = await manager.registry.execute(
        "repl",
        {"action": "input", "session_id": session.session_id, "code": "print(value)"},
    )
    history = await manager.registry.execute(
        "repl",
        {"action": "history", "session_id": session.session_id},
    )
    closed = await manager.registry.execute(
        "repl",
        {"action": "close", "session_id": session.session_id},
    )

    refreshed = service.get_session(session.session_id)

    assert assigned.success is True
    assert echoed.success is True
    assert history.success is True
    assert closed.success is True
    assert "4" in echoed.content
    assert "print(value)" in history.content
    assert refreshed is not None
    assert refreshed.closed_at is not None
    assert (tmp_path / ".henchman" / "repl" / "index.json").exists()


@pytest.mark.anyio
async def test_verify_plan_execution_tool_enforces_ordered_step_completion(
    tmp_path: Path,
) -> None:
    """VerifyPlanExecutionTool should enforce sequential plan completion."""

    from henchman.advanced import PlanExecutionService

    manager = ToolManager()
    manager.bind_runtime(project_root=tmp_path)
    manager.register_builtin_tools()

    created = await manager.registry.execute(
        "verify_plan_execution",
        {
            "action": "create",
            "title": "tier6",
            "steps": ["Write tests", "Implement feature", "Run focused checks"],
        },
    )
    assert created.success is True

    service = PlanExecutionService(project_root=tmp_path)
    plan = service.list_plans()[0]

    next_step = await manager.registry.execute(
        "verify_plan_execution",
        {"action": "next", "plan_id": plan.plan_id},
    )
    out_of_order = await manager.registry.execute(
        "verify_plan_execution",
        {"action": "complete", "plan_id": plan.plan_id, "step": 2},
    )
    completed = await manager.registry.execute(
        "verify_plan_execution",
        {
            "action": "complete",
            "plan_id": plan.plan_id,
            "step": 1,
            "evidence": "Added red tests first.",
        },
    )
    status = await manager.registry.execute(
        "verify_plan_execution",
        {"action": "status", "plan_id": plan.plan_id},
    )

    refreshed = service.get_plan(plan.plan_id)

    assert next_step.success is True
    assert out_of_order.success is False
    assert completed.success is True
    assert status.success is True
    assert "Write tests" in next_step.content
    assert "[done] 1. Write tests" in status.content
    assert refreshed is not None
    assert refreshed.steps[0].done is True
    assert refreshed.steps[0].evidence == "Added red tests first."


@pytest.mark.anyio
async def test_acceptance_tool_reports_actual_file_checks(tmp_path: Path) -> None:
    """Reported progress cannot substitute for file observations."""
    import json

    from henchman.advanced import PlanExecutionService
    from henchman.tools.base import ToolKind
    from henchman.tools.builtins.tier6_tools import VerifyPlanExecutionTool

    tool = VerifyPlanExecutionTool()
    tool.bind_runtime(project_root=tmp_path)
    assert tool.kind is ToolKind.EXECUTE
    result = await tool.execute(action="create", steps=["create file"], checks=[
        {"kind": "file_exists", "path": "out.py"},
    ])
    assert result.success
    plan = PlanExecutionService(tmp_path).list_plans()[0]
    failed = await tool.execute(action="verify", plan_id=plan.plan_id)
    assert not failed.success
    assert json.loads(failed.content)["task_verified"] is False
    (tmp_path / "out.py").touch()
    passed = await tool.execute(action="verify", plan_id=plan.plan_id)
    assert passed.success
    assert json.loads(passed.content)["checks_passed"] is True
    assert not (await tool.execute(action="complete", plan_id=plan.plan_id, step=True)).success
    assert not (await tool.execute(action="create", steps=[42])).success
