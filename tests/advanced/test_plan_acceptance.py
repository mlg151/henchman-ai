"""Plan acceptance evidence remains separate from reported progress."""

import asyncio
import json
from pathlib import Path

import pytest

from henchman.advanced.plans import PlanExecutionService


async def test_reported_completion_does_not_pass_missing_file(tmp_path: Path) -> None:
    service = PlanExecutionService(tmp_path)
    plan = service.create_plan(steps=["Create module"], checks=[
        {"kind": "file_exists", "path": "module.py"},
    ])
    service.complete_step(plan.plan_id, step=1, evidence="All done and verified")
    report = await service.verify_plan(plan.plan_id)
    assert report["checks_passed"] is False
    assert report["task_verified"] is False
    (tmp_path / "module.py").write_text("value = 1")
    assert (await service.verify_plan(plan.plan_id))["checks_passed"] is True
    restored = PlanExecutionService(tmp_path).get_plan(plan.plan_id)
    assert restored is not None
    assert restored.last_verification["checks_passed"] is True
    assert "historical" in service.render_status(plan.plan_id).lower()
    (tmp_path / "module.py").unlink()
    assert not (await service.verify_plan(plan.plan_id))["checks_passed"]


def test_existing_services_do_not_lose_other_plans(tmp_path: Path) -> None:
    first, second = PlanExecutionService(tmp_path), PlanExecutionService(tmp_path)
    a = first.create_plan(steps=["a"])
    b = second.create_plan(steps=["b"])
    assert {p.plan_id for p in first.list_plans()} == {a.plan_id, b.plan_id}


async def test_legacy_checklist_cannot_verify(tmp_path: Path) -> None:
    service = PlanExecutionService(tmp_path)
    plan = service.create_plan(steps=["legacy"])
    with pytest.raises(ValueError, match="checks"):
        await service.verify_plan(plan.plan_id)


@pytest.mark.parametrize("content", ["broken json", "{}", '[{"plan_id": "x", "checks": [{}]}]'])
def test_corrupt_state_is_not_reset(tmp_path: Path, content: str) -> None:
    path = tmp_path / ".henchman/plans/verification.json"
    path.parent.mkdir(parents=True)
    path.write_text(content)
    with pytest.raises(ValueError):
        PlanExecutionService(tmp_path).list_plans()
    assert path.read_text() == content


async def test_cancelled_reverification_clears_old_success(tmp_path: Path, monkeypatch) -> None:
    from henchman.advanced import plans

    service = PlanExecutionService(tmp_path)
    (tmp_path / "x").touch()
    plan = service.create_plan(steps=["x"], checks=[{"kind": "file_exists", "path": "x"}])
    assert (await service.verify_plan(plan.plan_id))["checks_passed"]

    async def cancelled(*_args):
        raise asyncio.CancelledError

    monkeypatch.setattr(plans, "run_checks", cancelled)
    with pytest.raises(asyncio.CancelledError):
        await service.verify_plan(plan.plan_id)
    stored = json.loads((tmp_path / ".henchman/plans/verification.json").read_text())[0]
    assert stored["last_verification"]["checks_passed"] is False
    assert stored["last_verification"]["status"] == "cancelled"


async def test_changed_baseline_survives_reload(tmp_path: Path) -> None:
    (tmp_path / "x").write_text("before")
    service = PlanExecutionService(tmp_path)
    plan = service.create_plan(steps=["edit"], checks=[{"kind": "file_changed", "path": "x"}])
    (tmp_path / "x").write_text("after")
    assert (await PlanExecutionService(tmp_path).verify_plan(plan.plan_id))["checks_passed"]


