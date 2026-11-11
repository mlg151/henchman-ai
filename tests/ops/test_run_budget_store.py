"""SQLite accounting is authoritative across independent handles and processes."""

import json
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from decimal import Decimal
from pathlib import Path
from threading import Event

import pytest

from henchman.core.run_budget import (
    BudgetAccountingError,
    BudgetExceeded,
    BudgetLimits,
    RequestEstimate,
)
from henchman.ops.run_budget_store import RunBudgetStore
from henchman.providers.usage import TokenPricing, UsageReport


def test_reopen_retains_unknown_dispatch_and_idempotent_observations(tmp_path: Path) -> None:
    path = tmp_path / "ops.db"
    store = RunBudgetStore(path)
    ledger = store.create_run(run_id="run", limits=BudgetLimits(max_requests=1, max_tokens=20))
    ledger.reserve(RequestEstimate(10, 10), request_id="request", operation_id="operation")
    assert ledger.start("request")
    ledger.cancel("request")
    restored = RunBudgetStore(path).resume_run("run", store_id=store.store_id)
    assert not restored.start("request")
    assert restored.snapshot().accounting_lifetime == "durable"
    assert restored.snapshot().held_tokens == 20
    assert restored.snapshot().unknown_dispatched_requests == 1
    with pytest.raises(BudgetExceeded):
        restored.reserve(RequestEstimate(1, 1))
    for _ in range(2):
        restored.reconcile("request", UsageReport(prompt_tokens=10, completion_tokens=2, source="reported"), final=True)
    assert restored.snapshot().settled_tokens == 12
    assert ledger.snapshot().settled_tokens == 12


def test_session_binding_cannot_reset_an_active_run(tmp_path: Path) -> None:
    store = RunBudgetStore(tmp_path / "ops.db")
    ledger = store.create_run(run_id="old", project_hash="project", session_id="session")
    assert store.session_binding("project", "session").active_run_id == "old"
    with pytest.raises(BudgetAccountingError, match="active_run"):
        store.create_run(run_id="new", project_hash="project", session_id="session")
    ledger.reserve(RequestEstimate(1, 1), request_id="unknown")
    ledger.start("unknown")
    store.finish_run("old")
    with pytest.raises(BudgetAccountingError, match="closed"):
        ledger.reserve(RequestEstimate(1, 1))
    store.create_run(run_id="new", project_hash="project", session_id="session")
    binding = store.session_binding("project", "session")
    assert binding.active_run_id == "new" and binding.run_ids == ("old", "new")
    assert ledger.snapshot().unknown_dispatched_requests == 1


def test_missing_wrong_and_cross_session_references_fail_closed(tmp_path: Path) -> None:
    store = RunBudgetStore(tmp_path / "ops.db")
    store.create_run(run_id="run", project_hash="project", session_id="session")
    for run_id, store_id, project, session in [
        ("missing", store.store_id, "project", "session"),
        ("run", "other-store", "project", "session"),
        ("run", store.store_id, "project", "other"),
    ]:
        with pytest.raises(BudgetAccountingError):
            store.resume_run(run_id, store_id=store_id, project_hash=project, session_id=session)
    (tmp_path / "ops.db").unlink()
    with pytest.raises(BudgetAccountingError):
        store.session_binding("project", "session")
    assert not (tmp_path / "ops.db").exists()


def test_price_strings_and_final_billing_survive_reopening(tmp_path: Path) -> None:
    store = RunBudgetStore(tmp_path / "ops.db")
    ledger = store.create_run(limits=BudgetLimits(max_cost=Decimal("0.02")))
    estimate = RequestEstimate(10, 10, TokenPricing.uniform(Decimal("0.123456789012345678901")))
    ledger.reserve(estimate, request_id="r")
    assert ledger.reserve(estimate, request_id="r").estimate == estimate
    with closing(sqlite3.connect(tmp_path / "ops.db")) as connection, connection:
        data = json.loads(connection.execute("SELECT payload_json FROM budget_attempts").fetchone()[0])
    assert data["estimate"]["pricing"]["input_per_1k"] == "0.123456789012345678901"
    assert ledger.start("r")
    restored = RunBudgetStore(tmp_path / "ops.db").resume_run(ledger.run_id, store_id=store.store_id)
    assert restored.snapshot().records[0].estimate == estimate


