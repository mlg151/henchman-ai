"""Configured requirements cannot disappear from current plan verification."""

import asyncio
import copy
import json
from unittest.mock import AsyncMock

import pytest

from henchman.advanced.acceptance_checks import check_spec_digest, parse_checks
from henchman.advanced.plans import PlanExecutionService
from henchman.config.schema import Settings


def configured():
    return Settings.model_validate({"verification": {"checks": [
        {"kind": "file_contains", "path": "value.txt", "text": "required", "requirement_ids": ["REQ-1"]},
    ]}})


async def test_configured_checks_are_included_and_bound_before_work(tmp_path):
    (tmp_path / "value.txt").write_text("required", encoding="utf-8")
    settings = configured()
    service = PlanExecutionService(tmp_path, settings=settings)
    record = service.create_plan(steps=["Inspect"], checks=[{"kind": "file_exists", "path": "value.txt"}])
    assert len(record.checks) == 2 and record.checks[0].requirement_ids == ("REQ-1",)
    assert record.project_checks_digest
    assert (await service.verify_plan(record.plan_id))["current_checks_passed"] is True
    assert service.verification_status(record.plan_id)["status"] == "pass"


async def test_changed_required_configuration_revokes_pass_without_rewriting_history(tmp_path, monkeypatch):
    from henchman.advanced import plans

    (tmp_path / "value.txt").write_text("required", encoding="utf-8")
    settings = configured()
    service = PlanExecutionService(tmp_path, settings=settings)
    record = service.create_plan(steps=["Inspect"])
    await service.verify_plan(record.plan_id)
    index = tmp_path / ".henchman/plans/verification.json"
    before = index.read_bytes()
    settings.verification.checks.clear()
    assert service.verification_status(record.plan_id)["status"] == "stale"
    assert index.read_bytes() == before
    runner = AsyncMock()
    monkeypatch.setattr(plans, "run_checks", runner)
    with pytest.raises(ValueError, match="configuration changed"):
        await service.verify_plan(record.plan_id)
    runner.assert_not_called()
    assert index.read_bytes() == before


async def test_new_required_checks_make_legacy_plan_unverified(tmp_path):
    (tmp_path / "value.txt").write_text("required", encoding="utf-8")
    settings = Settings()
    service = PlanExecutionService(tmp_path, settings=settings)
    record = service.create_plan(steps=["Inspect"], checks=[{"kind": "file_exists", "path": "value.txt"}])
    await service.verify_plan(record.plan_id)
    settings.verification.checks = copy.deepcopy(configured().verification.checks)
    status = service.verification_status(record.plan_id)
    assert status["status"] == "unverified" and status["current_checks_passed"] is False


async def test_configuration_change_during_checks_cannot_become_current_proof(tmp_path, monkeypatch):
    from henchman.advanced import plans

    (tmp_path / "value.txt").write_text("required", encoding="utf-8")
    settings = configured()
    service = PlanExecutionService(tmp_path, settings=settings)
    record = service.create_plan(steps=["Inspect"])
    original = plans.run_checks
    before = copy.deepcopy(settings.verification.checks)
    async def changed(*args, **kwargs):
        report = await original(*args, **kwargs)
        settings.verification.checks.clear()
        return report
    monkeypatch.setattr(plans, "run_checks", changed)
    report = await service.verify_plan(record.plan_id)
    assert report["configuration_status"] == "changed"
    assert report["current_checks_passed"] is False
    settings.verification.checks = before
    assert service.verification_status(record.plan_id)["status"] == "stale"


def test_combined_limit_and_duplicate_configured_checks(tmp_path):
    settings = configured()
    service = PlanExecutionService(tmp_path, settings=settings)
    record = service.create_plan(steps=["Inspect"], checks=copy.deepcopy(settings.verification.checks))
    assert len(record.checks) == 1
    with pytest.raises(ValueError, match="20"):
        service.create_plan(steps=["Inspect"], checks=[
            {"kind": "file_exists", "path": f"file-{index}.txt"} for index in range(20)
        ])


def test_direct_service_uses_existing_project_settings_configuration(tmp_path):
    directory = tmp_path / ".henchman"
    directory.mkdir()
    (directory / "settings.json").write_text(json.dumps({"verification": configured().verification.model_dump()}))
    service = PlanExecutionService(tmp_path)
    record = service.create_plan(steps=["Inspect"])
    assert record.checks[0].requirement_ids == ("REQ-1",)


