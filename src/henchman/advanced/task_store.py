"""Versioned task evidence with locked per-record compare-and-swap updates.

Task records are evidence, never executable input or PID ownership. Readers do
not rewrite lifecycle state. One stable lock protects validation and replacement;
unrelated task updates preserve each other and stale same-task writes fail.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO
from uuid import uuid4

from henchman.advanced.task_output import (
    _evidence_directory,
    atomic_evidence,
    open_evidence,
    write_evidence,
)
from henchman.utils.file_lock import FileLock

MAX_INDEX_BYTES = 8 * 1024 * 1024
TASK_STATES = {"queued", "started", "running", "completed", "failed", "stopped", "cancelled", "outcome_unknown"}
FINAL_STATES = {"completed", "failed", "stopped", "cancelled"}
_BASE_FIELDS = {"task_id", "title", "argv", "cwd", "status", "created_at", "started_at", "finished_at",
                "output_path", "pid", "return_code", "metadata"}
_FIELDS = _BASE_FIELDS | {"revision", "owner_id", "operation_context"}
_CONTEXT = {"operation_id", "project_hash", "session_id", "run_id", "turn_id", "agent_id", "tool_call_id"}


class TaskStoreError(OSError, ValueError):
    """Task authority is missing, damaged, or changed concurrently."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def _identity(value: Any) -> bool:
    return isinstance(value, str) and 0 < len(value) <= 256 and all(ord(char) >= 32 for char in value)


def _record(raw: Any, *, legacy: bool = False) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw.keys() >= _BASE_FIELDS or raw.keys() - _FIELDS:
        raise TaskStoreError("Task index has invalid record fields")
    if not legacy and raw.keys() != _FIELDS:
        raise TaskStoreError("Task index is missing versioned record fields")
    value = deepcopy(raw)
    identity = value["task_id"]
    if not isinstance(identity, str) or re.fullmatch(r"task-[0-9a-f]{12}", identity) is None:
        raise TaskStoreError("Task index has invalid task identity")
    value.setdefault("revision", 0)
    value.setdefault("owner_id", None)
    value.setdefault("operation_context", None)
    valid = type(value["revision"]) is int and value["revision"] >= 0
    valid = valid and (value["owner_id"] is None or _identity(value["owner_id"]))
    valid = valid and isinstance(value["status"], str) and value["status"] in TASK_STATES
    valid = valid and all(isinstance(value[key], str) and len(value[key]) <= 65536
                          for key in ("title", "cwd", "output_path"))
    valid = valid and isinstance(value["argv"], list) and len(value["argv"]) <= 4096 and all(
        isinstance(arg, str) and len(arg) <= 65536 for arg in value["argv"])
    valid = valid and isinstance(value["metadata"], dict) and len(value["metadata"]) <= 4096 and all(
        isinstance(key, str) and len(key) <= 65536 and isinstance(item, str) and len(item) <= 65536
        for key, item in value["metadata"].items())
    valid = valid and all(value[key] is None or type(value[key]) is int for key in ("pid", "return_code"))
    try:
        for key in ("created_at", "started_at", "finished_at"):
            if key == "created_at" or value[key] is not None:
                datetime.fromisoformat(value[key])
    except (ValueError, TypeError):
        valid = False
    context = value["operation_context"]
    valid = valid and (context is None or isinstance(context, dict) and context.keys() == _CONTEXT
                       and all(_identity(item) for item in context.values()))
    if not valid:
        raise TaskStoreError("Task index has invalid or oversized record values")
    if not legacy:
        state = value["status"]
        if state == "queued" and any(value[key] is not None for key in ("started_at", "finished_at", "pid", "return_code")):
            raise TaskStoreError("Queued task intent cannot contain process observations")
        if state in {"started", "running"} and (value["started_at"] is None or value["finished_at"] is not None or value["return_code"] is not None):
            raise TaskStoreError("Active task intent has inconsistent process observations")
        if state == "started" and value["pid"] is not None:
            raise TaskStoreError("Started task intent cannot claim a returned process")
        if state in FINAL_STATES and value["finished_at"] is None:
            raise TaskStoreError("Terminal task evidence requires an observation timestamp")
        if state == "cancelled" and (value["started_at"] is not None or value["pid"] is not None or value["return_code"] is not None):
            raise TaskStoreError("Cancelled queued intent cannot claim dispatch")
    # Legacy absolute output paths are evidence only, never replayable paths.
    if not legacy and value["output_path"] != f"{identity}.log":
        raise TaskStoreError("Task index has invalid output identity")
    value["output_path"] = f"{identity}.log"
    return value


