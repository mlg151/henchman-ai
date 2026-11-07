"""Transactional session workflow authority beside existing operations namespaces."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TypeVar
from uuid import uuid4

from henchman.core.workflow_state import (
    InputKind,
    InputOutcome,
    InputPermit,
    QueuedInput,
    WorkflowError,
    WorkflowGoal,
    WorkflowJournal,
    WorkflowReference,
    WorkflowState,
    decode_state,
    encode_state,
)
from henchman.utils.evidence_redaction import EvidenceRedactor

_T = TypeVar("_T")


class WorkflowStore:
    """Commit intent/start before returning permission; inspection never creates."""

    def __init__(self, path: Path, *, expected_store_id: str | None = None,
                 redactor: EvidenceRedactor | None = None,
                 checkpoint: Callable[[str], None] | None = None) -> None:
        self.path = Path(path).resolve()
        self._store_id = expected_store_id
        self._runtime_id = uuid4().hex
        self.redactor = redactor if redactor is not None else EvidenceRedactor()
        self._checkpoint = checkpoint or (lambda _stage: None)
        if expected_store_id is None:
            try:
                self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                try:
                    descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                except FileExistsError:
                    pass
                else:
                    os.close(descriptor)
                with self._transaction("migration", initialize=True) as connection:
                    connection.execute("CREATE TABLE IF NOT EXISTS schema_versions (namespace TEXT PRIMARY KEY, version INTEGER NOT NULL, updated_at TEXT NOT NULL)")
                    version = connection.execute("SELECT version FROM schema_versions WHERE namespace='session_workflow'").fetchone()
                    if version is None:
                        connection.execute("CREATE TABLE workflow_store (singleton INTEGER PRIMARY KEY CHECK(singleton=1), store_id TEXT NOT NULL)")
                        connection.execute("CREATE TABLE workflow_sessions (project_hash TEXT NOT NULL, session_id TEXT NOT NULL, state_json TEXT NOT NULL, state_sha256 TEXT NOT NULL, PRIMARY KEY(project_hash,session_id))")
                        connection.execute("INSERT INTO workflow_store VALUES (1,?)", (uuid4().hex,))
                        connection.execute("INSERT INTO schema_versions VALUES ('session_workflow',1,datetime('now'))")
                    self._store_id = self._validate(connection)
            except (OSError, sqlite3.Error) as exc:
                raise WorkflowError("store_unavailable") from exc
        else:
            with self._transaction("open"):
                pass

    @property
    def store_id(self) -> str:
        assert self._store_id is not None
        return self._store_id

    @property
    def owner_id(self) -> str:
        return f"{os.getpid()}:{self._runtime_id}"

    @staticmethod
    def _identity(connection: sqlite3.Connection) -> str | None:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "schema_versions" not in tables:
            if tables:
                raise WorkflowError("unsupported_schema")
            return None
        version = connection.execute("SELECT version FROM schema_versions WHERE namespace='session_workflow'").fetchone()
        if version is None:
            if {"workflow_store", "workflow_sessions"} & tables:
                raise WorkflowError("unsupported_schema")
            return None
        if version[0] != 1:
            raise WorkflowError("unsupported_schema")
        row = connection.execute("SELECT store_id FROM workflow_store WHERE singleton=1").fetchone()
        if row is None:
            raise WorkflowError("missing_store_identity")
        try:
            return WorkflowReference(store_id=row[0], project_hash="validation", session_id="validation").store_id
        except ValueError as exc:
            raise WorkflowError("invalid_store_identity") from exc

    def _validate(self, connection: sqlite3.Connection) -> str:
        identity = self._identity(connection)
        if identity is None:
            raise WorkflowError("missing_workflow_schema")
        if self._store_id is not None and identity != self._store_id:
            raise WorkflowError("store_identity_mismatch")
        return identity

    @staticmethod
    def _load(connection: sqlite3.Connection, project_hash: str, session_id: str) -> WorkflowState | None:
        row = connection.execute("SELECT state_json,state_sha256 FROM workflow_sessions WHERE project_hash=? AND session_id=?",
                                 (project_hash, session_id)).fetchone()
        if row is None:
            return None
        if not isinstance(row[0], str) or hashlib.sha256(row[0].encode()).hexdigest() != row[1]:
            raise WorkflowError("invalid_state")
        state = decode_state(row[0])
        if (state.project_hash, state.session_id) != (project_hash, session_id):
            raise WorkflowError("session_identity_mismatch")
        return state

    @classmethod
    def _inspect(cls, path: Path, project_hash: str, session_id: str, *,
                 reference: WorkflowReference | None = None) -> tuple[WorkflowReference, WorkflowState] | None:
        """Read current authority; an old/missing JSON reference cannot hide it."""
        path = Path(path).resolve()
        if not path.exists():
            if reference is not None:
                raise WorkflowError("missing_workflow_store")
            return None
        connection = None
        try:
            connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
            connection.execute("BEGIN")
            identity = cls._identity(connection)
            if reference is not None and (reference.store_id, reference.project_hash, reference.session_id) != (identity, project_hash, session_id):
                raise WorkflowError("store_identity_mismatch")
            state = cls._load(connection, project_hash, session_id) if identity is not None else None
            if reference is not None and state is None:
                raise WorkflowError("missing_workflow_session")
            if state is None or identity is None:
                return None
            return WorkflowReference(store_id=identity, project_hash=project_hash, session_id=session_id), state
        except (sqlite3.Error, OSError) as exc:
            raise WorkflowError("store_unavailable") from exc
        finally:
            if connection is not None:
                connection.close()

    @classmethod
    def inspect(cls, path: Path, project_hash: str, session_id: str, *,
                reference: WorkflowReference | None = None) -> WorkflowState | None:
        inspected = cls._inspect(path, project_hash, session_id, reference=reference)
        return inspected[1] if inspected is not None else None

    @classmethod
    def existing_reference(cls, path: Path, project_hash: str, session_id: str, *,
                           reference: WorkflowReference | None = None) -> WorkflowReference | None:
        inspected = cls._inspect(path, project_hash, session_id, reference=reference)
        return inspected[0] if inspected is not None else None

    @staticmethod
    def _commit(connection: sqlite3.Connection) -> None:
        connection.commit()

    @contextmanager
    def _transaction(self, operation: str, *, initialize: bool = False,
                     guard: Callable[[], None] | None = None) -> Iterator[sqlite3.Connection]:
        connection = None
        try:
            connection = sqlite3.connect(f"{self.path.as_uri()}?mode=rw", uri=True,
                                         timeout=0.05 if guard is not None else 30)
            if guard is None:
                connection.execute("BEGIN IMMEDIATE")
            else:
                # Preserve the existing contention bound, but let an owned UI
                # operation revoke admission while another writer holds SQLite.
                deadline = time.monotonic() + 30
                while True:
                    guard()
                    try:
                        connection.execute("BEGIN IMMEDIATE")
                        break
                    except sqlite3.OperationalError as error:
                        if (getattr(error, "sqlite_errorcode", None) != sqlite3.SQLITE_BUSY
                            or time.monotonic() >= deadline):
                            raise
            if not initialize:
                self._validate(connection)
            if guard is not None:
                guard()
            yield connection
            self._checkpoint(f"{operation}:before_commit")
            if guard is not None:
                guard()
            self._commit(connection)
            self._checkpoint(f"{operation}:after_commit")
        except (sqlite3.Error, OSError) as exc:
            raise WorkflowError("store_unavailable") from exc
        finally:
            if connection is not None:
                try:
                    if connection.in_transaction:
                        connection.rollback()
                finally:
                    connection.close()

    def open_session(self, project_hash: str, session_id: str, *, create: bool = False) -> StoredWorkflow:
        reference = WorkflowReference(store_id=self.store_id, project_hash=project_hash, session_id=session_id)
        with self._transaction("session") as connection:
            state = self._load(connection, project_hash, session_id)
            if state is None:
                if not create:
                    raise WorkflowError("missing_workflow_session")
                payload = encode_state(WorkflowState(project_hash=project_hash, session_id=session_id))
                connection.execute("INSERT INTO workflow_sessions VALUES (?,?,?,?)",
                                   (project_hash, session_id, payload, hashlib.sha256(payload.encode()).hexdigest()))
        return StoredWorkflow(self, reference)

    def _change(self, reference: WorkflowReference, operation: str, change: Callable[[WorkflowJournal], _T],
                *, guard: Callable[[], None] | None = None) -> _T:
        with self._transaction(operation, guard=guard) as connection:
            if reference.store_id != self.store_id:
                raise WorkflowError("store_identity_mismatch")
            state = self._load(connection, reference.project_hash, reference.session_id)
            if state is None:
                raise WorkflowError("missing_workflow_session")
            journal = WorkflowJournal(reference.project_hash, reference.session_id, owner_id=self.owner_id,
                                      state=state, redactor=self.redactor)
            result = change(journal)
            payload = encode_state(journal.projected_state())
            connection.execute("UPDATE workflow_sessions SET state_json=?,state_sha256=? WHERE project_hash=? AND session_id=?",
                               (payload, hashlib.sha256(payload.encode()).hexdigest(), reference.project_hash, reference.session_id))
        return result


class StoredWorkflow:
    """A scoped facade; all decisions reload the latest committed authority."""

    def __init__(self, store: WorkflowStore, reference: WorkflowReference) -> None:
        self.store = store
        self.reference = reference

    @property
    def owner_id(self) -> str:
        return self.store.owner_id

    def snapshot(self) -> WorkflowState:
        state = WorkflowStore.inspect(self.store.path, self.reference.project_hash, self.reference.session_id,
                                      reference=self.reference)
        assert state is not None
        return state

    def report(self) -> WorkflowState:
        return WorkflowJournal(self.reference.project_hash, self.reference.session_id,
                               owner_id=self.owner_id, state=self.snapshot(), redactor=self.store.redactor).report()

    def _call(self, method: str, change: Callable[[WorkflowJournal], _T],
              *, guard: Callable[[], None] | None = None) -> _T:
        return self.store._change(self.reference, method, change, guard=guard)

    def enqueue(self, text: str, *, kind: InputKind = "message", role: str | None = None,
                input_id: str | None = None, goal_id: str | None = None, goal_revision: int | None = None) -> QueuedInput:
        return self._call("enqueue", lambda journal: journal.enqueue(text, kind=kind, role=role, input_id=input_id,
                                                                     goal_id=goal_id, goal_revision=goal_revision))

    def edit(self, input_id: str, revision: int, text: str) -> QueuedInput:
        return self._call("edit", lambda journal: journal.edit(input_id, revision, text))

    def move(self, input_id: str, revision: int, position: int) -> QueuedInput:
        return self._call("move", lambda journal: journal.move(input_id, revision, position))

    def drop(self, input_id: str, revision: int) -> QueuedInput:
        return self._call("drop", lambda journal: journal.drop(input_id, revision))

    def transfer_queued(self, input_id: str, revision: int, *, live_text: str | None = None) -> QueuedInput:
        return self._call("transfer_queued", lambda journal: journal.transfer_queued(input_id, revision, live_text=live_text))

    def claim(self, input_id: str, revision: int, *, live_text: str | None = None) -> InputPermit:
        return self._call("claim", lambda journal: journal.claim(input_id, revision, live_text=live_text))

    def finish(self, permit: InputPermit, *, outcome: InputOutcome) -> QueuedInput:
        return self._call("finish", lambda journal: journal.finish(permit, outcome=outcome))

    def correlate(self, permit: InputPermit, *, budget_run_id: str | None = None,
                  operation_run_id: str | None = None, operation_id: str | None = None) -> QueuedInput:
        return self._call("correlate", lambda journal: journal.correlate(
            permit, budget_run_id=budget_run_id, operation_run_id=operation_run_id, operation_id=operation_id))

    def cancel(self, input_id: str, revision: int) -> QueuedInput:
        return self._call("cancel", lambda journal: journal.cancel(input_id, revision))

    def abandon(self, input_id: str, revision: int, note: str) -> QueuedInput:
        return self._call("abandon", lambda journal: journal.abandon(input_id, revision, note))

    def set_goal(self, goal: WorkflowGoal | None, *, expected_revision: int) -> WorkflowGoal | None:
        return self._call("set_goal", lambda journal: journal.set_goal(goal, expected_revision=expected_revision))
