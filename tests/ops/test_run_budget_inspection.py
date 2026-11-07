"""Inspect existing accounting without creating, migrating or rewriting storage."""

import sqlite3
from pathlib import Path

import pytest

from henchman.core.run_budget import BudgetAccountingError, BudgetLimits, RequestEstimate
from henchman.ops.run_budget_store import RunBudgetStore
from henchman.ops.store import OpsStore


def test_inspection_creates_no_store_or_namespace(tmp_path: Path) -> None:
    missing = tmp_path / "missing" / "ops.db"
    assert RunBudgetStore.inspect_session(missing, "p", "s") is None
    assert not missing.parent.exists()
    path = tmp_path / "existing.db"
    OpsStore(path)
    before = path.read_bytes()
    assert RunBudgetStore.inspect_session(path, "p", "s") is None
    assert path.read_bytes() == before


def test_inspection_reads_authoritative_usage_without_writes(tmp_path: Path) -> None:
    path = tmp_path / "ops.db"
    store = RunBudgetStore(path)
    ledger = store.create_run(project_hash="p", session_id="s", limits=BudgetLimits(max_requests=1))
    request = ledger.reserve(RequestEstimate(1, 1))
    ledger.start(request.request_id)
    reference = store.session_binding("p", "s")
    before = path.read_bytes()
    inspection = RunBudgetStore.inspect_session(path, "p", "s", reference=reference)
    assert inspection.reference == reference
    assert inspection.snapshot.run_id == ledger.run_id
    assert inspection.snapshot.consumed_requests == 1
    assert inspection.snapshot.remaining_requests == 0
    assert path.read_bytes() == before


def test_corrupt_referenced_state_is_an_error_not_empty_accounting(tmp_path: Path) -> None:
    path = tmp_path / "ops.db"
    store = RunBudgetStore(path)
    store.create_run(project_hash="p", session_id="s")
    reference = store.session_binding("p", "s")
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE budget_runs SET state_json='{}'")
    with pytest.raises(BudgetAccountingError):
        RunBudgetStore.inspect_session(path, "p", "s", reference=reference)
    path.unlink()
    with pytest.raises(BudgetAccountingError):
        RunBudgetStore.inspect_session(path, "p", "s", reference=reference)
    assert not path.exists()


def test_inspection_preserves_unverified_time_and_rejects_wrong_identity(tmp_path: Path) -> None:
    from dataclasses import replace

    path = tmp_path / "ops.db"
    store = RunBudgetStore(path, clock=lambda: 0)
    store.create_run(project_hash="p", session_id="s", limits=BudgetLimits(max_seconds=5))
    reference = store.session_binding("p", "s")
    inspection = RunBudgetStore.inspect_session(path, "p", "s", reference=reference)
    assert inspection.snapshot.remaining_seconds is None
    assert inspection.snapshot.accounting_error == "time_origin_unverified"
    with pytest.raises(BudgetAccountingError, match="identity"):
        RunBudgetStore.inspect_session(path, "p", "s", reference=replace(reference, store_id="another"))
    with pytest.raises(BudgetAccountingError, match="identity"):
        RunBudgetStore.inspect_session(path, "p", "different", reference=reference)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE schema_versions SET version=999 WHERE namespace='run_budget'")
    with pytest.raises(BudgetAccountingError, match="unsupported_schema"):
        RunBudgetStore.inspect_session(path, "p", "s")
