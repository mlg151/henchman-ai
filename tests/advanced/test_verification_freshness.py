"""Current check status is bound to declared contents, not a saved pass bit."""

import asyncio
import copy
import json
import sys

import pytest

from henchman.advanced.acceptance_checks import CheckSpec, parse_checks, run_checks
from henchman.advanced.plans import PlanExecutionService


async def test_manual_edit_and_delete_revoke_current_pass_without_changing_history(tmp_path):
    path = tmp_path / "value.txt"
    path.write_text("expected")
    service = PlanExecutionService(tmp_path)
    plan = service.create_plan(steps=["Implement"], checks=[
        {"kind": "file_contains", "path": "value.txt", "text": "expected"},
    ])
    assert service.verification_status(plan.plan_id)["status"] == "not_run"
    report = await service.verify_plan(plan.plan_id)
    assert service.verification_status(plan.plan_id)["status"] == "pass"
    index = tmp_path / ".henchman/plans/verification.json"
    saved = index.read_bytes()
    path.write_text("changed!")
    status = PlanExecutionService(tmp_path).verification_status(plan.plan_id)
    assert status["status"] == "stale" and status["current_checks_passed"] is False
    assert status["task_verified"] is False
    assert index.read_bytes() == saved
    assert service.get_plan(plan.plan_id).last_verification == report
    assert "stale" in service.render_status(plan.plan_id).lower()
    path.unlink()
    assert service.verification_status(plan.plan_id)["status"] == "stale"


async def test_content_identity_does_not_depend_on_same_length_or_mtime(tmp_path):
    import os

    path = tmp_path / "value.txt"
    path.write_text("pass")
    service = PlanExecutionService(tmp_path)
    plan = service.create_plan(steps=["Check"], checks=[{"kind": "file_exists", "path": "value.txt"}])
    await service.verify_plan(plan.plan_id)
    before = path.stat()
    path.write_text("fail")
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert service.verification_status(plan.plan_id)["status"] == "stale"


async def test_declared_command_inputs_and_requirement_ids_survive_reload(tmp_path):
    (tmp_path / "module.py").write_text("value = 1\n")
    service = PlanExecutionService(tmp_path)
    raw = {"kind": "command", "argv": [sys.executable, "-c", "pass"],
           "inputs": ["module.py"], "requirement_ids": ["REQ-1"]}
    plan = service.create_plan(steps=["Check"], checks=[raw])
    report = await service.verify_plan(plan.plan_id)
    assert report["current_checks_passed"] is True
    status = PlanExecutionService(tmp_path).verification_status(plan.plan_id)
    assert status["status"] == "pass"
    assert status["requirement_ids"] == ["REQ-1"]
    assert CheckSpec.from_dict(plan.checks[0].to_dict()) == plan.checks[0]
    (tmp_path / "module.py").write_text("value = 2\n")
    assert service.verification_status(plan.plan_id)["status"] == "stale"


async def test_unscoped_commands_remain_observations_without_current_proof(tmp_path):
    service = PlanExecutionService(tmp_path)
    plan = service.create_plan(steps=["Check"], checks=[
        {"kind": "command", "argv": [sys.executable, "-c", "pass"]},
    ])
    report = await service.verify_plan(plan.plan_id)
    assert report["checks_passed"] is True
    assert report["current_checks_passed"] is False
    assert service.verification_status(plan.plan_id)["status"] == "unverified"


async def test_later_check_mutation_cannot_reuse_earlier_pass(tmp_path):
    (tmp_path / "value.txt").write_text("before")
    report = await run_checks(tmp_path, parse_checks([
        {"kind": "file_contains", "path": "value.txt", "text": "before"},
        {"kind": "command", "argv": [sys.executable, "-c",
            "from pathlib import Path; Path('value.txt').write_text('after')"],
         "inputs": ["value.txt"]},
    ]))
    assert report["results"][0]["passed"] is True
    assert report["checks_passed"] is False
    assert report["current_checks_passed"] is False
    assert report["freshness"] == "stale"


async def test_edit_while_command_runs_is_detected(tmp_path, monkeypatch):
    from henchman.advanced import acceptance_checks

    target = tmp_path / "value.txt"
    target.write_text("before")
    entered, release = asyncio.Event(), asyncio.Event()

    async def observe(*_args):
        entered.set()
        await release.wait()
        return {"passed": True}

    monkeypatch.setattr(acceptance_checks, "_command_result", observe)
    task = asyncio.create_task(run_checks(tmp_path, parse_checks([
        {"kind": "command", "argv": ["fixture"], "inputs": ["value.txt"]},
    ])))
    await entered.wait()
    target.write_text("after")
    release.set()
    assert (await task)["freshness"] == "stale"


