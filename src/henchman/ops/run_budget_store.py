"""Transactional run accounting with conservative crash/restart semantics.

The caller owns the database path and run lifecycle. Each mutation reloads the
authoritative state under BEGIN IMMEDIATE and commits before granting dispatch.
A committed start is never retried automatically, even if the process dies before
HTTP begins. No metrics, transcript backup, or sampled event can refund a hold.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path
from typing import Any, TypeVar, cast
from uuid import uuid4

from henchman.core.run_budget import (
    BudgetAccountingError,
    BudgetExceeded,
    BudgetLimits,
    BudgetSnapshot,
    ReportedCost,
    RequestEstimate,
    RequestRecord,
    RunBudgetLedger,
    _identifier,
)
from henchman.core.run_budget_state import encode_state, state_from_dict, state_to_dict
from henchman.core.session_data import SessionAccountingReference
from henchman.providers.usage import UsageReport

_PROCESS_TOKEN = uuid4().hex
_NATIVE_CLOCK = time.monotonic
_T = TypeVar("_T")


def _process_origin() -> str:
    # PID also changes after fork, where the module token would be inherited.
    return f"{os.getpid()}:{_PROCESS_TOKEN}"


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class SessionBudgetInspection:
    """Read-only session authority and its active or most recent run evidence."""

    reference: SessionAccountingReference
    snapshot: BudgetSnapshot | None


class RunBudgetStore:
    """Durable store at an explicitly injected path, with no implicit run creation.

    ``checkpoint`` is a synchronous fault-injection hook at commit boundaries.
    A time-capped run can continue only in its original process/clock domain;
    other processes may inspect/reconcile it but cannot authorize new dispatch.
    Native monotonic time shares a domain across handles in one process. An
    injected clock belongs to this store instance; another handle cannot verify
    it even in the same process and therefore cannot resume time-capped dispatch.
    """

    def __init__(self, path: Path, *, clock: Callable[[], float] = time.monotonic,
                 checkpoint: Callable[[str], None] | None = None) -> None:
        self.path = Path(path).resolve()
        self._clock = clock
        self._clock_domain = "monotonic" if clock is _NATIVE_CLOCK else uuid4().hex
        self._checkpoint = checkpoint or (lambda _name: None)
        self._store_id: str | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._initialize()
        except (sqlite3.Error, OSError, ValueError) as exc:
            raise BudgetAccountingError("store_unavailable") from exc

    @property
    def store_id(self) -> str:
        assert self._store_id is not None
        return self._store_id

    def _clock_origin(self) -> str:
        return f"{_process_origin()}:{self._clock_domain}"

    def _connect(self, *, initialize: bool = False) -> sqlite3.Connection:
        mode = "rwc" if initialize else "rw"
        connection = sqlite3.connect(f"{self.path.as_uri()}?mode={mode}", uri=True, isolation_level=None, timeout=1)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA synchronous=FULL")
        except BaseException:
            connection.close()
            raise
        return connection

    @staticmethod
    def _commit(connection: sqlite3.Connection) -> None:
        connection.commit()

    @contextmanager
    def _transaction(self, operation: str, *, initialize: bool = False) -> Iterator[sqlite3.Connection]:
        connection = None
        try:
            connection = self._connect(initialize=initialize)
            connection.execute("BEGIN IMMEDIATE")
            if not initialize:
                identity = connection.execute("SELECT store_id FROM budget_store WHERE singleton=1").fetchone()
                version = connection.execute("SELECT version FROM schema_versions WHERE namespace='run_budget'").fetchone()
                if identity is None or identity[0] != self.store_id:
                    raise BudgetAccountingError("store_identity_mismatch")
                if version is None or version[0] != 1:
                    raise BudgetAccountingError("unsupported_schema")
            yield connection
            self._checkpoint(f"{operation}:before_commit")
            self._commit(connection)
            self._checkpoint(f"{operation}:after_commit")
        except (sqlite3.Error, OSError) as exc:
            raise BudgetAccountingError("store_unavailable") from exc
        finally:
            if connection is not None:
                try:
                    try:
                        if connection.in_transaction:
                            connection.rollback()
                    finally:
                        connection.close()
                except sqlite3.Error as exc:
                    raise BudgetAccountingError("store_unavailable") from exc

    def _initialize(self) -> None:
        with self._transaction("migration", initialize=True) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS schema_versions (namespace TEXT PRIMARY KEY, version INTEGER NOT NULL, updated_at TEXT NOT NULL)")
            version = connection.execute("SELECT version FROM schema_versions WHERE namespace='run_budget'").fetchone()
            if version is not None and version[0] != 1:
                raise BudgetAccountingError("unsupported_schema")
            if version is None:
                statements = (
                    "CREATE TABLE budget_store (singleton INTEGER PRIMARY KEY CHECK(singleton=1), store_id TEXT NOT NULL)",
                    "CREATE TABLE budget_runs (run_id TEXT PRIMARY KEY, state_json TEXT NOT NULL, state_sha256 TEXT NOT NULL, lifecycle TEXT NOT NULL CHECK(lifecycle IN ('open','closed')), process_origin TEXT NOT NULL, monotonic_start REAL NOT NULL, owner_key TEXT, revision INTEGER NOT NULL DEFAULT 0)",
                    "CREATE TABLE budget_attempts (run_id TEXT NOT NULL REFERENCES budget_runs(run_id), request_id TEXT NOT NULL, operation_id TEXT NOT NULL, payload_json TEXT NOT NULL, PRIMARY KEY(run_id,request_id))",
                    "CREATE INDEX budget_attempt_operation ON budget_attempts(run_id,operation_id)",
                    "CREATE TABLE budget_session_runs (sequence INTEGER PRIMARY KEY AUTOINCREMENT, project_hash TEXT NOT NULL, session_id TEXT NOT NULL, run_id TEXT NOT NULL UNIQUE REFERENCES budget_runs(run_id), active INTEGER NOT NULL CHECK(active IN (0,1)))",
                    "CREATE UNIQUE INDEX budget_active_session ON budget_session_runs(project_hash,session_id) WHERE active=1",
                )
                for statement in statements:
                    connection.execute(statement)
                connection.execute("INSERT INTO budget_store VALUES (1,?)", (uuid4().hex,))
                connection.execute("INSERT INTO schema_versions VALUES ('run_budget',1,?)", (str(time.time()),))
            row = connection.execute("SELECT store_id FROM budget_store WHERE singleton=1").fetchone()
            if row is None:
                raise BudgetAccountingError("missing_store_identity")
            _identifier(row[0], "store_id")
            self._store_id = row[0]

    def _load(self, connection: sqlite3.Connection, run_id: str) -> tuple[RunBudgetLedger, sqlite3.Row, bool]:
        return self._read_ledger(connection, run_id, clock=self._clock, clock_origin=self._clock_origin())

    @staticmethod
    def _read_ledger(
        connection: sqlite3.Connection, run_id: str, *, clock: Callable[[], float], clock_origin: str,
    ) -> tuple[RunBudgetLedger, sqlite3.Row, bool]:
        row = connection.execute("SELECT * FROM budget_runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise BudgetAccountingError("missing_run")
        try:
            payload = json.loads(row["state_json"])
            attempts = connection.execute("SELECT * FROM budget_attempts WHERE run_id=? ORDER BY rowid", (run_id,)).fetchall()
            payload["attempts"] = []
            for attempt in attempts:
                raw = json.loads(attempt["payload_json"])
                if raw["request_id"] != attempt["request_id"] or raw["operation_id"] != attempt["operation_id"]:
                    raise ValueError("Accounting identity differs from indexed identity")
                payload["attempts"].append(raw)
            state = state_from_dict(payload)
            digest = hashlib.sha256(encode_state(state).encode()).hexdigest()
            if state.run_id != run_id or digest != row["state_sha256"]:
                raise ValueError("Accounting state integrity failed")
            if row["lifecycle"] not in ("open", "closed") or not math.isfinite(row["monotonic_start"]):
                raise ValueError("Invalid accounting lifecycle")
            if row["owner_key"] is not None:
                _identifier(row["owner_key"], "owner_key")
            verified = row["process_origin"] == clock_origin
            if verified:
                elapsed = clock() - row["monotonic_start"]
                if not math.isfinite(elapsed):
                    raise ValueError("Invalid accounting clock")
                state = replace(state, elapsed_seconds=max(state.elapsed_seconds, elapsed))
            ledger = RunBudgetLedger.from_state(state, clock=clock)
            return ledger, row, verified
        except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError) as exc:
            raise BudgetAccountingError("invalid_accounting_state") from exc

    @classmethod
    def inspect_session(
        cls, path: Path, project_hash: str, session_id: str, *,
        reference: SessionAccountingReference | None = None,
    ) -> SessionBudgetInspection | None:
        """Read an existing database without initialization, migrations or writes.

        Missing unreferenced storage/namespace means unavailable history. A
        missing referenced store, wrong identity, newer schema or damaged state
        raises an accounting control error instead of suggesting empty capacity.
        """
        cls._session_pair(project_hash, session_id)
        connection = None
        try:
            path = Path(path).resolve()
            if not path.exists():
                if reference is not None:
                    raise BudgetAccountingError("missing_accounting_store")
                return None
            connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, isolation_level=None, timeout=1)
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN")
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            version = connection.execute("SELECT version FROM schema_versions WHERE namespace='run_budget'").fetchone() if "schema_versions" in tables else None
            if version is None:
                if reference is not None or any(name.startswith("budget_") for name in tables):
                    raise BudgetAccountingError("missing_accounting_schema")
                return None
            if version[0] != 1:
                raise BudgetAccountingError("unsupported_schema")
            identity = connection.execute("SELECT store_id FROM budget_store WHERE singleton=1").fetchone()
            if identity is None:
                raise BudgetAccountingError("missing_store_identity")
            _identifier(identity[0], "store_id")
            rows = connection.execute("SELECT b.run_id,b.active,r.owner_key FROM budget_session_runs b LEFT JOIN budget_runs r ON b.run_id=r.run_id WHERE b.project_hash=? AND b.session_id=? ORDER BY b.sequence", (project_hash, session_id)).fetchall()
            active = [row for row in rows if row["active"]]
            if len(active) > 1:
                raise BudgetAccountingError("invalid_accounting_state")
            binding = SessionAccountingReference(
                identity[0], active[0]["run_id"] if active else None,
                tuple(row["run_id"] for row in rows), active[0]["owner_key"] if active else None,
            )
            if reference is not None and (reference.store_id != binding.store_id or not set(reference.run_ids).issubset(binding.run_ids)):
                raise BudgetAccountingError("session_accounting_identity_mismatch")
            selected = binding.active_run_id or (binding.run_ids[-1] if binding.run_ids else None)
            snapshot = None
            for row in rows:
                ledger, _metadata, verified = cls._read_ledger(
                    connection, row["run_id"], clock=_NATIVE_CLOCK,
                    clock_origin=f"{_process_origin()}:monotonic",
                )
                if row["run_id"] == selected:
                    uncertain = ledger.limits.max_seconds is not None and not verified
                    result = ledger.snapshot()
                    snapshot = replace(result, accounting_lifetime="durable",
                                       remaining_seconds=None if uncertain else result.remaining_seconds,
                                       accounting_error="time_origin_unverified" if uncertain else None)
            return SessionBudgetInspection(binding, snapshot)
        except (sqlite3.Error, OSError, ValueError) as exc:
            raise BudgetAccountingError("accounting_inspection_unavailable") from exc
        finally:
            if connection is not None:
                connection.close()

    def _write(self, connection: sqlite3.Connection, ledger: RunBudgetLedger) -> None:
        state = ledger.export_state()
        payload = state_to_dict(state)
        attempts = payload.pop("attempts")
        digest = hashlib.sha256(encode_state(state).encode()).hexdigest()
        connection.execute("UPDATE budget_runs SET state_json=?, state_sha256=?, revision=revision+1 WHERE run_id=?", (_json(payload), digest, state.run_id))
        for attempt in attempts:
            connection.execute(
                "INSERT INTO budget_attempts(run_id,request_id,operation_id,payload_json) VALUES (?,?,?,?) ON CONFLICT(run_id,request_id) DO UPDATE SET payload_json=excluded.payload_json",
                (state.run_id, attempt["request_id"], attempt["operation_id"], _json(attempt)),
            )

    @staticmethod
    def _session_pair(project_hash: str | None, session_id: str | None) -> None:
        if (project_hash is None) != (session_id is None):
            raise ValueError("Project and session identities must be supplied together")
        if project_hash is not None:
            _identifier(project_hash, "project_hash")
            _identifier(session_id, "session_id")  # type: ignore[arg-type]

    def create_run(self, *, limits: BudgetLimits | None = None, run_id: str | None = None,
                   project_hash: str | None = None, session_id: str | None = None,
                   owner_key: str | None = None) -> PersistentRunBudgetLedger:
        """Create an explicit new run; never replace an active session's budget."""
        self._session_pair(project_hash, session_id)
        if owner_key is not None:
            _identifier(owner_key, "owner_key")
        ledger = RunBudgetLedger(run_id=run_id, limits=limits, clock=self._clock)
        with self._transaction("create_run") as connection:
            if connection.execute("SELECT 1 FROM budget_runs WHERE run_id=?", (ledger.run_id,)).fetchone():
                raise BudgetAccountingError("run_already_exists")
            if project_hash is not None and connection.execute("SELECT 1 FROM budget_session_runs WHERE project_hash=? AND session_id=? AND active=1", (project_hash, session_id)).fetchone():
                raise BudgetAccountingError("active_run_exists")
            connection.execute("INSERT INTO budget_runs(run_id,state_json,state_sha256,lifecycle,process_origin,monotonic_start,owner_key) VALUES (?,'','', 'open',?,?,?)", (ledger.run_id, self._clock_origin(), ledger.monotonic_origin, owner_key))
            self._write(connection, ledger)
            if project_hash is not None:
                connection.execute("INSERT INTO budget_session_runs(project_hash,session_id,run_id,active) VALUES (?,?,?,1)", (project_hash, session_id, ledger.run_id))
        return PersistentRunBudgetLedger(self, ledger.run_id, ledger.limits, owner_key)

    def resume_run(self, run_id: str, *, store_id: str, project_hash: str | None = None,
                   session_id: str | None = None) -> PersistentRunBudgetLedger:
        """Open existing authority; missing or cross-session references fail closed."""
        self._session_pair(project_hash, session_id)
        if store_id != self.store_id:
            raise BudgetAccountingError("store_identity_mismatch")
        with self._transaction("resume_run") as connection:
            ledger, row, _verified = self._load(connection, run_id)
            binding = connection.execute("SELECT project_hash,session_id FROM budget_session_runs WHERE run_id=?", (run_id,)).fetchone()
            actual = tuple(binding) if binding is not None else (None, None)
            if actual != (project_hash, session_id):
                raise BudgetAccountingError("session_identity_mismatch")
        return PersistentRunBudgetLedger(self, run_id, ledger.limits, row["owner_key"])

    def session_binding(self, project_hash: str, session_id: str) -> SessionAccountingReference:
        """Find active/history identities even when a transcript backup omitted them."""
        self._session_pair(project_hash, session_id)
        with self._transaction("session_binding") as connection:
            rows = connection.execute("SELECT b.run_id,b.active,r.owner_key FROM budget_session_runs b LEFT JOIN budget_runs r ON b.run_id=r.run_id WHERE b.project_hash=? AND b.session_id=? ORDER BY b.sequence", (project_hash, session_id)).fetchall()
            for row in rows:
                self._load(connection, row["run_id"])
            active = next((row["run_id"] for row in rows if row["active"]), None)
            owner_key = next((row["owner_key"] for row in rows if row["active"]), None)
            return SessionAccountingReference(self.store_id, active, tuple(row["run_id"] for row in rows), owner_key)

    def finish_run(self, run_id: str) -> None:
        """Close admission explicitly; unknown dispatched holds and history remain."""
        with self._transaction("finish_run") as connection:
            ledger, _row, _verified = self._load(connection, run_id)
            for attempt in ledger.export_state().attempts:
                if not attempt.dispatched and attempt.state == "reserved":
                    ledger.cancel(attempt.request_id)
            self._write(connection, ledger)
            connection.execute("UPDATE budget_runs SET lifecycle='closed' WHERE run_id=?", (run_id,))
            connection.execute("UPDATE budget_session_runs SET active=0 WHERE run_id=?", (run_id,))

    def _apply(self, run_id: str, operation: str, change: Callable[[RunBudgetLedger], _T], *, admission: bool = False) -> _T:
        denial = None
        result: Any = None
        with self._transaction(operation) as connection:
            ledger, row, verified = self._load(connection, run_id)
            if admission and row["lifecycle"] != "open":
                raise BudgetAccountingError("run_closed")
            if admission and ledger.limits.max_seconds is not None and not verified:
                raise BudgetAccountingError("time_origin_unverified")
            try:
                result = change(ledger)
            except BudgetExceeded as exc:
                # A denied start cancels its undispatched reservation; commit that
                # transition and the diagnostic before propagating the denial.
                denial = exc
            self._write(connection, ledger)
            if isinstance(result, BudgetSnapshot):
                uncertain_time = ledger.limits.max_seconds is not None and not verified
                result = replace(result, accounting_lifetime="durable",
                                 remaining_seconds=None if uncertain_time else result.remaining_seconds,
                                 accounting_error="time_origin_unverified" if uncertain_time else None)
        if denial is not None:
            raise denial
        return cast(_T, result)


