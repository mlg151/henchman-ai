"""Provider-side contract verification for advanced services."""

from __future__ import annotations

from pathlib import Path

from henchman.advanced.repl import ExperimentReplService
from henchman.advanced.schedule import CronScheduleService
from henchman.advanced.tungsten import TungstenService
from tests.contracts.helpers import assert_contract_matches


def test_tungsten_service_produces_contract_compliant_snapshots(tmp_path: Path, contract_suite) -> None:
    """TungstenService should produce snapshots that satisfy the TungstenSnapshotRecord contract."""
    service = TungstenService(project_root=tmp_path)

    test_file = tmp_path / "test.txt"
    test_file.write_text("hello", encoding="utf-8")

    snapshot = service.snapshot(name="test", paths=["test.txt"])

    assert_contract_matches(
        payload=snapshot.to_dict(),
        schema_name="advanced/tungsten_snapshot",
        contract_suite=contract_suite,
    )


def test_cron_service_produces_contract_compliant_schedules(tmp_path: Path, contract_suite) -> None:
    """CronScheduleService should produce schedules that satisfy the CronScheduleRecord contract."""
    service = CronScheduleService(project_root=tmp_path)

    schedule = service.create_schedule(
        title="Nightly Check",
        cron="0 0 * * *",
        argv=["ls", "-la"]
    )

    assert_contract_matches(
        payload=schedule.to_dict(),
        schema_name="advanced/cron_schedule",
        contract_suite=contract_suite,
    )


def test_repl_service_produces_contract_compliant_sessions(tmp_path: Path, contract_suite) -> None:
    """ExperimentReplService should produce sessions that satisfy the ReplSessionRecord contract."""
    service = ExperimentReplService(project_root=tmp_path)

    session = service.start_session(name="Test Session")
    service.execute(session.session_id, "x = 1")

    updated_session = service.get_session(session.session_id)
    assert updated_session is not None

    assert_contract_matches(
        payload=updated_session.to_dict(),
        schema_name="advanced/repl_session",
        contract_suite=contract_suite,
    )
