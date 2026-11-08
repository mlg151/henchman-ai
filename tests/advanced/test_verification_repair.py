"""Bounded repair observes real checks without granting restored execution."""

import asyncio
from contextlib import suppress

import pytest

from henchman.advanced.plans import PlanExecutionService
from henchman.advanced.verification_repair import RepairRequest, VerificationRepairSession
from henchman.config.schema import Settings


def setup(tmp_path, *, checks=None):
    (tmp_path / "target.py").write_text("answer = 1\n")
    (tmp_path / "criteria.txt").write_text("Keep the required answer assertion.\n")
    settings = Settings()
    service = PlanExecutionService(tmp_path, settings=settings)
    plan = service.create_plan(steps=["Inspect and repair"], checks=checks or [
        {"kind": "file_contains", "path": "target.py", "text": "answer = 2"},
    ])
    return service, plan, settings


def session(service, plan, **limits):
    return VerificationRepairSession(service, RepairRequest(
        plan_id=plan.plan_id, edit_paths=("target.py",), protected_paths=("criteria.txt",), **limits,
    ))


async def test_failed_check_repair_and_fresh_final_check_are_distinct_observations(tmp_path):
    service, plan, _ = setup(tmp_path)
    repair = session(service, plan)
    seen = []

    async def edit(attempt):
        seen.append(attempt.repair_index)
        assert (tmp_path / "target.py").read_text() == "answer = 1\n"
        await repair.admit_mutation(("target.py",))
        (tmp_path / "target.py").write_text("answer = 2\n")

    report = await repair.run(edit)
    assert seen == [1]
    assert report.status == "scoped_pass" and report.task_verified is False
    assert [item.status for item in report.observations] == ["fail", "pass"]
    assert service.get_plan(plan.plan_id).last_repair == report.to_dict()
    (tmp_path / "target.py").write_text("answer = 3\n")
    assert service.verification_status(plan.plan_id)["status"] == "stale"
    assert service.get_plan(plan.plan_id).last_repair["task_verified"] is False


async def test_repeated_identical_failure_stops_without_extra_repair(tmp_path):
    service, plan, _ = setup(tmp_path)
    repair = session(service, plan, max_repairs=5, max_identical_failures=2)
    attempts = []

    async def unchanged(attempt):
        attempts.append(attempt.repair_index)

    report = await repair.run(unchanged)
    assert attempts == [1]
    assert report.status == "incomplete" and report.reason == "identical_failure_limit"
    assert len(report.observations) == 2
    assert report.observations[-1].diagnostics


async def test_total_repair_limit_preserves_failed_final_observation(tmp_path):
    service, plan, _ = setup(tmp_path)
    repair = session(service, plan, max_repairs=2, max_identical_failures=5)

    async def wrong(attempt):
        await repair.admit_mutation(("target.py",))
        (tmp_path / "target.py").write_text(f"answer = {-attempt.repair_index}\n")

    report = await repair.run(wrong)
    assert report.status == "incomplete" and report.reason == "attempts_exhausted"
    assert report.repairs_started == 2 and len(report.observations) == 3
    assert not service.verification_status(plan.plan_id)["current_checks_passed"]


async def test_changed_criterion_stops_before_rechecking_weakened_assertion(tmp_path):
    service, plan, _ = setup(tmp_path)
    repair = session(service, plan)

    async def corrupt(_attempt):
        (tmp_path / "criteria.txt").write_text("weakened")
        (tmp_path / "target.py").write_text("answer = 2\n")

    report = await repair.run(corrupt)
    assert report.status == "incomplete" and report.reason == "criteria_changed"
    assert len(report.observations) == 1
    assert not service.get_plan(plan.plan_id).last_verification["checks_passed"]


@pytest.mark.parametrize("targets", [None, ("criteria.txt",), ("elsewhere.py",), ("../escape",)])
async def test_unknown_or_unapproved_mutation_scope_is_refused(tmp_path, targets):
    service, plan, _ = setup(tmp_path)
    repair = session(service, plan)
    effects = []

    async def unsupported(_attempt):
        await repair.admit_mutation(targets)
        effects.append("effect")

    report = await repair.run(unsupported)
    assert effects == []
    assert report.status == "incomplete" and report.reason == "mutation_unavailable"