class PersistentRunBudgetLedger:
    """An authority handle, never an in-memory cache of available capacity."""

    def __init__(self, store: RunBudgetStore, run_id: str, limits: BudgetLimits, owner_key: str | None = None) -> None:
        self._store, self._run_id, self._limits = store, run_id, limits
        self._owner_key = owner_key

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def limits(self) -> BudgetLimits:
        return self._limits

    @property
    def owner_key(self) -> str | None:
        return self._owner_key

    def reserve(self, estimate: RequestEstimate, *, request_id: str | None = None,
                operation_id: str | None = None, agent_id: str | None = None,
                provider: str | None = None, model: str | None = None) -> RequestRecord:
        # Normalize the same decimal spelling used by the existing exact cost
        # arithmetic, so a repeated float-configured estimate survives storage.
        if estimate.pricing is not None:
            pricing = estimate.pricing
            def rate(name: str) -> Decimal | None:
                value = getattr(pricing, name)
                return Decimal(str(value)) if value is not None else None
            estimate = replace(estimate, pricing=replace(
                pricing, input_per_1k=rate("input_per_1k"), output_per_1k=rate("output_per_1k"),
                cache_read_per_1k=rate("cache_read_per_1k"), cache_write_per_1k=rate("cache_write_per_1k"),
            ))
        return self._store._apply(self.run_id, "reserve", lambda ledger: ledger.reserve(
            estimate, request_id=request_id, operation_id=operation_id, agent_id=agent_id,
            provider=provider, model=model), admission=True)

    def start(self, request_id: str) -> bool:
        return self._store._apply(self.run_id, "start", lambda ledger: ledger.start(request_id), admission=True)

    def reconcile(self, request_id: str, usage: UsageReport | None = None, *, final: bool = False,
                  reported_cost: ReportedCost | None = None) -> RequestRecord:
        return self._store._apply(self.run_id, "reconcile", lambda ledger: ledger.reconcile(request_id, usage, final=final, reported_cost=reported_cost))

    def cancel(self, request_id: str) -> RequestRecord:
        return self._store._apply(self.run_id, "cancel", lambda ledger: ledger.cancel(request_id))

    def snapshot(self) -> BudgetSnapshot:
        return self._store._apply(self.run_id, "snapshot", lambda ledger: ledger.snapshot())
