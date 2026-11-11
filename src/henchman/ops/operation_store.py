"""Transactional operation recovery in an explicitly selected operations database.

The operation_recovery schema namespace coexists with OpsStore and run budgets.
Dispatch permits are returned only after a committed start. Missing, incompatible
or corrupt authority is an error, never permission to reconstruct an empty queue.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TypeVar
from uuid import uuid4

from henchman.core.operation_bindings import OperationSessionReference
from henchman.core.operation_recovery import (
    DispatchPermit,
    OperationContext,
    OperationJournal,
    OperationRecord,
    OperationRecoveryError,
    OperationResult,
    RecoveryReport,
    RetryAuthority,
    RetryAuthorization,
    _identity,
)
from henchman.utils.evidence_redaction import EvidenceRedactor

_T = TypeVar("_T")


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class OperationStore:
    """SQLite authority with independent transactions and runtime-only retries.

    ``expected_store_id`` opens existing authority without initialization. Callers
    must use it whenever a saved session already carries a store reference.
    ``checkpoint`` permits deterministic process termination at commit boundaries.
    """

    def __init__(self, path: Path, *, expected_store_id: str | None = None,
                 redactor: EvidenceRedactor | None = None,
                 checkpoint: Callable[[str], None] | None = None) -> None:
        self.path = Path(path).resolve()
        self._redactor = redactor if redactor is not None else EvidenceRedactor()
        self._checkpoint = checkpoint or (lambda _stage: None)
        self._runtime_id = uuid4().hex
        self._authority = RetryAuthority()
        self._store_id: str | None = expected_store_id
        try:
            if expected_store_id is not None:
                _identity(expected_store_id)
                with self._transaction("open"):
                    pass
            else:
                self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                try:
                    descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                except FileExistsError:
                    pass
                else:
                    os.close(descriptor)
                self._initialize()
        except (sqlite3.Error, OSError, ValueError) as exc:
            raise OperationRecoveryError("store_unavailable") from exc

    @property
    def store_id(self) -> str:
        assert self._store_id is not None
        return self._store_id

    @property
    def owner_id(self) -> str:
        # Reopening a runtime and inheriting a handle across fork both invalidate
        # prior ownership. This does not imply the earlier process has stopped.
        return self._runtime_id

    @classmethod
    def existing_reference(cls, path: Path, project_hash: str, session_id: str) -> OperationSessionReference | None:
        """Discover existing authority without creating a file or migrating a schema."""
        path = Path(path).resolve()
        if not path.exists():
            return None
        connection = None
        try:
            connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "schema_versions" not in tables:
                if tables:
                    raise OperationRecoveryError("unsupported_schema")
                return None
            version = connection.execute("SELECT version FROM schema_versions WHERE namespace='operation_recovery'").fetchone()
            if version is None:
                if "operation_store" in tables or "operation_sessions" in tables:
                    raise OperationRecoveryError("unsupported_schema")
                return None
            if version[0] != 1:
                raise OperationRecoveryError("unsupported_schema")
            identity = connection.execute("SELECT store_id FROM operation_store WHERE singleton=1").fetchone()
            if identity is None:
                raise OperationRecoveryError("missing_store_identity")
            row = connection.execute("SELECT 1 FROM operation_sessions WHERE project_hash=? AND session_id=?",
                                     (project_hash, session_id)).fetchone()
            return OperationSessionReference(identity[0], project_hash, session_id) if row is not None else None
        except (sqlite3.Error, OSError, ValueError) as exc:
            raise OperationRecoveryError("store_unavailable") from exc
        finally:
            if connection is not None:
                connection.close()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(f"{self.path.as_uri()}?mode=rw", uri=True,
                                     isolation_level=None, timeout=5)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA foreign_keys=ON")
        except BaseException:
            connection.close()
            raise
        return connection

    @staticmethod
    def _commit(connection: sqlite3.Connection) -> None:
        connection.commit()

    def _validate(self, connection: sqlite3.Connection) -> None:
        version = connection.execute("SELECT version FROM schema_versions WHERE namespace='operation_recovery'").fetchone()
        if version is None or version[0] != 1:
            raise OperationRecoveryError("unsupported_schema")
        identity = connection.execute("SELECT store_id FROM operation_store WHERE singleton=1").fetchone()
        if identity is None or identity[0] != self.store_id:
            raise OperationRecoveryError("store_identity_mismatch")

    @contextmanager
    def _transaction(self, operation: str, *, initialize: bool = False) -> Iterator[sqlite3.Connection]:
        connection = None
        try:
            connection = self._connect()
            connection.execute("BEGIN IMMEDIATE")
            if not initialize:
                self._validate(connection)
            yield connection
            self._checkpoint(f"{operation}:before_commit")
            self._commit(connection)
            self._checkpoint(f"{operation}:after_commit")
        except (sqlite3.Error, OSError) as exc:
            raise OperationRecoveryError("store_unavailable") from exc
        finally:
            if connection is not None:
                try:
                    try:
                        if connection.in_transaction:
                            connection.rollback()
                    finally:
                        connection.close()
                except sqlite3.Error as exc:
                    raise OperationRecoveryError("store_unavailable") from exc

    def _initialize(self) -> None:
        with self._transaction("migration", initialize=True) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS schema_versions (namespace TEXT PRIMARY KEY, version INTEGER NOT NULL, updated_at TEXT NOT NULL)")
            version = connection.execute("SELECT version FROM schema_versions WHERE namespace='operation_recovery'").fetchone()
            if version is not None and version[0] != 1:
                raise OperationRecoveryError("unsupported_schema")
            if version is None:
                connection.execute("CREATE TABLE operation_store (singleton INTEGER PRIMARY KEY CHECK(singleton=1), store_id TEXT NOT NULL)")
                connection.execute("CREATE TABLE operation_sessions (project_hash TEXT NOT NULL, session_id TEXT NOT NULL, state_json TEXT NOT NULL, state_sha256 TEXT NOT NULL, PRIMARY KEY(project_hash,session_id))")
                connection.execute("INSERT INTO operation_store VALUES (1,?)", (uuid4().hex,))
                connection.execute("INSERT INTO schema_versions VALUES ('operation_recovery',1,?)", (str(time.time()),))
            row = connection.execute("SELECT store_id FROM operation_store WHERE singleton=1").fetchone()
            if row is None:
                raise OperationRecoveryError("missing_store_identity")
            self._store_id = _identity(row[0])

    def _load(self, connection: sqlite3.Connection, project_hash: str, session_id: str) -> OperationJournal:
        row = connection.execute("SELECT state_json,state_sha256 FROM operation_sessions WHERE project_hash=? AND session_id=?",
                                 (project_hash, session_id)).fetchone()
        if row is None:
            raise OperationRecoveryError("missing_session")
        try:
            if hashlib.sha256(row[0].encode()).hexdigest() != row[1]:
                raise ValueError("Operation state integrity failed")
            journal = OperationJournal.from_state(json.loads(row[0]), owner_id=self.owner_id,
                                                  redactor=self._redactor, retry_authority=self._authority)
            if (journal.project_hash, journal.session_id) != (project_hash, session_id):
                raise ValueError("Operation state scope mismatch")
            return journal
        except (TypeError, ValueError, AttributeError) as exc:
            raise OperationRecoveryError("invalid_state") from exc

    @staticmethod
    def _save(connection: sqlite3.Connection, journal: OperationJournal) -> None:
        payload = _json(journal.export_state())
        connection.execute("UPDATE operation_sessions SET state_json=?,state_sha256=? WHERE project_hash=? AND session_id=?",
                           (payload, hashlib.sha256(payload.encode()).hexdigest(), journal.project_hash, journal.session_id))

    def open_session(self, project_hash: str, session_id: str, *, create: bool = False) -> PersistentOperationJournal:
        """Explicitly bind a session, returning existing history without resetting it."""
        _identity(project_hash)
        _identity(session_id)
        with self._transaction("session") as connection:
            existing = connection.execute("SELECT 1 FROM operation_sessions WHERE project_hash=? AND session_id=?",
                                          (project_hash, session_id)).fetchone()
            if existing is None and create:
                journal = OperationJournal(project_hash, session_id, owner_id=self.owner_id,
                                           redactor=self._redactor, retry_authority=self._authority)
                payload = _json(journal.export_state())
                connection.execute("INSERT INTO operation_sessions VALUES (?,?,?,?)",
                                   (project_hash, session_id, payload, hashlib.sha256(payload.encode()).hexdigest()))
            self._load(connection, project_hash, session_id)
        return PersistentOperationJournal(self, OperationSessionReference(self.store_id, project_hash, session_id))

    def resume_session(self, reference: OperationSessionReference) -> PersistentOperationJournal:
        if reference.store_id != self.store_id:
            raise OperationRecoveryError("store_identity_mismatch")
        return self.open_session(reference.project_hash, reference.session_id)


class PersistentOperationJournal:
    """A stable session reference; every operation reloads authoritative state."""

    def __init__(self, store: OperationStore, reference: OperationSessionReference) -> None:
        self._store = store
        self.reference = reference

    def _apply(self, operation: str, action: Callable[[OperationJournal], _T], *, write: bool = True) -> _T:
        with self._store._transaction(operation) as connection:
            journal = self._store._load(connection, self.reference.project_hash, self.reference.session_id)
            result = action(journal)
            if write:
                self._store._save(connection, journal)
        return result

    def queue(self, context: OperationContext, *, tool_name: str, effect: str,
              input_digest: str, description: str = "", operation_id: str | None = None) -> OperationRecord:
        return self._apply("queue", lambda journal: journal.queue(
            context, tool_name=tool_name, effect=effect, input_digest=input_digest,
            description=description, operation_id=operation_id))

    def start(self, operation_id: str) -> DispatchPermit | None:
        return self._apply("start", lambda journal: journal.start(operation_id))

    def finish(self, permit: DispatchPermit, result: OperationResult) -> OperationRecord:
        return self._apply("finish", lambda journal: journal.finish(permit, result))

    def cancel(self, operation_id: str) -> OperationRecord:
        return self._apply("cancel", lambda journal: journal.cancel(operation_id))

    def report(self) -> RecoveryReport:
        return self._apply("report", lambda journal: journal.report(), write=False)

    def recover(self) -> RecoveryReport:
        return self._apply("recover", lambda journal: journal.recover())

    def resolve(self, operation_id: str, *, expected_revision: int, decision: str,
                note: str, result: OperationResult | None = None) -> OperationRecord:
        return self._apply("resolve", lambda journal: journal.resolve(
            operation_id, expected_revision=expected_revision, decision=decision, note=note, result=result))

    def authorize_retry(self, operation_id: str, *, expected_revision: int) -> RetryAuthorization:
        return self._apply("authorize_retry", lambda journal: journal.authorize_retry(
            operation_id, expected_revision=expected_revision), write=False)

    def retry(self, authorization: RetryAuthorization, *, operation_id: str | None = None,
              note: str) -> OperationRecord:
        return self._apply("retry", lambda journal: journal.retry(authorization, operation_id=operation_id, note=note))