def test_configured_credentials_reject_before_baseline_reads(tmp_path, monkeypatch):
    from henchman.advanced import plans

    settings = configured()
    settings.providers.deepseek["api_key"] = "configured-check-private-canary"
    settings.verification.checks[0]["text"] = "configured-check-private-canary"
    monkeypatch.setattr(plans, "prepare_checks", lambda *_args: pytest.fail("Read sensitive baseline"))
    with pytest.raises(ValueError, match="credential"):
        PlanExecutionService(tmp_path, settings=settings).create_plan(steps=["Inspect"])
    assert not (tmp_path / ".henchman/plans").exists()


def test_verification_tool_uses_held_runtime_configuration(tmp_path):
    from henchman.cli.tool_manager import ToolManager

    settings = configured()
    manager = ToolManager(settings)
    manager.bind_runtime(project_root=tmp_path)
    manager.register_builtin_tools()
    tool = manager.registry.get("verify_plan_execution")
    record = tool._plan_service.create_plan(steps=["Inspect"])
    assert record.checks[0].requirement_ids == ("REQ-1",)
    settings.verification.checks.clear()
    assert tool._plan_service.verification_status(record.plan_id)["configuration_status"] == "changed"


@pytest.mark.parametrize("runtime", [True, False])
async def test_invalid_postflight_configuration_preserves_terminal_observations(tmp_path, monkeypatch, runtime):
    from henchman.advanced import plans

    (tmp_path / "value.txt").write_text("required", encoding="utf-8")
    settings = configured()
    config_path = tmp_path / ".henchman/settings.json"
    if not runtime:
        config_path.parent.mkdir()
        config_path.write_text(json.dumps({"verification": settings.verification.model_dump()}))
    service = PlanExecutionService(tmp_path, settings=settings if runtime else None)
    record = service.create_plan(steps=["Check"])
    original = plans.run_checks

    async def invalidate(*args):
        report = await original(*args)
        settings.verification.checks[0]["kind"] = "invalid-after-check"
        if not runtime:
            config_path.write_text(json.dumps({"verification": settings.verification.model_dump()}))
        return report

    monkeypatch.setattr(plans, "run_checks", invalidate)
    with pytest.raises(ValueError):
        await service.verify_plan(record.plan_id)
    saved = json.loads((tmp_path / ".henchman/plans/verification.json").read_text())[0]
    report = saved["last_verification"]
    assert report["status"] == "error"
    assert report["checks_passed"] is False and report["current_checks_passed"] is False
    assert len(report["results"]) == 1 and report["results"][0]["status"] == "pass"


async def test_configuration_digest_alone_does_not_prove_required_assertions(tmp_path, monkeypatch):
    from henchman.advanced import plans

    (tmp_path / "value.txt").write_text("safe", encoding="utf-8")
    settings = Settings()
    service = PlanExecutionService(tmp_path, settings=settings)
    record = service.create_plan(steps=["Check"], checks=[{"kind": "file_exists", "path": "value.txt"}])
    await service.verify_plan(record.plan_id)
    settings.verification.checks = copy.deepcopy(configured().verification.checks)
    index = tmp_path / ".henchman/plans/verification.json"
    payload = json.loads(index.read_text())
    payload[0]["project_checks_digest"] = check_spec_digest(parse_checks(settings.verification.checks))
    payload[0]["last_verification"]["configuration_status"] = "current"
    index.write_text(json.dumps(payload))
    status = service.verification_status(record.plan_id)
    assert status["current_checks_passed"] is False
    assert status["configuration_status"] == "unbound"
    runner = AsyncMock()
    monkeypatch.setattr(plans, "run_checks", runner)
    with pytest.raises(ValueError, match="never bound"):
        await service.verify_plan(record.plan_id)
    runner.assert_not_called()