def test_failed_commit_never_authorizes_dispatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = RunBudgetStore(tmp_path / "ops.db")
    ledger = store.create_run()
    ledger.reserve(RequestEstimate(1, 1), request_id="request")
    def fail_commit(_connection: sqlite3.Connection) -> None:
        raise sqlite3.OperationalError("injected commit failure")
    monkeypatch.setattr(store, "_commit", fail_commit)
    with pytest.raises(BudgetAccountingError):
        ledger.start("request")
    restored = RunBudgetStore(tmp_path / "ops.db").resume_run(ledger.run_id, store_id=store.store_id)
    assert restored.snapshot().consumed_requests == 0
    assert restored.start("request")


def test_owner_is_immutable_and_bound_with_run_creation(tmp_path: Path) -> None:
    store = RunBudgetStore(tmp_path / "ops.db")
    ledger = store.create_run(run_id="r", project_hash="p", session_id="s", owner_key="goal:one")
    assert ledger.owner_key == "goal:one"
    assert store.session_binding("p", "s").active_owner_key == "goal:one"
    reopened = RunBudgetStore(tmp_path / "ops.db").resume_run("r", store_id=store.store_id, project_hash="p", session_id="s")
    assert reopened.owner_key == "goal:one"
    with pytest.raises(BudgetAccountingError):
        store.create_run(run_id="replacement", project_hash="p", session_id="s", owner_key="goal:two")
    assert store.session_binding("p", "s").active_run_id == "r"


@pytest.mark.parametrize("held_transaction", [False, True])
def test_independent_processes_contend_for_one_dispatch(tmp_path: Path, held_transaction: bool) -> None:
    path = tmp_path / "ops.db"
    store = RunBudgetStore(path)
    ledger = store.create_run(run_id="run", limits=BudgetLimits(max_requests=1))
    script = """
import sqlite3,sys,time
from pathlib import Path
from henchman.core.run_budget import BudgetAccountingError,BudgetExceeded,RequestEstimate
from henchman.ops.run_budget_store import RunBudgetStore
path,store_id,name,held=sys.argv[1:]
root=Path(path).parent
def checkpoint(boundary):
    if held=='True' and name=='0' and boundary=='reserve:before_commit':
        (root/'holding').touch()
        while not (root/'release').exists(): time.sleep(.01)
ledger=RunBudgetStore(Path(path),checkpoint=checkpoint).resume_run('run',store_id=store_id)
(root/('ready-'+name)).touch()
while not (root/'go').exists(): time.sleep(.01)
if held=='True' and name=='1':
    while not (root/'holding').exists(): time.sleep(.01)
try:
    request=ledger.reserve(RequestEstimate(1,1),request_id=name)
    result=ledger.start(request.request_id)
except BudgetExceeded:
    result=False
except BudgetAccountingError as error:
    cause=error.__cause__
    code=getattr(cause,'sqlite_errorcode',None)
    if (error.reason!='store_unavailable' or not isinstance(cause,sqlite3.OperationalError)
        or not isinstance(code,int) or code & 255 not in (sqlite3.SQLITE_BUSY,sqlite3.SQLITE_LOCKED)):
        raise
    result=False
    (root/('busy-'+name)).touch()
if result:
    (root/('effect-'+name)).write_text('admitted effect')
(root/('result-'+name)).write_text(str(result))
"""
    processes = [subprocess.Popen([sys.executable, "-c", script, str(path), store.store_id, str(i), str(held_transaction)]) for i in range(2)]
    try:
        deadline = time.monotonic() + 20
        while not all((tmp_path / f"ready-{i}").exists() for i in range(2)):
            assert time.monotonic() < deadline and all(p.poll() is None for p in processes)
            time.sleep(.01)
        (tmp_path / "go").touch()
        if held_transaction:
            # Release the owner only after its competitor has exhausted the
            # real SQLite busy timeout. No wall-clock sleep decides the race.
            assert processes[1].wait(timeout=20) == 0
            (tmp_path / "release").touch()
        for process in processes:
            assert process.wait(timeout=20) == 0
        outcomes = [(tmp_path / f"result-{i}").read_text() for i in range(2)]
        assert sorted(outcomes) == ["False", "True"]
        for i, outcome in enumerate(outcomes):
            assert (tmp_path / f"effect-{i}").exists() is (outcome == "True")
        if held_transaction:
            assert (tmp_path / "busy-1").exists()
            assert outcomes == ["True", "False"]
        assert ledger.snapshot().consumed_requests == 1
    finally:
        (tmp_path / "release").touch()
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)


