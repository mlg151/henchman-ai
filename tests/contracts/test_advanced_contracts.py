"""Contract tests for Tier 6 advanced service models.

These tests validate that PlanRecord and TaskRecord payloads conform to
their published JSON Schema contracts.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from henchman.advanced.plans import PlanRecord, PlanStepRecord
from henchman.advanced.repl import ReplEntryRecord, ReplSessionRecord
from henchman.advanced.schedule import CronScheduleRecord
from henchman.advanced.tasks import TaskRecord
from henchman.advanced.tungsten import TungstenFileRecord, TungstenSnapshotRecord
from tests.contracts.helpers import assert_contract_matches


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