@pytest.mark.parametrize("field,value", [
    ("inputs", []), ("inputs", ["../outside"]), ("inputs", ["x", "x"]),
    ("requirement_ids", ["r", "r"]), ("requirement_ids", [""]),
    ("requirement_ids", ["x" * 129]), ("inputs", [str(i) for i in range(257)]),
])
def test_invalid_declared_scope_and_requirement_ids_are_rejected(field, value):
    with pytest.raises(ValueError):
        parse_checks([{"kind": "command", "argv": ["fixture"], field: value}])


async def test_legacy_report_and_tampered_input_binding_never_claim_current_pass(tmp_path):
    (tmp_path / "value.txt").write_text("value")
    service = PlanExecutionService(tmp_path)
    plan = service.create_plan(steps=["Check"], checks=[{"kind": "file_exists", "path": "value.txt"}])
    await service.verify_plan(plan.plan_id)
    index = tmp_path / ".henchman/plans/verification.json"
    original = json.loads(index.read_text())
    for evidence in (None, {"version": 999}, {"version": 1, "paths": ["other"]}):
        payload = copy.deepcopy(original)
        if evidence is None:
            payload[0]["last_verification"].pop("input_evidence")
        else:
            payload[0]["last_verification"]["input_evidence"] = evidence
        index.write_text(json.dumps(payload))
        assert service.verification_status(plan.plan_id)["current_checks_passed"] is False


async def test_declared_symlink_inputs_cannot_establish_current_proof(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.write_text("private")
    try:
        (tmp_path / "link").symlink_to(outside)
    except OSError as error:
        pytest.skip(f"Host cannot create a symlink: {error}")
    report = await run_checks(tmp_path, parse_checks([
        {"kind": "command", "argv": [sys.executable, "-c", "pass"], "inputs": ["link"]},
    ]))
    assert report["current_checks_passed"] is False
    assert report["freshness"] == "unverified"


@pytest.mark.parametrize("failure", [TimeoutError, FileNotFoundError])
async def test_unavailable_checks_are_incomplete_with_actionable_observations(tmp_path, monkeypatch, failure):
    from henchman.advanced import acceptance_checks

    (tmp_path / "value.txt").write_text("value")
    service = PlanExecutionService(tmp_path)
    plan = service.create_plan(steps=["Check"], checks=[
        {"kind": "command", "argv": ["fixture"], "inputs": ["value.txt"]},
    ])

    async def fail(*_args):
        raise failure("Required executable unavailable")

    monkeypatch.setattr(acceptance_checks, "_command_result", fail)
    report = await service.verify_plan(plan.plan_id)
    assert report["results"][0]["status"] == ("timeout" if failure is TimeoutError else "not_run")
    assert report["results"][0]["error"]
    assert service.verification_status(plan.plan_id)["status"] == "incomplete"


async def test_cancelled_input_capture_joins_reader_before_returning(tmp_path, monkeypatch):
    import threading

    from henchman.advanced import verification_inputs

    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = verification_inputs.WorkspaceFiles.state
    (tmp_path / "value.txt").write_text("value")

    def slow(reader, path):
        entered.set()
        assert release.wait(5)
        try:
            return original(reader, path)
        finally:
            finished.set()

    monkeypatch.setattr(verification_inputs.WorkspaceFiles, "state", slow)
    worker = asyncio.create_task(verification_inputs.capture_inputs_async(tmp_path, ("value.txt",)))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        worker.cancel("first cancellation")
        await asyncio.sleep(0)
        worker.cancel("second cancellation")
        await asyncio.sleep(0)
        assert not worker.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError, match="first cancellation"):
        await worker
    assert finished.is_set()


@pytest.mark.parametrize("limit", ["bytes", "time", "files"])
def test_input_observation_limits_are_explicit(tmp_path, monkeypatch, limit):
    from henchman.advanced import verification_inputs

    (tmp_path / "value.txt").write_text("value")
    if limit == "bytes":
        monkeypatch.setattr(verification_inputs, "MAX_INPUT_BYTES", 1)
    elif limit == "time":
        monkeypatch.setattr(verification_inputs, "MAX_CAPTURE_SECONDS", 0)
    paths = ("value.txt",) if limit != "files" else tuple(str(i) for i in range(257))
    observation = verification_inputs.capture_inputs(tmp_path, paths)
    assert observation["status"] == "unavailable"
    assert observation["reason"]