@pytest.mark.parametrize("operation,committed", [(name, committed) for name in ("reserve", "start", "reconcile") for committed in (False, True)])
def test_process_death_at_commit_boundaries_never_refunds_dispatch(tmp_path: Path, operation: str, committed: bool) -> None:
    path = tmp_path / "ops.db"
    store = RunBudgetStore(path)
    ledger = store.create_run(run_id="run", limits=BudgetLimits(max_requests=1, max_tokens=20))
    if operation != "reserve":
        ledger.reserve(RequestEstimate(10, 10), request_id="request")
    if operation == "reconcile":
        ledger.start("request")
    boundary = f"{operation}:{'after' if committed else 'before'}_commit"
    script = """
import os,sys
from pathlib import Path
from henchman.core.run_budget import RequestEstimate
from henchman.ops.run_budget_store import RunBudgetStore
from henchman.providers.usage import UsageReport
path,store_id,operation,boundary=sys.argv[1:]
def checkpoint(name):
    if name==boundary: os._exit(73)
store=RunBudgetStore(Path(path),checkpoint=checkpoint)
ledger=store.resume_run('run',store_id=store_id)
if operation=='reserve': ledger.reserve(RequestEstimate(10,10),request_id='request')
elif operation=='start': ledger.start('request')
else: ledger.reconcile('request',UsageReport(prompt_tokens=10,completion_tokens=2,source='reported'),final=True)
"""
    result = subprocess.run([sys.executable, "-c", script, str(path), store.store_id, operation, boundary], timeout=20, check=False)
    assert result.returncode == 73
    restored = RunBudgetStore(path).resume_run("run", store_id=store.store_id)
    snapshot = restored.snapshot()
    dispatched = operation == "reconcile" or (operation == "start" and committed)
    assert snapshot.consumed_requests == int(dispatched)
    assert len(snapshot.records) == int(operation != "reserve" or committed)
    settled = operation == "reconcile" and committed
    assert snapshot.settled_tokens == (12 if settled else 0)
    assert snapshot.unknown_dispatched_requests == int(dispatched and not settled)
    if dispatched:
        assert not restored.start("request")


def test_time_capped_run_cannot_rebase_its_clock_after_process_restart(tmp_path: Path) -> None:
    path = tmp_path / "ops.db"
    store = RunBudgetStore(path)
    store.create_run(run_id="run", limits=BudgetLimits(max_seconds=1000))
    script = """
import sys
from pathlib import Path
from henchman.core.run_budget import BudgetAccountingError,RequestEstimate
from henchman.ops.run_budget_store import RunBudgetStore
ledger=RunBudgetStore(Path(sys.argv[1])).resume_run('run',store_id=sys.argv[2])
assert ledger.snapshot().remaining_seconds is None
assert ledger.snapshot().accounting_error=='time_origin_unverified'
try: ledger.reserve(RequestEstimate(1,1))
except BudgetAccountingError as exc: assert exc.reason=='time_origin_unverified'
else: raise AssertionError('Restart refunded time budget')
"""
    subprocess.run([sys.executable, "-c", script, str(path), store.store_id], timeout=20, check=True)