async def test_injected_credential_rotation_blocks_next_assertion(tmp_path, monkeypatch):
    from henchman.advanced import acceptance_checks

    (tmp_path / "first").write_text("ok", encoding="utf-8")
    canary = "injected-rotation-private-canary"
    (tmp_path / "second").write_text(canary, encoding="utf-8")
    settings = Settings(verification={"checks": [
        {"kind": "file_exists", "path": "first"},
        {"kind": "file_contains", "path": "second", "text": canary},
    ]})
    service = PlanExecutionService(tmp_path, settings=settings)
    record = service.create_plan(steps=["Check"])
    original = acceptance_checks._file_result
    visited = []

    def rotate(root, spec):
        visited.append(spec.path)
        result = original(root, spec)
        if spec.path == "first":
            settings.providers.deepseek["api_key"] = canary
        return result

    monkeypatch.setattr(acceptance_checks, "_file_result", rotate)
    with pytest.raises(ValueError, match="credentials"):
        await service.verify_plan(record.plan_id)
    assert visited == ["first"]
    saved = (tmp_path / ".henchman/plans/verification.json").read_text()
    assert canary not in saved
    assert json.loads(saved)[0]["last_verification"]["status"] == "error"


async def test_required_changed_file_keeps_internally_captured_baseline(tmp_path):
    (tmp_path / "source.py").write_text("before", encoding="utf-8")
    settings = Settings(verification={"checks": [{"kind": "file_changed", "path": "source.py"}]})
    service = PlanExecutionService(tmp_path, settings=settings)
    record = service.create_plan(steps=["Change file"])
    assert record.checks[0].baseline_captured is True
    assert service.verification_status(record.plan_id)["configuration_status"] == "current"
    (tmp_path / "source.py").write_text("after", encoding="utf-8")
    assert (await service.verify_plan(record.plan_id))["current_checks_passed"] is True


@pytest.mark.parametrize("field,value", [
    ("inputs", ["other.py"]), ("requirement_ids", ["OTHER"]),
    ("timeout", 30), ("expected_exit", 1), ("argv", ["different-program"]),
])
def test_required_check_binding_keeps_every_public_assertion_field(tmp_path, field, value):
    settings = Settings(verification={"checks": [{"kind": "command", "argv": ["configured-program"],
        "inputs": ["source.py"], "requirement_ids": ["REQ-1"], "timeout": 20}]})
    service = PlanExecutionService(tmp_path, settings=settings)
    record = service.create_plan(steps=["Check"])
    index = tmp_path / ".henchman/plans/verification.json"
    payload = json.loads(index.read_text())
    payload[0]["checks"][0][field] = value
    index.write_text(json.dumps(payload))
    assert service.verification_status(record.plan_id)["configuration_status"] == "unbound"


@pytest.mark.parametrize("outcome", ["running", "error", "cancelled"])
async def test_configured_checks_preserve_explicit_run_lifecycle(tmp_path, monkeypatch, outcome):
    from henchman.advanced import plans

    (tmp_path / "value.txt").write_text("required", encoding="utf-8")
    service = PlanExecutionService(tmp_path, settings=configured())
    record = service.create_plan(steps=["Check"])
    original = plans.run_checks

    async def runner(*args):
        if outcome == "running":
            assert service.verification_status(record.plan_id)["status"] == "running"
            return await original(*args)
        if outcome == "cancelled":
            raise asyncio.CancelledError()
        raise OSError("Check runner failed")

    monkeypatch.setattr(plans, "run_checks", runner)
    if outcome == "running":
        await service.verify_plan(record.plan_id)
    else:
        with pytest.raises(asyncio.CancelledError if outcome == "cancelled" else OSError):
            await service.verify_plan(record.plan_id)
        status = service.verification_status(record.plan_id)
        assert status["status"] == outcome
        assert status["current_checks_passed"] is False


async def test_credential_rotation_during_input_capture_blocks_dispatch(tmp_path, monkeypatch):
    from henchman.advanced import acceptance_checks

    canary = "rotation-during-input-capture-private-canary"
    (tmp_path / "value.txt").write_text(canary, encoding="utf-8")
    settings = configured()
    settings.verification.checks[0]["text"] = canary
    service = PlanExecutionService(tmp_path, settings=settings)
    record = service.create_plan(steps=["Check"])
    capture = acceptance_checks.capture_inputs_async
    file_result = acceptance_checks._file_result
    captured = 0
    visited = []

    async def rotate(*args, **kwargs):
        nonlocal captured
        result = await capture(*args, **kwargs)
        captured += 1
        if captured == 2:
            settings.providers.deepseek["api_key"] = canary
        return result

    def observe(*args):
        visited.append(True)
        return file_result(*args)

    monkeypatch.setattr(acceptance_checks, "capture_inputs_async", rotate)
    monkeypatch.setattr(acceptance_checks, "_file_result", observe)
    with pytest.raises(ValueError, match="credentials"):
        await service.verify_plan(record.plan_id)
    assert visited == []