async def test_runtime_tool_retains_declared_scope_and_detects_later_edits(tmp_path, monkeypatch):
    from henchman.tools.builtins.tier6_tools import VerifyPlanExecutionTool
    from henchman.tools.registry import ToolRegistry

    monkeypatch.chdir(tmp_path)
    target = tmp_path / "module.py"
    target.write_text("value = 1\n")
    registry = ToolRegistry()
    tool = VerifyPlanExecutionTool()
    tool.bind_runtime(project_root=tmp_path)
    registry.register(tool)

    async def approve(_request):
        return True

    registry.set_confirmation_handler(approve)
    created = await registry.execute("verify_plan_execution", {"action": "create", "steps": ["Check"],
        "checks": [{"kind": "command", "argv": [sys.executable, "-c", "pass"],
                    "inputs": ["module.py"], "requirement_ids": ["REQ-1"]}]})
    assert created.success, created.content
    plan, = PlanExecutionService(tmp_path).list_plans()
    observed = await registry.execute("verify_plan_execution", {"action": "verify", "plan_id": plan.plan_id})
    assert observed.success and json.loads(observed.content)["current_checks_passed"] is True
    target.write_text("value = 2\n")
    status = await registry.execute("verify_plan_execution", {"action": "status", "plan_id": plan.plan_id})
    assert "stale" in status.content.lower()


async def test_checks_cannot_validate_different_intermediate_file_contents(tmp_path):
    path = tmp_path / "value.txt"
    path.write_text("bad")
    service = PlanExecutionService(tmp_path)
    plan = service.create_plan(steps=["Check"], checks=[
        {"kind": "command", "argv": [sys.executable, "-c", "from pathlib import Path; Path('value.txt').write_text('good')"], "inputs": ["value.txt"]},
        {"kind": "file_contains", "path": "value.txt", "text": "good"},
        {"kind": "command", "argv": [sys.executable, "-c", "from pathlib import Path; Path('value.txt').write_text('bad')"], "inputs": ["value.txt"]},
    ])
    report = await service.verify_plan(plan.plan_id)
    assert path.read_text() == "bad"
    assert all(result["passed"] for result in report["results"])
    assert report["freshness"] == "stale"
    assert not report["checks_passed"]
    assert service.verification_status(plan.plan_id)["status"] == "stale"


@pytest.mark.parametrize("mutation", ["summary", "missing_result", "index", "spec", "passed_type", "status"])
async def test_inconsistent_saved_results_never_establish_current_pass(tmp_path, mutation):
    (tmp_path / "value.txt").write_text("bad")
    service = PlanExecutionService(tmp_path)
    plan = service.create_plan(steps=["Check"], checks=[{"kind": "file_contains", "path": "value.txt", "text": "good"}])
    await service.verify_plan(plan.plan_id)
    index = tmp_path / ".henchman/plans/verification.json"
    records = json.loads(index.read_text())
    report = records[0]["last_verification"]
    report["checks_passed"] = True
    if mutation == "missing_result":
        report["results"] = []
    elif mutation == "index":
        report["results"][0]["index"] = 5
    elif mutation == "spec":
        report["results"][0]["check"]["text"] = "bad"
    elif mutation == "passed_type":
        report["results"][0]["passed"] = "true"
    elif mutation == "status":
        report["results"][0]["status"] = "pass"
    index.write_text(json.dumps(records))
    status = service.verification_status(plan.plan_id)
    assert not status["current_checks_passed"]
    assert status["status"] == "unverified"


@pytest.mark.parametrize("interrupt", ["deadline", "cancel"])
def test_last_input_read_cannot_publish_after_stop_or_deadline(tmp_path, monkeypatch, interrupt):
    import threading

    from henchman.advanced import verification_inputs

    (tmp_path / "value.txt").write_text("value")
    stopped = threading.Event()
    now = [0.0]
    monkeypatch.setattr(verification_inputs.time, "monotonic", lambda: now[0])
    original = verification_inputs.WorkspaceFiles.state

    def interrupted(reader, path):
        result = original(reader, path)
        if interrupt == "deadline":
            now[0] = 10.0
        else:
            stopped.set()
        return result

    monkeypatch.setattr(verification_inputs.WorkspaceFiles, "state", interrupted)
    assert verification_inputs.capture_inputs(tmp_path, ("value.txt",), stopped)["status"] == "unavailable"


