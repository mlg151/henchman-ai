"""Contract tests for Tier 6 advanced service models.

These tests validate that PlanRecord and TaskRecord payloads conform to
their published JSON Schema contracts.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from henchman.advanced.plans import PlanRecord, PlanStepRecord
from henchman.advanced.repl import ReplEntryRecord, ReplSessionRecord
from henchman.advanced.schedule import CronScheduleRecord
from henchman.advanced.tasks import TaskRecord
from henchman.advanced.tungsten import TungstenFileRecord, TungstenSnapshotRecord
from tests.contracts.helpers import assert_contract_matches, load_contract_schema


async def test_plan_repair_contract_retains_bounded_historical_observations(tmp_path, contract_suite):
    from henchman.advanced.plans import PlanExecutionService
    from henchman.advanced.verification_repair import RepairRequest, VerificationRepairSession

    (tmp_path / "target.py").write_text("answer = 2\n")
    (tmp_path / "criteria.txt").write_text("Required answer remains 2.\n")
    service = PlanExecutionService(tmp_path)
    plan = service.create_plan(steps=["Check declared answer"], checks=[
        {"kind": "file_contains", "path": "target.py", "text": "answer = 2"},
    ])
    repair = VerificationRepairSession(service, RepairRequest(
        plan_id=plan.plan_id, edit_paths=("target.py",), protected_paths=("criteria.txt",), max_repairs=0,
    ))

    async def unexpected_repair(_attempt):
        pytest.fail("Already passing checks must not dispatch a repair")

    report = await repair.run(unexpected_repair)
    assert report.status == "scoped_pass" and report.task_verified is False
    payload = service.get_plan(plan.plan_id).to_dict()
    assert_contract_matches(contract_suite=contract_suite, payload=payload, schema_name="advanced/plan_record")
    validator = Draft7Validator(load_contract_schema("advanced/plan_record"))
    validator.validate(payload)
    for name, value in (("task_verified", True), ("version", 2), ("resume_authority", "forged")):
        invalid = deepcopy(payload)
        invalid["last_repair"][name] = value
        assert not validator.is_valid(invalid)


@pytest.mark.parametrize("fault", ["reason", "digest", "extra", "executable_checks"])
def test_unavailable_plan_checks_contract_rejects_replay_shapes(sample_plan_record, fault):
    payload = sample_plan_record.to_dict()
    payload["checks_unavailable"] = {"reason": "credential_sensitive", "spec_digest": "a" * 64}
    if fault == "reason":
        payload["checks_unavailable"]["reason"] = "unknown"
    elif fault == "digest":
        payload["checks_unavailable"]["spec_digest"] = "not-a-digest"
    elif fault == "extra":
        payload["checks_unavailable"]["argv"] = ["must-not-replay"]
    else:
        payload["checks"] = [{"kind": "command", "argv": ["must-not-replay"]}]
    assert not Draft7Validator(load_contract_schema("advanced/plan_record")).is_valid(payload)


def test_unavailable_plan_checks_contract_retains_only_original_digest(contract_suite, sample_plan_record):
    payload = sample_plan_record.to_dict()
    payload["checks_unavailable"] = {"reason": "credential_sensitive", "spec_digest": "a" * 64}
    assert_contract_matches(contract_suite=contract_suite, payload=payload, schema_name="advanced/plan_record")
    Draft7Validator(load_contract_schema("advanced/plan_record")).validate(payload)


@pytest.fixture
def sample_plan_record() -> PlanRecord:
    """A representative PlanRecord."""
    steps = (
        PlanStepRecord(
            index=0,
            text="Step 1",
            done=True,
            evidence="Evidence 1",
            completed_at="2026-04-24T12:00:00Z",
        ),
        PlanStepRecord(
            index=1,
            text="Step 2",
            done=False,
            evidence=None,
            completed_at=None,
        ),
    )
    return PlanRecord(
        plan_id="plan-123",
        title="Test Plan",
        created_at="2026-04-24T11:55:00Z",
        updated_at="2026-04-24T12:00:05Z",
        steps=steps,
    )


@pytest.fixture
def sample_task_record() -> TaskRecord:
    """A representative TaskRecord."""
    return TaskRecord(
        task_id="task-456",
        title="Test Task",
        argv=("ls", "-la"),
        cwd="/home/user",
        status="running",
        created_at="2026-04-24T12:10:00Z",
        started_at="2026-04-24T12:10:01Z",
        finished_at=None,
        output_path=Path("/tmp/task-456.log"),
        pid=1234,
        return_code=None,
        metadata={"priority": "high"},
    )


@pytest.fixture
def sample_tungsten_snapshot() -> TungstenSnapshotRecord:
    """A representative TungstenSnapshotRecord."""
    files = (
        TungstenFileRecord(path="src/main.py", sha256="a" * 64),
        TungstenFileRecord(path="README.md", sha256="b" * 64),
    )
    return TungstenSnapshotRecord(
        snapshot_id="snapshot-123",
        name="test-snapshot",
        created_at="2026-04-24T12:00:00Z",
        files=files,
    )


@pytest.fixture
def sample_cron_schedule() -> CronScheduleRecord:
    """A representative CronScheduleRecord."""
    return CronScheduleRecord(
        schedule_id="schedule-123",
        title="Test Schedule",
        cron="0 12 * * *",
        argv=("ls", "-la"),
        enabled=True,
        created_at="2026-04-24T12:00:00Z",
        updated_at="2026-04-24T12:00:00Z",
    )


@pytest.fixture
def sample_repl_session() -> ReplSessionRecord:
    """A representative ReplSessionRecord."""
    history = (
        ReplEntryRecord(code="print('hello')", output="hello", created_at="2026-04-24T12:00:05Z"),
    )
    return ReplSessionRecord(
        session_id="repl-123",
        name="test-repl",
        created_at="2026-04-24T12:00:00Z",
        updated_at="2026-04-24T12:00:05Z",
        closed_at=None,
        history=history,
    )


class TestAdvancedServiceContracts:
    """Advanced service models must satisfy their JSON Schema contracts."""

    def test_plan_record_matches_contract(
        self, contract_suite: object, sample_plan_record: PlanRecord
    ) -> None:
        payload = sample_plan_record.to_dict()
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="advanced/plan_record",
        )

    def test_task_record_matches_contract(
        self, contract_suite: object, sample_task_record: TaskRecord
    ) -> None:
        payload = sample_task_record.to_dict()
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="advanced/task_record",
        )

    def test_tungsten_snapshot_matches_contract(
        self, contract_suite: object, sample_tungsten_snapshot: TungstenSnapshotRecord
    ) -> None:
        payload = sample_tungsten_snapshot.to_dict()
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="advanced/tungsten_snapshot",
        )

    def test_cron_schedule_matches_contract(
        self, contract_suite: object, sample_cron_schedule: CronScheduleRecord
    ) -> None:
        payload = sample_cron_schedule.to_dict()
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="advanced/cron_schedule",
        )

    def test_repl_session_matches_contract(
        self, contract_suite: object, sample_repl_session: ReplSessionRecord
    ) -> None:
        payload = sample_repl_session.to_dict()
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="advanced/repl_session",
        )