async def test_verification_preserves_concurrent_progress_and_rejects_superseded_run(
    tmp_path: Path, monkeypatch,
) -> None:
    from henchman.advanced import plans

    service = PlanExecutionService(tmp_path)
    (tmp_path / "x").touch()
    plan = service.create_plan(steps=["x"], checks=[{"kind": "file_exists", "path": "x"}])
    entered, release = asyncio.Event(), asyncio.Event()
    original = plans.run_checks

    async def delayed(root, checks):
        entered.set()
        await release.wait()
        return await original(root, checks)

    monkeypatch.setattr(plans, "run_checks", delayed)
    older = asyncio.create_task(service.verify_plan(plan.plan_id))
    await entered.wait()
    other = PlanExecutionService(tmp_path)
    other.complete_step(plan.plan_id, step=1)
    monkeypatch.setattr(plans, "run_checks", original)
    newer = await other.verify_plan(plan.plan_id)
    release.set()
    with pytest.raises(ValueError, match="superseded"):
        await older
    current = service.get_plan(plan.plan_id)
    assert current.steps[0].done
    assert current.last_verification == newer


async def test_registry_policies_prevent_acceptance_command_execution(tmp_path: Path) -> None:
    import sys

    from henchman.tools.builtins.tier6_tools import VerifyPlanExecutionTool
    from henchman.tools.registry import ToolRegistry

    tool = VerifyPlanExecutionTool()
    tool.bind_runtime(project_root=tmp_path)
    registry = ToolRegistry()
    registry.register(tool)
    created = await registry.execute("verify_plan_execution", {
        "action": "create", "steps": ["produce marker"],
        "checks": [{"kind": "command", "argv": [
            sys.executable, "-c", "from pathlib import Path; Path('marker').touch()",
        ]}],
    })
    assert created.success
    plan = PlanExecutionService(tmp_path).list_plans()[0]
    params = {"action": "verify", "plan_id": plan.plan_id}
    registry.set_plan_mode(enabled=True)
    assert not (await registry.execute("verify_plan_execution", params)).success
    assert not (tmp_path / "marker").exists()
    registry.set_plan_mode(enabled=False)

    async def deny(*_args):
        return False

    registry.set_confirmation_handler(deny)
    assert not (await registry.execute("verify_plan_execution", params)).success
    assert not (tmp_path / "marker").exists()

    async def approve(request):
        assert request.params["checks"][0]["argv"][0] == sys.executable
        return True

    registry.set_confirmation_handler(approve)
    result = await registry.execute("verify_plan_execution", params)
    assert result.success, result.content
    assert json.loads(result.content)["task_verified"] is False
    assert (tmp_path / "marker").exists()


async def test_cancelling_superseded_run_preserves_cancellation(tmp_path: Path, monkeypatch) -> None:
    from henchman.advanced import plans

    service = PlanExecutionService(tmp_path)
    (tmp_path / "x").touch()
    plan = service.create_plan(steps=["x"], checks=[{"kind": "file_exists", "path": "x"}])
    entered = asyncio.Event()
    original = plans.run_checks

    async def delayed(*_args):
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(plans, "run_checks", delayed)
    older = asyncio.create_task(service.verify_plan(plan.plan_id))
    await entered.wait()
    monkeypatch.setattr(plans, "run_checks", original)
    newer = await service.verify_plan(plan.plan_id)
    older.cancel()
    with pytest.raises(asyncio.CancelledError):
        await older
    assert service.get_plan(plan.plan_id).last_verification == newer


async def test_corrupt_plan_storage_does_not_disable_other_tools(tmp_path: Path, monkeypatch) -> None:
    from henchman.cli.tool_manager import ToolManager

    path = tmp_path / ".henchman/plans/verification.json"
    path.parent.mkdir(parents=True)
    path.write_text("broken json")
    monkeypatch.chdir(tmp_path)
    manager = ToolManager()
    manager.bind_runtime(project_root=tmp_path)
    manager.register_builtin_tools()
    result = await manager.registry.execute("verify_plan_execution", {"action": "list"})
    assert not result.success
    assert path.read_text() == "broken json"
    assert manager.registry.get("read_file") is not None