@pytest.mark.parametrize("damage", ["usage", "delete_attempt", "future_schema"])
def test_corrupt_or_newer_accounting_never_restores_an_empty_budget(tmp_path: Path, damage: str) -> None:
    path = tmp_path / "ops.db"
    store = RunBudgetStore(path)
    ledger = store.create_run()
    ledger.reserve(RequestEstimate(1, 1), request_id="r")
    ledger.start("r")
    with closing(sqlite3.connect(path)) as connection, connection:
        if damage == "usage":
            connection.execute("UPDATE budget_attempts SET payload_json='{}'")
        elif damage == "delete_attempt":
            connection.execute("DELETE FROM budget_attempts")
        else:
            connection.execute("UPDATE schema_versions SET version=999 WHERE namespace='run_budget'")
    with pytest.raises(BudgetAccountingError):
        ledger.snapshot()


def test_recovered_session_backup_cannot_refund_database_consumption(tmp_path: Path) -> None:
    from henchman.core.session import SessionManager

    manager = SessionManager(tmp_path / "sessions")
    session = manager.create_session("project")
    manager.save(session)
    store = RunBudgetStore(tmp_path / "ops.db")
    ledger = store.create_run(run_id="run", project_hash="project", session_id=session.id, limits=BudgetLimits(max_requests=1))
    session.accounting = store.session_binding("project", session.id)
    path = manager.save(session)
    ledger.reserve(RequestEstimate(1, 1), request_id="r")
    ledger.start("r")
    path.write_text("corrupt")
    with pytest.warns(UserWarning, match="Recovered"):
        recovered = manager.load(session.id)
    assert recovered.accounting is None  # Older transcript genuinely predates binding.
    binding = store.session_binding(recovered.project_hash, recovered.id)
    assert binding.active_run_id == "run"
    restored = store.resume_run(binding.active_run_id, store_id=binding.store_id, project_hash="project", session_id=session.id)
    with pytest.raises(BudgetExceeded):
        restored.reserve(RequestEstimate(1, 1))
    with pytest.raises(BudgetAccountingError, match="active_run_exists"):
        store.create_run(project_hash="project", session_id=session.id)


@pytest.mark.parametrize("committed", [False, True])
def test_migration_schema_and_version_commit_together(tmp_path: Path, committed: bool) -> None:
    path = tmp_path / "ops.db"
    script = """
import os,sys
from pathlib import Path
from henchman.ops.run_budget_store import RunBudgetStore
def checkpoint(name):
    if name==sys.argv[2]: os._exit(73)
RunBudgetStore(Path(sys.argv[1]),checkpoint=checkpoint)
"""
    boundary = f"migration:{'after' if committed else 'before'}_commit"
    result = subprocess.run([sys.executable, "-c", script, str(path), boundary], timeout=20, check=False)
    assert result.returncode == 73
    with closing(sqlite3.connect(path)) as connection, connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert ("budget_runs" in tables) is committed
        assert ("schema_versions" in tables) is committed
    store = RunBudgetStore(path)
    assert store.create_run().snapshot().consumed_requests == 0


def test_existing_ops_store_and_zero_prices_remain_usable(tmp_path: Path) -> None:
    from henchman.ops.store import OpsStore

    path = tmp_path / "ops.db"
    ops = OpsStore(path)
    ops.put_state("preserved", {"value": 1})
    store = RunBudgetStore(path)
    ledger = store.create_run(limits=BudgetLimits(max_cost=Decimal(0)))
    estimate = RequestEstimate(1, 1, TokenPricing.uniform(0))
    ledger.reserve(estimate, request_id="free")
    assert ledger.start("free")
    assert ledger.snapshot().remaining_cost == 0
    assert ops.get_state("preserved") == {"value": 1}