async def test_injected_required_configuration_change_cannot_reset_repair_authority(tmp_path):
    service, plan, settings = setup(tmp_path)
    repair = session(service, plan)

    async def change(_attempt):
        settings.verification.checks = [{"kind": "file_exists", "path": "new-requirement"}]

    report = await repair.run(change)
    assert report.status == "incomplete" and report.reason == "authority_changed"
    assert len(report.observations) == 1


async def test_cancellation_joins_callback_and_persists_incomplete(tmp_path):
    service, plan, _ = setup(tmp_path)
    repair = session(service, plan)
    started, stopped = asyncio.Event(), asyncio.Event()

    async def blocked(_attempt):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    task = asyncio.create_task(repair.run(blocked))
    await asyncio.wait_for(started.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert stopped.is_set()
    report = service.get_plan(plan.plan_id).last_repair
    assert report["status"] == "incomplete" and report["reason"] == "cancelled"
    assert report["task_verified"] is False


async def test_missing_check_prerequisite_does_not_start_repair(tmp_path):
    service, plan, _ = setup(tmp_path, checks=[
        {"kind": "command", "argv": ["henchman-nonexistent-check-executable"], "inputs": ["target.py"]},
    ])
    repair = session(service, plan)

    async def forbidden(_attempt):
        pytest.fail("Missing prerequisites cannot authorize edits")

    report = await repair.run(forbidden)
    assert report.status == "incomplete" and report.reason == "checks_incomplete"
    assert report.repairs_started == 0


async def test_superseding_check_cannot_supply_another_invocations_pass(tmp_path):
    service, plan, _ = setup(tmp_path)
    (tmp_path / "target.py").write_text("answer = 2\n")
    repair = session(service, plan)

    async def superseded():
        original = await service.verify_plan(plan.plan_id)
        await service.verify_plan(plan.plan_id)
        return original

    report = await repair.run(lambda _: asyncio.sleep(0), verify=superseded)
    assert report.status == "incomplete"
    assert report.reason == "authority_changed"
    assert not report.observations


async def test_criterion_change_during_final_status_read_cannot_publish_pass(tmp_path, monkeypatch):
    service, plan, _ = setup(tmp_path)
    (tmp_path / "target.py").write_text("answer = 2\n")
    original = service.verification_status

    def raced(identity):
        status = original(identity)
        (tmp_path / "criteria.txt").write_text("weakened during final freshness check")
        return status

    monkeypatch.setattr(service, "verification_status", raced)
    report = await session(service, plan).run(lambda _: asyncio.sleep(0))
    assert report.status == "incomplete" and report.reason == "criteria_changed"


async def test_adapter_cannot_swallow_mutation_admission_refusal(tmp_path):
    service, plan, _ = setup(tmp_path)
    repair = session(service, plan)

    async def swallowed(_attempt):
        with suppress(Exception):
            await repair.admit_mutation(None)
        (tmp_path / "target.py").write_text("answer = 2\n")

    report = await repair.run(swallowed)
    assert report.status == "incomplete" and report.reason == "mutation_unavailable"
    assert len(report.observations) == 1


async def test_initial_save_lost_acknowledgement_records_failure_without_effect(tmp_path, monkeypatch):
    service, plan, _ = setup(tmp_path)
    save = service.save_repair_report
    failure = OSError("lost acknowledgement")

    def lost_ack(identity, report, *, start=False):
        result = save(identity, report, start=start)
        if start:
            raise failure
        return result

    monkeypatch.setattr(service, "save_repair_report", lost_ack)
    with pytest.raises(OSError) as caught:
        await session(service, plan).run(lambda _: pytest.fail("effect after failed admission"))
    assert caught.value is failure
    stored = service.get_plan(plan.plan_id).last_repair
    assert stored["status"] == "incomplete" and stored["reason"] == "persistence_error"
    assert stored["repairs_started"] == 0


async def test_overall_timeout_joins_owned_repair_and_retains_failure(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from henchman.advanced import verification_repair

    service, plan, _ = setup(tmp_path)
    repair = session(service, plan)
    stopped = asyncio.Event()
    timeouts = []

    def capture_timeout(delay):
        context = asyncio.timeout(delay)
        timeouts.append(context)
        return context

    local_asyncio = SimpleNamespace(**vars(asyncio))
    local_asyncio.timeout = capture_timeout
    monkeypatch.setattr(verification_repair, "asyncio", local_asyncio)

    async def blocked(_attempt):
        # Initial verification and durable admission may be slow on native
        # runners. Expire the actual overall timeout only after this owned
        # adapter starts; no production clock or cancellation handler is mocked.
        assert len(timeouts) == 1
        timeouts[0].reschedule(asyncio.get_running_loop().time())
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    report = await asyncio.wait_for(repair.run(blocked), repair.request.timeout_seconds + 10)
    assert timeouts[0].expired() and stopped.is_set()
    assert report.status == "incomplete" and report.reason == "timeout"
    assert len(report.observations) == 1
    assert service.get_plan(plan.plan_id).last_repair == report.to_dict()


async def test_cancellation_stays_primary_when_terminal_storage_fails(tmp_path, monkeypatch):
    service, plan, _ = setup(tmp_path)
    repair = session(service, plan)
    begun = asyncio.Event()
    save = service.save_repair_report

    def broken(identity, report, *, start=False):
        if report["status"] == "incomplete":
            raise OSError("terminal storage fault")
        return save(identity, report, start=start)

    async def blocked(_attempt):
        begun.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(service, "save_repair_report", broken)
    task = asyncio.create_task(repair.run(blocked))
    await asyncio.wait_for(begun.wait(), 2)
    task.cancel("original cancellation")
    with pytest.raises(asyncio.CancelledError, match="original cancellation") as caught:
        await task
    assert "Could not persist" in caught.value.__notes__[0]
    assert repair.report.status == "incomplete" and repair.report.reason == "cancelled"


async def test_editable_change_during_final_status_read_is_not_a_scoped_pass(tmp_path, monkeypatch):
    service, plan, _ = setup(tmp_path)
    (tmp_path / "target.py").write_text("answer = 2\n")
    original = service.verification_status

    def raced(identity):
        result = original(identity)
        (tmp_path / "target.py").write_text("answer = 9\n")
        return result

    monkeypatch.setattr(service, "verification_status", raced)
    report = await session(service, plan).run(lambda _: asyncio.sleep(0))
    assert report.status == "incomplete" and report.reason == "checks_incomplete"


@pytest.mark.parametrize("target", ["target.py", "TARGET.py"])
def test_criterion_and_edit_aliases_are_rejected_before_execution(target):
    with pytest.raises(ValueError, match="disjoint"):
        RepairRequest(plan_id="plan-example", edit_paths=(target,), protected_paths=("target.py",))


async def test_real_pytest_criterion_cannot_be_deleted_to_manufacture_a_pass(tmp_path):
    import sys

    criterion = tmp_path / "test_required.py"
    criterion.write_text("from pathlib import Path\ndef test_answer():\n    assert Path('target.py').read_text() == 'answer = 2\\n'\n")
    service, plan, _ = setup(tmp_path, checks=[
        {"kind": "command", "argv": [sys.executable, "-m", "pytest", "-q", "test_required.py"],
         "inputs": ["target.py", "test_required.py"]},
    ])
    repair = VerificationRepairSession(service, RepairRequest(
        plan_id=plan.plan_id, edit_paths=("target.py",), protected_paths=("test_required.py",),
    ))

    async def weaken(_attempt):
        criterion.write_text("def test_answer():\n    assert True\n")

    report = await repair.run(weaken)
    assert report.reason == "criteria_changed" and report.status == "incomplete"
    assert len(report.observations) == 1
    assert not service.verification_status(plan.plan_id)["current_checks_passed"]


async def test_run_ownership_cannot_be_replaced_or_replayed(tmp_path):
    service, plan, _ = setup(tmp_path)
    first = session(service, plan)
    second = session(PlanExecutionService(tmp_path), plan, max_repairs=0)

    async def replace_owner(_attempt):
        await second.run(lambda _: pytest.fail("zero repair budget"))

    with pytest.raises(ValueError, match="superseded"):
        await first.run(replace_owner)
    assert first.report.status == "incomplete" and first.report.reason == "persistence_error"
    assert service.get_plan(plan.plan_id).last_repair["run_id"] == second.report.run_id
    with pytest.raises(ValueError, match="already been used"):
        await first.run(replace_owner)


@pytest.mark.parametrize("shape", ["directory", "symlink", "excluded"])
async def test_unsupported_scopes_fail_without_callback(tmp_path, shape):
    service, plan, _ = setup(tmp_path)
    if shape == "directory":
        (tmp_path / "criteria.txt").unlink()
        (tmp_path / "criteria.txt").mkdir()
    elif shape == "symlink":
        (tmp_path / "criteria.txt").unlink()
        try:
            (tmp_path / "criteria.txt").symlink_to(tmp_path / "target.py")
        except OSError:
            pytest.skip("Native symlink privilege unavailable")
    else:
        (tmp_path / "criteria.txt").rename(tmp_path / ".env")
    repair = VerificationRepairSession(service, RepairRequest(
        plan_id=plan.plan_id, edit_paths=("target.py",),
        protected_paths=(".env" if shape == "excluded" else "criteria.txt",),
    ))
    report = await repair.run(lambda _: pytest.fail("unsupported scope dispatched"))
    assert report.reason == "scope_unavailable" and report.repairs_started == 0


async def test_credential_rotation_projects_read_without_writes_and_scrubs_at_write(tmp_path):
    import json

    service, plan, _ = setup(tmp_path)
    policy = service._policy
    secret = "repair-diagnostic-secret-59fd"

    async def failure(_attempt):
        raise RuntimeError("diagnostic " + secret)

    with pytest.raises(RuntimeError):
        await session(service, plan).run(failure)
    index = tmp_path / ".henchman/plans/verification.json"
    before = index.read_bytes()
    assert secret.encode() in before
    policy.register_secret(secret)
    projected = service.get_plan(plan.plan_id)
    assert secret not in json.dumps(projected.to_dict())
    assert index.read_bytes() == before
    service.sanitize_persisted_evidence()
    assert secret.encode() not in index.read_bytes()


async def test_error_projection_precedes_cutoff_and_preserves_primary(tmp_path):
    import json

    service, plan, _ = setup(tmp_path)
    secret = "known-repair-secret-98ab"
    service._policy.register_secret(secret)
    failure = RuntimeError("x" * 4090 + secret + "\nAuthorization: Bearer unknown-header-canary")

    async def fail(_attempt):
        raise failure

    with pytest.raises(RuntimeError) as caught:
        await session(service, plan).run(fail)
    assert caught.value is failure and secret in str(failure)
    raw = json.dumps(service.get_plan(plan.plan_id).to_dict())
    assert secret not in raw and "known-" not in raw and "unknown-header-canary" not in raw


async def test_initial_report_cannot_replay_observations_or_preclaim_criteria(tmp_path):
    service, plan, _ = setup(tmp_path)
    repair = session(service, plan, max_repairs=0)
    await repair.run(lambda _: pytest.fail("zero repair budget"))
    payload = repair.report.to_dict()
    payload.update(status="running", reason="running", observations=[], criteria_digest="a" * 64)
    with pytest.raises(ValueError, match="begin"):
        service.save_repair_report(plan.plan_id, payload, start=True)


@pytest.mark.parametrize("field,value", [
    ("version", True), ("task_verified", True), ("repairs_started", True),
    ("max_repairs", 11), ("timeout_seconds", float("inf")), ("run_id", "invalid"),
    ("plan_created_at", "credential-bearing-arbitrary-text"), ("started_at", "yesterday"),
    ("observations", [{}]), ("status", "scoped_pass"), ("error", "x" * 4097),
])
async def test_persisted_codec_rejects_invalid_or_unbounded_fields(tmp_path, field, value):
    from henchman.advanced.verification_repair import decode_repair_report

    service, plan, _ = setup(tmp_path)
    repair = session(service, plan, max_repairs=0)
    await repair.run(lambda _: pytest.fail("zero repair budget"))
    payload = repair.report.to_dict()
    payload[field] = value
    with pytest.raises(ValueError, match="invalid or exceeds"):
        decode_repair_report(payload)


async def test_terminal_persisted_owner_cannot_admit_another_effect(tmp_path):
    service, plan, _ = setup(tmp_path)
    repair = session(service, plan)
    effects = []

    async def revoked(_attempt):
        terminal = repair.report.to_dict()
        terminal.update(status="incomplete", reason="cancelled")
        service.save_repair_report(plan.plan_id, terminal)
        await repair.admit_mutation(("target.py",))
        effects.append("dispatch")
        (tmp_path / "target.py").write_text("answer = 2\n")

    report = await repair.run(revoked)
    assert effects == []
    assert report.status == "incomplete" and report.reason == "authority_changed"


async def test_adapter_cannot_convert_external_cancellation_into_success(tmp_path):
    service, plan, _ = setup(tmp_path)
    repair = session(service, plan)
    begun = asyncio.Event()

    async def swallowed(_attempt):
        begun.set()
        with suppress(asyncio.CancelledError):
            await asyncio.Event().wait()
        (tmp_path / "target.py").write_text("answer = 2\n")

    task = asyncio.create_task(repair.run(swallowed))
    await asyncio.wait_for(begun.wait(), 2)
    task.cancel("external stop")
    with pytest.raises(asyncio.CancelledError):
        await task
    assert repair.report.status == "incomplete" and repair.report.reason == "cancelled"
    assert service.get_plan(plan.plan_id).last_repair["status"] == "incomplete"


@pytest.mark.parametrize("kind", ["pytest", "command"])
@pytest.mark.parametrize("line_ending", ["native", "crlf"])
async def test_real_pytest_repeated_failure_ignores_only_runner_volatility(tmp_path, monkeypatch, kind, line_ending):
    import re
    import sys
    from dataclasses import replace

    from henchman.advanced import acceptance_checks

    criterion = tmp_path / "test_required.py"
    criterion.write_text("def test_required(tmp_path):\n    assert (tmp_path / 'required-output').exists()\n")
    check = {"kind": "pytest", "path": "test_required.py", "inputs": ["target.py"]} if kind == "pytest" else {
        "kind": "command", "argv": [sys.executable, "-m", "pytest", "-q", "test_required.py"],
        "inputs": ["target.py", "test_required.py"],
    }
    service, plan, _ = setup(tmp_path, checks=[check])
    actual = acceptance_checks.run_bounded_subprocess
    outputs = []

    async def timed(*args, **kwargs):
        result = await actual(*args, **kwargs)
        # Keep real pytest assertions/exit/evidence, but make timing variation
        # deterministic independently of scheduler speed and clock resolution.
        stdout, count = re.subn(rb" in \d+(?:\.\d+)?s", f" in {len(outputs) + 1}.00s".encode(), result.stdout)
        assert count == 1
        if line_ending == "crlf":
            # Windows subprocess pipes preserve CRLF even though pytest's
            # source and timing fields are identical to their POSIX shape.
            stdout = stdout.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        outputs.append(stdout)
        return replace(result, stdout=stdout)

    monkeypatch.setattr(acceptance_checks, "run_bounded_subprocess", timed)
    repair = VerificationRepairSession(service, RepairRequest(
        plan_id=plan.plan_id, edit_paths=("target.py",), protected_paths=("test_required.py",),
        max_repairs=2, max_identical_failures=2,
    ))
    report = await repair.run(lambda _: asyncio.sleep(0))
    assert report.reason == "identical_failure_limit" and report.repairs_started == 1
    assert outputs[0] != outputs[1]
    assert report.observations[0].failure_digest == report.observations[1].failure_digest
    assert report.observations[0].diagnostics != report.observations[1].diagnostics


@pytest.mark.parametrize("summary", ["1 failed in {elapsed}s", "=== 1 failed, 1 warning in {elapsed}s ==="])
def test_pytest_crlf_summary_normalizes_timing_without_erasing_diagnostics(summary):
    from henchman.advanced.verification_repair import _pytest_failure_text

    failure = "test_required.py::test_required\r\nE AssertionError: expected 12, received 34\r\n"
    first = failure + summary.format(elapsed="1.00") + "\r\n"
    second = failure + summary.format(elapsed="2.00") + "\r\n"
    normalized = _pytest_failure_text(first)
    assert normalized == _pytest_failure_text(second)
    assert normalized.startswith(failure) and normalized.endswith("\r\n")
    for old, new in [("received 34", "received 35"), ("test_required.py", "test_other.py"), ("1 failed", "2 failed")]:
        assert normalized != _pytest_failure_text(first.replace(old, new))
    # An assertion containing summary-like text is not runner metadata.
    assert _pytest_failure_text("E assert '1 failed in 1.00s'\r\n") != _pytest_failure_text("E assert '1 failed in 2.00s'\r\n")


async def test_real_pytest_substantively_different_failure_has_distinct_identity(tmp_path):
    import sys

    criterion = tmp_path / "test_required.py"
    criterion.write_text("from pathlib import Path\ndef test_required():\n    assert Path('target.py').read_text() == 'expected'\n")
    service, plan, _ = setup(tmp_path, checks=[{
        "kind": "command", "argv": [sys.executable, "-m", "pytest", "-q", "test_required.py"],
        "inputs": ["target.py", "test_required.py"],
    }])
    repair = VerificationRepairSession(service, RepairRequest(
        plan_id=plan.plan_id, edit_paths=("target.py",), protected_paths=("test_required.py",),
        max_repairs=1, max_identical_failures=2,
    ))

    async def edit(_attempt):
        await repair.admit_mutation(("target.py",))
        (tmp_path / "target.py").write_text("different substantive failure")

    report = await repair.run(edit)
    assert report.reason == "attempts_exhausted"
    assert report.observations[0].failure_digest != report.observations[1].failure_digest


@pytest.mark.parametrize("boundary", ["admission", "observation"])
async def test_synchronous_persistence_expiry_denies_next_repair_transition(tmp_path, monkeypatch, boundary):
    from types import SimpleNamespace

    from henchman.advanced import verification_repair

    service, plan, _ = setup(tmp_path)
    if boundary == "observation":
        (tmp_path / "target.py").write_text("answer = 2\n")
    repair = session(service, plan, timeout_seconds=120.0)
    clock = [10.0]
    monkeypatch.setattr(verification_repair, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    save = service.save_repair_report
    calls = []

    def delayed(identity, report, *, start=False):
        result = save(identity, report, start=start)
        crossed = report["repairs_started"] == 1 if boundary == "admission" else bool(report["observations"])
        if crossed and report["status"] == "running":
            clock[0] = 131.0
        return result

    async def adapter(attempt):
        calls.append(attempt.repair_index)

    monkeypatch.setattr(service, "save_repair_report", delayed)
    report = await repair.run(adapter)
    assert report.reason == "timeout" and report.status == "incomplete"
    assert calls == []
    assert report.repairs_started == (1 if boundary == "admission" else 0)
    assert [item.status for item in report.observations] == (["fail"] if boundary == "admission" else ["pass"])
    assert service.get_plan(plan.plan_id).last_repair == report.to_dict()


async def test_initial_persistence_consumes_the_same_async_deadline(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from henchman.advanced import verification_repair

    service, plan, _ = setup(tmp_path)
    repair = session(service, plan, timeout_seconds=5.0)
    elapsed = [0.0]
    monkeypatch.setattr(verification_repair, "time", SimpleNamespace(monotonic=lambda: elapsed[0]))
    save = service.save_repair_report
    joined = asyncio.Event()
    remaining = []
    deadlines = []

    class ControlledAsyncio:
        def __getattr__(self, name):
            return getattr(asyncio, name)

        def timeout(self, delay):
            remaining.append(delay)
            deadline = asyncio.timeout(None)
            deadlines.append(deadline)
            return deadline

    monkeypatch.setattr(verification_repair, "asyncio", ControlledAsyncio())

    def delayed(identity, report, *, start=False):
        result = save(identity, report, start=start)
        if start:
            elapsed[0] = 4.5
        return result

    async def adapter(_attempt):
        try:
            # Observe the actual reduced allowance, then expire the real async
            # timeout once owned work exists. CI speed cannot decide whether
            # prerequisite verification reaches this adapter in half a second.
            assert remaining == [0.5]
            elapsed[0] = 5.0
            deadlines[0].reschedule(asyncio.get_running_loop().time())
            await asyncio.Event().wait()
        finally:
            joined.set()

    monkeypatch.setattr(service, "save_repair_report", delayed)
    report = await asyncio.wait_for(repair.run(adapter), timeout=10)
    assert report.reason == "timeout" and report.status == "incomplete"
    assert joined.is_set()


async def test_wall_clock_rollback_during_cancellation_keeps_primary_and_observations(tmp_path, monkeypatch):
    from datetime import datetime, timedelta

    from henchman.advanced import verification_repair

    service, plan, _ = setup(tmp_path)
    repair = session(service, plan)
    begun = asyncio.Event()

    async def adapter(_attempt):
        begun.set()
        await asyncio.Event().wait()

    task = asyncio.create_task(repair.run(adapter))
    await asyncio.wait_for(begun.wait(), 2)
    previous = repair.report
    earlier = (datetime.fromisoformat(previous.started_at) - timedelta(seconds=1)).isoformat()
    monkeypatch.setattr(verification_repair, "_now", lambda: earlier)
    task.cancel("original cancellation")
    with pytest.raises(asyncio.CancelledError, match="original cancellation"):
        await task
    report = service.get_plan(plan.plan_id).last_repair
    assert report["status"] == "incomplete" and report["reason"] == "cancelled"
    assert report["updated_at"] == previous.updated_at
    assert report["observations"] == previous.to_dict()["observations"]


@pytest.mark.parametrize("boundary", ["projection", "construction", "persistence"])
async def test_cancellation_survives_every_secondary_interruption_reporting_failure(tmp_path, monkeypatch, boundary):
    service, plan, _ = setup(tmp_path)
    repair = session(service, plan)
    begun = asyncio.Event()

    async def adapter(_attempt):
        begun.set()
        await asyncio.Event().wait()

    task = asyncio.create_task(repair.run(adapter))
    await asyncio.wait_for(begun.wait(), 2)

    def broken(*_args, **_kwargs):
        raise ValueError("secondary-private-canary")

    if boundary == "projection":
        monkeypatch.setattr(service._policy, "text", broken)
    elif boundary == "construction":
        monkeypatch.setattr(repair, "_change", broken)
    else:
        monkeypatch.setattr(repair, "_save", broken)
    task.cancel("original cancellation")
    with pytest.raises(asyncio.CancelledError, match="original cancellation") as caught:
        await task
    assert any("Could not persist" in note for note in caught.value.__notes__)
    assert "secondary-private-canary" not in " ".join(caught.value.__notes__)
    assert repair._owner is None and not repair._editing


async def test_cancellation_with_unprintable_detail_remains_primary(tmp_path):
    service, plan, _ = setup(tmp_path)
    repair = session(service, plan)

    class UnprintableCancellation(asyncio.CancelledError):
        def __str__(self):
            raise ValueError("secondary-private-canary")

    primary = UnprintableCancellation()

    async def adapter(_attempt):
        raise primary

    with pytest.raises(asyncio.CancelledError) as caught:
        await repair.run(adapter)
    assert caught.value is primary
    assert any("Could not persist" in note for note in primary.__notes__)


@pytest.mark.parametrize("control", ["deadline", "cancellation", "queued_cancellation", "downgrade_cancellation"])
async def test_terminal_pass_acknowledgement_rechecks_controls_and_downgrades_evidence(tmp_path, monkeypatch, control):
    from types import SimpleNamespace

    from henchman.advanced import verification_repair

    service, plan, _ = setup(tmp_path)
    (tmp_path / "target.py").write_text("answer = 2\n")
    repair = session(service, plan, timeout_seconds=120.0)
    clock = [10.0]
    monkeypatch.setattr(verification_repair, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    save = service.save_repair_report
    published = []

    def delayed(identity, report, *, start=False):
        result = save(identity, report, start=start)
        if report["status"] == "scoped_pass":
            published.append(result)
            if control in {"deadline", "downgrade_cancellation"}:
                clock[0] = 131.0
            elif control == "queued_cancellation":
                asyncio.get_running_loop().call_soon(asyncio.current_task().cancel, "cancel during terminal acknowledgement")
            else:
                asyncio.current_task().cancel("cancel during terminal acknowledgement")
        elif control == "downgrade_cancellation" and report["reason"] == "timeout":
            asyncio.get_running_loop().call_soon(asyncio.current_task().cancel, "cancel during downgrade acknowledgement")
        return result

    monkeypatch.setattr(service, "save_repair_report", delayed)
    task = asyncio.create_task(repair.run(lambda _: asyncio.sleep(0)))
    if control != "deadline":
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        report = await task
        assert report.status == "incomplete" and report.reason == "timeout"
    assert len(published) == 1
    retained = service.get_plan(plan.plan_id).last_repair
    assert retained["status"] == "incomplete"
    assert retained["reason"] == ("timeout" if control == "deadline" else "cancelled")
    assert retained["run_id"] == published[0]["run_id"]
    assert retained["observations"] == published[0]["observations"]
    assert retained["criteria_digest"] == published[0]["criteria_digest"]
    assert retained["repairs_started"] == 0
    assert repair._owner is None and not repair._editing


async def test_admission_acknowledgement_yields_to_pending_cancellation_before_adapter(tmp_path, monkeypatch):
    service, plan, _ = setup(tmp_path)
    repair = session(service, plan)
    save = service.save_repair_report
    calls = []

    def delayed(identity, report, *, start=False):
        result = save(identity, report, start=start)
        if report["status"] == "running" and report["repairs_started"] == 1:
            asyncio.get_running_loop().call_soon(asyncio.current_task().cancel, "cancel during admission acknowledgement")
        return result

    async def adapter(attempt):
        calls.append(attempt.repair_index)
        await asyncio.sleep(0)

    monkeypatch.setattr(service, "save_repair_report", delayed)
    task = asyncio.create_task(repair.run(adapter))
    with pytest.raises(asyncio.CancelledError, match="cancel during admission acknowledgement"):
        await task
    assert calls == []
    retained = service.get_plan(plan.plan_id).last_repair
    assert retained["status"] == "incomplete" and retained["reason"] == "cancelled"
    assert retained["repairs_started"] == 1
    assert [item["status"] for item in retained["observations"]] == ["fail"]


@pytest.mark.parametrize("control", ["deadline", "cancellation"])
async def test_terminal_downgrade_cannot_overwrite_a_newer_repair_owner(tmp_path, monkeypatch, control):
    from types import SimpleNamespace
    from uuid import uuid4

    from henchman.advanced import verification_repair

    service, plan, _ = setup(tmp_path)
    (tmp_path / "target.py").write_text("answer = 2\n")
    # The injected clock controls the deadline race; leave the real event loop
    # enough time to reach terminal persistence on slow native filesystems.
    repair = session(service, plan, timeout_seconds=120.0)
    clock = [10.0]
    monkeypatch.setattr(verification_repair, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    capture = verification_repair.capture_inputs_async
    first_capture = True

    async def slow_first_capture(*args, **kwargs):
        nonlocal first_capture
        if first_capture:
            first_capture = False
            await asyncio.sleep(1.1)
        return await capture(*args, **kwargs)

    monkeypatch.setattr(verification_repair, "capture_inputs_async", slow_first_capture)
    save = service.save_repair_report
    replacement = []

    def superseded(identity, report, *, start=False):
        result = save(identity, report, start=start)
        if report["status"] == "scoped_pass":
            fresh = {**result, "run_id": uuid4().hex, "status": "running", "reason": "running",
                     "repairs_started": 0, "observations": [], "criteria_digest": None, "error": ""}
            replacement.append(save(identity, fresh, start=True))
            if control == "deadline":
                clock[0] = 131.0
            else:
                asyncio.current_task().cancel("cancel during terminal acknowledgement")
        return result

    monkeypatch.setattr(service, "save_repair_report", superseded)
    task = asyncio.create_task(repair.run(lambda _: asyncio.sleep(0)))
    expected = ValueError if control == "deadline" else asyncio.CancelledError
    try:
        result = await task
    except (ValueError, asyncio.CancelledError) as caught:
        assert isinstance(caught, expected)
        assert any("Could not persist" in note for note in caught.__notes__)
    else:
        pytest.fail(f"Expected {expected.__name__}; got {result.status}/{result.reason} with {len(replacement)} replacement(s)")
    assert len(replacement) == 1
    assert service.get_plan(plan.plan_id).last_repair == replacement[0]
    assert repair._owner is None and not repair._editing