async def test_cancellation_during_file_assertion_joins_reader(tmp_path, monkeypatch):
    import threading

    from henchman.advanced import acceptance_checks

    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    (tmp_path / "value.txt").write_text("value")
    original = acceptance_checks._file_result

    def blocked(*args):
        entered.set()
        assert release.wait(5)
        try:
            return original(*args)
        finally:
            finished.set()

    monkeypatch.setattr(acceptance_checks, "_file_result", blocked)
    checking = asyncio.create_task(run_checks(tmp_path, parse_checks([{"kind": "file_exists", "path": "value.txt"}])))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        checking.cancel()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert not checking.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await checking
    assert finished.is_set()


@pytest.mark.parametrize("digest", [None, "0" * 64])
@pytest.mark.parametrize("saved_freshness", ["current", "unverified"])
async def test_changed_saved_file_observation_digest_revokes_current_proof(tmp_path, digest, saved_freshness):
    (tmp_path / "value.txt").write_text("good")
    service = PlanExecutionService(tmp_path)
    plan = service.create_plan(steps=["Check"], checks=[{"kind": "file_contains", "path": "value.txt", "text": "good"}])
    await service.verify_plan(plan.plan_id)
    index = tmp_path / ".henchman/plans/verification.json"
    records = json.loads(index.read_text())
    report = records[0]["last_verification"]
    report["freshness"] = saved_freshness
    if digest is None:
        report["results"][0].pop("sha256")
    else:
        report["results"][0]["sha256"] = digest
    index.write_text(json.dumps(records))
    assert service.verification_status(plan.plan_id)["status"] == "unverified"


async def test_saved_unverified_proof_cannot_be_upgraded_by_status_read(tmp_path):
    (tmp_path / "value.txt").write_text("good")
    service = PlanExecutionService(tmp_path)
    plan = service.create_plan(steps=["Check"], checks=[{"kind": "file_exists", "path": "value.txt"}])
    await service.verify_plan(plan.plan_id)
    index = tmp_path / ".henchman/plans/verification.json"
    records = json.loads(index.read_text())
    records[0]["last_verification"]["freshness"] = "unverified"
    index.write_text(json.dumps(records))
    assert service.verification_status(plan.plan_id)["status"] == "unverified"


def test_aggregate_check_scope_is_bounded_before_persistence(tmp_path):
    paths = ["/".join(["p" * 200] * 8 + [f"value-{i}.txt"]) for i in range(256)]
    with pytest.raises(ValueError, match="512 KiB"):
        PlanExecutionService(tmp_path).create_plan(steps=["Check"], checks=[
            {"kind": "command", "argv": ["fixture"], "inputs": paths} for _ in range(20)
        ])
    assert not (tmp_path / ".henchman/plans/verification.json").exists()


async def test_per_check_observations_keep_only_bounded_fingerprint_summaries(tmp_path, monkeypatch):
    from henchman.advanced import acceptance_checks

    async def observed(*_args):
        return {"passed": True}

    monkeypatch.setattr(acceptance_checks, "_command_result", observed)
    paths = [f"input-{i}.py" for i in range(128)]
    service = PlanExecutionService(tmp_path)
    plan = service.create_plan(steps=["Check"], checks=[
        {"kind": "command", "argv": ["fixture"], "inputs": paths} for _ in range(20)
    ])
    report = await service.verify_plan(plan.plan_id)
    assert report["current_checks_passed"] is True
    assert len(json.dumps(report)) < 150_000
    assert all("files" not in item[phase] for item in report["input_evidence"]["observations"] for phase in ("before", "after"))


async def test_failed_final_report_save_records_incomplete_terminal_state(tmp_path, monkeypatch):
    (tmp_path / "value.txt").write_text("value")
    service = PlanExecutionService(tmp_path)
    plan = service.create_plan(steps=["Check"], checks=[{"kind": "file_exists", "path": "value.txt"}])
    original = service._persist_records

    def reject_full_report():
        if service._records[plan.plan_id].last_verification["status"] == "finished":
            raise ValueError("Plan storage exceeds the 16 MiB limit.")
        original()

    monkeypatch.setattr(service, "_persist_records", reject_full_report)
    with pytest.raises(ValueError, match="16 MiB"):
        await service.verify_plan(plan.plan_id)
    stored = PlanExecutionService(tmp_path).get_plan(plan.plan_id).last_verification
    assert stored["status"] == "error"
    assert stored["checks_passed"] is False and stored["error"]