class TaskStore:
    """An explicit canonical index path; construction performs no I/O."""

    def __init__(self, path: Path, *, checkpoint: Callable[[str], None] | None = None) -> None:
        self.path = path
        self._store_id: str | None = None
        self._seen = False
        self._lock_file: BinaryIO | None = None
        self._checkpoint = checkpoint or (lambda _stage: None)

    def _read(self) -> tuple[int, dict[str, dict[str, Any]]]:
        try:
            with open_evidence(self.path) as source:
                encoded = source.read(MAX_INDEX_BYTES + 1)
        except FileNotFoundError:
            if self._seen or self._store_id is not None:
                raise TaskStoreError("Task index is missing; preserve existing authority for repair") from None
            return 0, {}
        if len(encoded) > MAX_INDEX_BYTES:
            raise TaskStoreError("Task index exceeds its 8 MiB limit")
        try:
            raw = json.loads(encoded)
        except (ValueError, UnicodeError, RecursionError):
            raise TaskStoreError("Task index is corrupt; preserve it for explicit repair") from None
        self._seen = True
        legacy = isinstance(raw, list)
        if legacy:
            if self._store_id is not None:
                raise TaskStoreError("Task index identity changed to legacy data")
            revision, records = 0, raw
        else:
            if not isinstance(raw, dict) or raw.keys() != {"version", "store_id", "revision", "records", "sha256"}:
                raise TaskStoreError("Task index has invalid envelope fields")
            if type(raw["version"]) is not int or raw["version"] != 1:
                raise TaskStoreError("Task index version is unsupported")
            digest = raw.pop("sha256")
            if digest != hashlib.sha256(_canonical(raw)).hexdigest():
                raise TaskStoreError("Task index integrity check failed")
            if not _identity(raw["store_id"]) or type(raw["revision"]) is not int or raw["revision"] < 0:
                raise TaskStoreError("Task index has invalid revision or identity")
            if self._store_id is not None and self._store_id != raw["store_id"]:
                raise TaskStoreError("Task index identity changed")
            self._store_id = raw["store_id"]
            revision, records = raw["revision"], raw["records"]
        if not isinstance(records, list) or len(records) > 10000:
            raise TaskStoreError("Task index must contain a bounded record list")
        result = {}
        for raw_record in records:
            item = _record(raw_record, legacy=legacy)
            if item["task_id"] in result:
                raise TaskStoreError("Task index has duplicate task identities")
            result[item["task_id"]] = item
        return revision, result

    @contextmanager
    def _lock(self) -> Iterator[None]:
        # Validate storage before FileLock opens its stable cooperative lock.
        with _evidence_directory(self.path.parent):
            pass
        lock_path = self.path.with_suffix(".lock")
        try:
            with open_evidence(lock_path):
                pass
        except FileNotFoundError:
            pass
        with FileLock(lock_path) as lock:
            handle = lock.lock_file
            assert handle is not None
            observed = lock_path.lstat()
            if not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1 or not os.path.samestat(observed, os.fstat(handle.fileno())):
                raise TaskStoreError("Task index lock is not a stable regular file")
            handle.seek(0)
            marker = handle.read(257)
            if marker:
                if re.fullmatch(rb"[0-9a-f]{32}", marker) is None:
                    raise TaskStoreError("Task index lock identity is corrupt")
                identity = marker.decode("ascii")
                if self._store_id is not None and self._store_id != identity:
                    raise TaskStoreError("Task index identity changed")
                self._store_id = identity
            self._lock_file = handle
            try:
                yield
            finally:
                self._lock_file = None

    def read(self) -> tuple[dict[str, Any], ...]:
        """Return detached records without upgrading or projecting stored state."""
        with self._lock():
            return tuple(self._read()[1].values())

    def initialize(self) -> None:
        """Create empty authority only when no prior index has been observed."""
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self._lock():
            revision, records = self._read()
            if not self._seen:
                self._write(revision, records, operation="initialize")

    def _write(self, revision: int, records: dict[str, dict[str, Any]], *, operation: str) -> None:
        payload: dict[str, Any] = {"version": 1, "store_id": self._store_id or uuid4().hex,
                                   "revision": revision + 1, "records": list(records.values())}
        payload["sha256"] = hashlib.sha256(_canonical(payload)).hexdigest()
        encoded = _canonical(payload)
        if len(encoded) > MAX_INDEX_BYTES:
            raise TaskStoreError("Task index exceeds its 8 MiB persistence limit")
        self._checkpoint(f"{operation}:before_commit")
        with atomic_evidence(self.path) as target:
            write_evidence(target, encoded)
        assert self._lock_file is not None
        self._lock_file.seek(0)
        if not self._lock_file.read(1):
            # Keep authority detectable after index loss, even before a task
            # has created a log. Never replace or truncate the lock inode.
            self._lock_file.write(payload["store_id"].encode("ascii"))
            self._lock_file.flush()
            os.fsync(self._lock_file.fileno())
        if os.name != "nt":
            with _evidence_directory(self.path.parent) as descriptor:
                assert descriptor is not None
                os.fsync(descriptor)
        self._store_id = payload["store_id"]
        self._seen = True
        self._checkpoint(f"{operation}:after_commit")

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Commit a unique queued intent before any subprocess dispatch."""
        record = _record(payload)
        if record["revision"] != 0 or record["status"] != "queued" or record["owner_id"] is None:
            raise TaskStoreError("Task index creation requires a new owned queued intent")
        with self._lock():
            revision, records = self._read()
            if record["task_id"] in records:
                raise TaskStoreError("Task index already contains this identity")
            record["revision"] = 1
            records[record["task_id"]] = record
            self._write(revision, records, operation="create")
            return deepcopy(record)

    def replace(self, payload: dict[str, Any], *, expected_revision: int,
                owner_id: str | None = None) -> dict[str, Any]:
        """Replace one expected revision; lifecycle changes require its owner."""
        record = _record(payload)
        with self._lock():
            revision, records = self._read()
            return self._replace(revision, records, record, expected_revision, owner_id)

    def update_owned(self, task_id: str, *, owner_id: str, changes: dict[str, Any],
                     metadata: dict[str, str] | None = None,
                     project: Callable[[dict[str, Any]], dict[str, Any]] | None = None) -> dict[str, Any]:
        """Merge an owned lifecycle observation with current metadata under lock.

        This retries no process effect. Concurrent title/metadata edits survive
        because the expected revision is selected within this same transaction.
        """
        if changes.keys() - {"status", "pid", "return_code", "started_at", "finished_at"}:
            raise TaskStoreError("Invalid owned task observation")
        with self._lock():
            revision, records = self._read()
            current = records.get(task_id)
            if current is None or current["owner_id"] != owner_id:
                raise TaskStoreError("Task lifecycle requires runtime ownership")
            evidence = _record(project(deepcopy(current))) if project is not None else current
            record = _record(dict(evidence, **changes, metadata={**evidence["metadata"], **(metadata or {})}))
            return self._replace(revision, records, record, current["revision"], owner_id)

    def project_evidence(self, task_id: str, project: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
        """Project terminal evidence under the same lock as record mutations."""
        with self._lock():
            revision, records = self._read()
            current = records.get(task_id)
            if current is None:
                raise TaskStoreError("Task index record disappeared")
            if current["status"] not in FINAL_STATES:
                return deepcopy(current)
            updated = _record(project(deepcopy(current)))
            if updated == current:
                return deepcopy(current)
            return self._replace(revision, records, updated, current["revision"], None)

    def _replace(self, revision: int, records: dict[str, dict[str, Any]], record: dict[str, Any],
                 expected_revision: int, owner_id: str | None) -> dict[str, Any]:
        current = records.get(record["task_id"])
        if type(expected_revision) is not int or current is None or current["revision"] != expected_revision:
            raise TaskStoreError("Task index record revision changed")
        if any(record[key] != current[key] for key in ("task_id", "owner_id", "operation_context", "created_at")):
            raise TaskStoreError("Task index immutable identity changed")
        lifecycle = any(record[key] != current[key] for key in ("status", "pid", "return_code", "started_at", "finished_at"))
        if lifecycle:
            if owner_id is None or current["owner_id"] != owner_id:
                raise TaskStoreError("Task lifecycle requires runtime ownership")
            allowed = {"queued": {"started", "cancelled"}, "started": {"running", "failed", "stopped", "outcome_unknown"},
                       "running": {"completed", "failed", "stopped", "outcome_unknown"},
                       "outcome_unknown": {"completed", "failed", "stopped"}}
            if record["status"] not in allowed.get(current["status"], set()):
                raise TaskStoreError("Task lifecycle transition is invalid")
        record["revision"] = expected_revision + 1
        records[record["task_id"]] = record
        self._write(revision, records, operation="replace")
        return deepcopy(record)