def test_float_price_retry_metadata_and_elapsed_floor_survive_transactions(tmp_path: Path) -> None:
    now = [10.0]
    store = RunBudgetStore(tmp_path / "ops.db", clock=lambda: now[0])
    ledger = store.create_run(limits=BudgetLimits(max_seconds=5))
    estimate = RequestEstimate(1, 1, TokenPricing.uniform(.12345))
    ledger.reserve(estimate, request_id="r")
    assert ledger.reserve(estimate, request_id="r").estimate.pricing.input_per_1k == Decimal(".12345")
    now[0] = 16
    with pytest.raises(BudgetExceeded, match="time_limit"):
        ledger.start("r")
    now[0] = 11
    assert ledger.snapshot().elapsed_seconds >= 6
    assert ledger.snapshot().held_tokens == 0


def test_lock_failure_and_replaced_store_do_not_admit_requests(tmp_path: Path) -> None:
    path = tmp_path / "ops.db"
    store = RunBudgetStore(path)
    ledger = store.create_run()
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        with pytest.raises(BudgetAccountingError, match="store_unavailable"):
            ledger.reserve(RequestEstimate(1, 1))
    assert not ledger.snapshot().records
    path.unlink()
    RunBudgetStore(path).create_run(run_id=ledger.run_id)
    with pytest.raises(BudgetAccountingError, match="identity"):
        ledger.reserve(RequestEstimate(1, 1))


def test_session_binding_does_not_hide_a_missing_authoritative_run(tmp_path: Path) -> None:
    path = tmp_path / "ops.db"
    store = RunBudgetStore(path)
    store.create_run(run_id="run", project_hash="project", session_id="session")
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("DELETE FROM budget_runs")
    with pytest.raises(BudgetAccountingError, match="missing_run"):
        store.session_binding("project", "session")


def test_creation_lock_wait_cannot_move_the_run_time_origin(tmp_path: Path) -> None:
    now = [0.0]
    entered = Event()

    def clock() -> float:
        observed = now[0]
        entered.set()
        return observed

    path = tmp_path / "ops.db"
    store = RunBudgetStore(path, clock=clock)
    with closing(sqlite3.connect(path)) as connection, connection, ThreadPoolExecutor(max_workers=1) as executor:
        connection.execute("BEGIN IMMEDIATE")
        future = executor.submit(store.create_run, limits=BudgetLimits(max_seconds=6))
        assert entered.wait(timeout=5)
        now[0] = 5
        connection.commit()
        ledger = future.result(timeout=5)
    assert ledger.snapshot().elapsed_seconds == 5
    now[0] = 9
    assert ledger.snapshot().elapsed_seconds == 9
    with pytest.raises(BudgetExceeded, match="time_limit"):
        ledger.reserve(RequestEstimate(1, 1))


def test_reopening_with_a_different_injected_clock_cannot_refund_elapsed_time(tmp_path: Path) -> None:
    path = tmp_path / "ops.db"
    now = [10.0]
    store = RunBudgetStore(path, clock=lambda: now[0])
    ledger = store.create_run(limits=BudgetLimits(max_seconds=1))
    now[0] = 20  # No intervening ledger call checkpoints elapsed time.
    reopened = RunBudgetStore(path, clock=lambda: 0).resume_run(ledger.run_id, store_id=store.store_id)
    assert reopened.snapshot().accounting_error == "time_origin_unverified"
    assert reopened.snapshot().remaining_seconds is None
    with pytest.raises(BudgetAccountingError, match="time_origin_unverified"):
        reopened.reserve(RequestEstimate(1, 1))


def test_native_monotonic_clock_is_shared_by_handles_in_the_same_process(tmp_path: Path) -> None:
    path = tmp_path / "ops.db"
    store = RunBudgetStore(path)
    ledger = store.create_run(limits=BudgetLimits(max_seconds=1000))
    reopened = RunBudgetStore(path).resume_run(ledger.run_id, store_id=store.store_id)
    assert reopened.snapshot().accounting_error is None
    record = reopened.reserve(RequestEstimate(1, 1))
    assert reopened.start(record.request_id)
