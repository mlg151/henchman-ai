"""Project-local background task management services."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import signal
from asyncio.subprocess import Process
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar
from uuid import uuid4

from henchman.advanced.task_output import (
    MAX_TASK_OUTPUT_BYTES,
    TaskOutput,
    atomic_evidence,
    migrate_evidence,
    open_evidence,
    write_evidence,
)
from henchman.config.paths import resolve_project_settings_path
from henchman.config.repository import SettingsRepository
from henchman.utils.evidence_redaction import EvidenceRedactor

TASK_STATUS_RUNNING = "running"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"
TASK_STATUS_STOPPED = "stopped"
_FINAL_TASK_STATUSES = {
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_STOPPED,
}
_TERMINATE_TIMEOUT_SECONDS = 1.0
_MAX_INDEX_BYTES = 8 * 1024 * 1024


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""

    return datetime.now(UTC).isoformat()


def _coerce_argv(value: object) -> tuple[str, ...]:
    """Normalize an argv-like value into a non-empty tuple of strings."""

    if not isinstance(value, list | tuple):
        return ()
    return tuple(str(item) for item in value)


def _coerce_string_mapping(value: object) -> dict[str, str]:
    """Normalize a mapping-like value into string metadata."""

    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items() if str(key).strip()}


def _read_json(path: Path, *, default: object) -> object:
    """Read one JSON payload or return *default* when absent."""

    try:
        with open_evidence(path) as source:
            raw = source.read(_MAX_INDEX_BYTES + 1)
    except FileNotFoundError:
        return default
    if len(raw) > _MAX_INDEX_BYTES:
        raise ValueError("Task index exceeds the 8 MiB load limit; preserve it for explicit repair")
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError):
        raise ValueError("Task index is corrupt; preserve it for explicit repair") from None
    if not isinstance(payload, list):
        raise ValueError("Task index must be a list; preserve it for explicit repair")
    seen: set[str] = set()
    for item in payload:
        if not isinstance(item, dict) or not isinstance(item.get("task_id"), str) or not re.fullmatch(
            r"task-[0-9a-f]{12}", item["task_id"],
        ) or item["task_id"] in seen:
            raise ValueError("Task index has invalid or duplicate records; preserve it for explicit repair")
        required = {"title", "argv", "cwd", "status", "created_at", "started_at", "finished_at",
                    "output_path", "pid", "return_code", "metadata"}
        if not required <= item.keys() or not isinstance(item.get("status"), str) or (
            item["status"] not in _FINAL_TASK_STATUSES | {TASK_STATUS_RUNNING}
        ):
            raise ValueError("Task index has an invalid record; preserve it for explicit repair")
        valid = all(isinstance(item[key], str) for key in ("title", "cwd", "output_path"))
        valid = valid and isinstance(item["argv"], list) and all(isinstance(arg, str) for arg in item["argv"])
        valid = valid and isinstance(item["metadata"], dict) and all(
            isinstance(key, str) and isinstance(value, str) for key, value in item["metadata"].items()
        )
        valid = valid and all(item[key] is None or type(item[key]) is int for key in ("pid", "return_code"))
        try:
            for key in ("created_at", "started_at", "finished_at"):
                if key != "finished_at" or item[key] is not None:
                    datetime.fromisoformat(item[key])
        except (ValueError, TypeError):
            valid = False
        if not valid:
            raise ValueError("Task index has invalid record fields; preserve it for explicit repair")
        seen.add(item["task_id"])
    return payload


def _write_json(path: Path, payload: object) -> None:
    """Atomically replace the private index with already projected evidence."""

    path.parent.mkdir(parents=True, exist_ok=True)
    # Never replace unreadable/corrupt historical evidence with an empty index.
    _read_json(path, default=[])
    encoded = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    if len(encoded) > _MAX_INDEX_BYTES:
        raise OSError("Task index exceeds the 8 MiB persistence limit")
    with atomic_evidence(path) as output:
        write_evidence(output, encoded)


@dataclass(frozen=True, slots=True)
class TaskRecord:
    """Persisted metadata for one background task."""

    task_id: str
    title: str
    argv: tuple[str, ...]
    cwd: str
    status: str
    created_at: str
    started_at: str
    finished_at: str | None
    output_path: Path = field(repr=False)
    pid: int | None
    return_code: int | None
    metadata: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation of the task."""

        return {
            "task_id": self.task_id,
            "title": self.title,
            "argv": list(self.argv),
            "cwd": self.cwd,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "output_path": f"{self.task_id}.log",
            "pid": self.pid,
            "return_code": self.return_code,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> TaskRecord:
        """Create one task record from persisted JSON data."""

        raw_pid = payload.get("pid")
        raw_return_code = payload.get("return_code")
        return cls(
            task_id=str(payload.get("task_id", "")),
            title=str(payload.get("title", "")),
            argv=_coerce_argv(payload.get("argv", [])),
            cwd=str(payload.get("cwd", "")),
            status=str(payload.get("status", TASK_STATUS_FAILED)),
            created_at=str(payload.get("created_at", "")),
            started_at=str(payload.get("started_at", "")),
            finished_at=(
                str(payload["finished_at"]) if payload.get("finished_at") is not None else None
            ),
            output_path=Path(str(payload.get("output_path", ""))),
            pid=int(raw_pid) if isinstance(raw_pid, int) else None,
            return_code=(
                int(raw_return_code)
                if isinstance(raw_return_code, int)
                else None
            ),
            metadata=_coerce_string_mapping(payload.get("metadata")),
        )


@dataclass(slots=True)
class _TaskRuntime:
    """In-memory task runtime shared per project root."""

    records: dict[str, TaskRecord] = field(default_factory=dict)
    processes: dict[str, Process] = field(default_factory=dict)
    waiters: dict[str, asyncio.Future[TaskRecord]] = field(default_factory=dict)
    monitors: dict[str, asyncio.Task[None]] = field(default_factory=dict)
    policy: EvidenceRedactor = field(default_factory=EvidenceRedactor)


class TaskService:
    """Manage project-local background tasks and their output."""

    _runtimes: ClassVar[dict[Path, _TaskRuntime]] = {}

    def __init__(self, project_root: Path | None = None) -> None:
        """Initialize the task service for one project root."""

        self._project_root = (project_root or Path.cwd()).resolve()
        self._storage_dir = resolve_project_settings_path(self._project_root) / "tasks"
        self._index_path = self._storage_dir / "index.json"
        runtime = self._runtimes.setdefault(self._storage_dir, _TaskRuntime())
        self._runtime = runtime
        self._refresh_policy()
        if not runtime.records:
            self._load_runtime()
        else:
            # Retained logs were checked at load; recheck an individual log on
            # read without rescanning every completed job on each tool launch.
            self._persist_runtime()

    def _refresh_policy(self) -> None:
        self._runtime.policy.register_policy(
            SettingsRepository(project_root=self._project_root).evidence_redactor(),
        )

    def _project_record(self, record: TaskRecord) -> TaskRecord:
        """Project display fields while preserving owned paths and typed identities."""
        policy = self._runtime.policy
        metadata = policy.redact(record.metadata)
        return replace(record, title=policy.text(record.title),
                       argv=tuple(policy.text(arg) for arg in record.argv),
                       cwd=policy.text(record.cwd), metadata=metadata)

    async def start_task(
        self,
        *,
        argv: list[str] | tuple[str, ...],
        title: str | None = None,
        cwd: str | None = None,
        metadata: dict[str, object] | None = None,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
        shell: bool = False,
    ) -> TaskRecord:
        """Start a new background task and begin capturing output."""

        normalized_argv = _coerce_argv(argv)
        if not normalized_argv or not normalized_argv[0].strip():
            msg = "A non-empty argv list is required."
            raise ValueError(msg)
        if shell and len(normalized_argv) != 1:
            raise ValueError("Shell execution requires exactly one command string.")
        if timeout is not None and timeout < 0:
            raise ValueError("Timeout must be zero or positive.")

        self._refresh_policy()
        self._runtime.policy.register_config(env)
        self._runtime.policy.register_config(metadata)

        resolved_cwd = str(Path(cwd).expanduser().resolve()) if cwd else str(self._project_root)
        task_id = f"task-{uuid4().hex[:12]}"
        output_path = self._storage_dir / f"{task_id}.log"
        # Prepare display evidence before acquiring process ownership; user
        # metadata conversion must not strand a process if it raises.
        record = self._project_record(TaskRecord(
            task_id=task_id,
            title=title.strip() if isinstance(title, str) and title.strip() else normalized_argv[0],
            argv=normalized_argv, cwd=resolved_cwd, status=TASK_STATUS_RUNNING,
            created_at=_now_iso(), started_at=_now_iso(), finished_at=None,
            output_path=output_path, pid=None, return_code=None,
            metadata=_coerce_string_mapping(metadata),
        ))
        output: TaskOutput | None = None
        process: Process | None = None
        spawn: asyncio.Task[Process] | None = None
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output = TaskOutput(output_path, self._runtime.policy)
            if shell:
                launch = asyncio.create_subprocess_shell(
                    normalized_argv[0], cwd=resolved_cwd, env=env, stdout=output.writer,
                    stderr=asyncio.subprocess.STDOUT, stdin=asyncio.subprocess.DEVNULL,
                    start_new_session=os.name == "posix",
                )
            else:
                launch = asyncio.create_subprocess_exec(
                    *normalized_argv, cwd=resolved_cwd, env=env, stdout=output.writer,
                    stderr=asyncio.subprocess.STDOUT, stdin=asyncio.subprocess.DEVNULL,
                    start_new_session=os.name == "posix",
                )
            spawn = asyncio.create_task(launch)
            # Retain the process result if cancellation arrives during spawn.
            process = await asyncio.shield(spawn)
        except BaseException as exc:
            if output is not None:
                interrupted = await self._await_cleanup(asyncio.create_task(
                    self._cancel_launch(spawn, output),
                ))
                if interrupted:
                    raise asyncio.CancelledError from None
            if isinstance(exc, OSError):
                raise type(exc)(self._runtime.policy.text(str(exc))) from None
            raise
        finally:
            if output is not None:
                output.close_writer()

        record = replace(record, pid=process.pid)
        self._runtime.records[task_id] = record
        self._runtime.processes[task_id] = process
        self._runtime.waiters[task_id] = asyncio.get_running_loop().create_future()
        try:
            self._persist_runtime()
        except OSError as exc:
            interrupted = await self._await_cleanup(asyncio.create_task(
                self._finish_capture(process, output),
            ))
            self._runtime.records.pop(task_id, None)
            self._runtime.processes.pop(task_id, None)
            self._runtime.waiters.pop(task_id, None)
            if interrupted:
                raise asyncio.CancelledError from None
            raise type(exc)(self._runtime.policy.text(str(exc))) from None
        self._runtime.monitors[task_id] = asyncio.create_task(
            self._monitor_process(task_id, process, output, timeout=timeout or None),
        )
        # Enter the monitor before returning ownership to the caller. A task
        # cancelled before its first step cannot run its cancellation cleanup.
        try:
            await asyncio.sleep(0)
        except asyncio.CancelledError:
            await self.stop_task(task_id)
            raise
        return record

    def get_task(self, task_id: str) -> TaskRecord | None:
        """Return one task by ID when it exists."""

        record = self._runtime.records.get(task_id)
        return self._project_record(record) if record else None

    def list_tasks(self, *, status: str | None = None) -> list[TaskRecord]:
        """Return all known tasks, optionally filtered by status."""

        records = [self._project_record(record) for record in
                   sorted(self._runtime.records.values(), key=lambda item: item.created_at)]
        if status is None:
            return records
        return [record for record in records if record.status == status]

    def tail_output(self, task_id: str, *, lines: int = 25) -> str:
        """Return the trailing output lines for one task."""

        record = self.get_task(task_id)
        if record is None:
            msg = f"Task {task_id} not found."
            raise KeyError(msg)

        self._refresh_policy()
        if self._migrate_log(record):
            self._persist_runtime()
        record = self._runtime.records[task_id]
        if record.metadata.get("evidence_migration_error"):
            raise OSError(record.metadata["evidence_migration_error"])
        try:
            with open_evidence(record.output_path) as output:
                content = output.read(MAX_TASK_OUTPUT_BYTES).decode("utf-8", errors="replace")
        except FileNotFoundError:
            return ""
        except OSError as exc:
            raise type(exc)(self._runtime.policy.text(str(exc))) from None
        output_lines = self._runtime.policy.text(content).splitlines()
        if lines <= 0:
            return "\n".join(output_lines)
        return "\n".join(output_lines[-lines:])

    def _migrate_log(self, record: TaskRecord) -> bool:
        """Migrate retained logs, preserving live writer ownership and failures."""
        if record.task_id in self._runtime.processes:
            return False
        metadata = dict(record.metadata)
        previous = metadata.pop("evidence_migration_error", None)
        if previous and metadata.get("error") == previous:
            metadata.pop("error")
        try:
            truncated = migrate_evidence(record.output_path, self._runtime.policy)
        except FileNotFoundError:
            return False
        except (OSError, UnicodeError) as exc:
            detail = self._runtime.policy.text(str(exc))
            message = self._runtime.policy.text(f"Task evidence migration failed: {detail}")
            metadata["evidence_migration_error"] = message
            metadata.setdefault("error", message)
        else:
            if truncated:
                metadata["output_truncated"] = "true"
        updated = self._project_record(replace(record, metadata=metadata))
        self._runtime.records[record.task_id] = updated
        return updated != record

    def update_task(
        self,
        task_id: str,
        *,
        title: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> TaskRecord:
        """Update task metadata without affecting the running process."""

        record = self.get_task(task_id)
        if record is None:
            msg = f"Task {task_id} not found."
            raise KeyError(msg)

        self._refresh_policy()
        self._runtime.policy.register_config(metadata)
        merged_metadata = dict(record.metadata)
        merged_metadata.update(_coerce_string_mapping(metadata))
        updated = self._project_record(replace(
            record,
            title=title.strip() if isinstance(title, str) and title.strip() else record.title,
            metadata=merged_metadata,
        ))
        self._runtime.records[task_id] = updated
        self._persist_runtime()
        return updated

    async def stop_task(self, task_id: str) -> TaskRecord:
        """Stop a running task and wait for its final persisted state."""

        record = self.get_task(task_id)
        if record is None:
            msg = f"Task {task_id} not found."
            raise KeyError(msg)
        if record.status in _FINAL_TASK_STATUSES and task_id not in self._runtime.processes:
            return record

        process = self._runtime.processes.get(task_id)
        if process is None:
            updated = replace(record, status=TASK_STATUS_STOPPED, finished_at=_now_iso())
            self._runtime.records[task_id] = updated
            self._persist_runtime()
            return updated

        self._runtime.records[task_id] = replace(record, status=TASK_STATUS_STOPPED)
        # Stop the process even when storage has become unwritable. The monitor
        # reports persistence failures in the finalized task record.
        await self._terminate_process(process)
        return await self.wait_for_task(task_id, timeout=5.0)

    async def wait_for_task(self, task_id: str, timeout: float | None = None) -> TaskRecord:
        """Wait for a task to reach a final state and return its record."""

        record = self.get_task(task_id)
        if record is None:
            msg = f"Task {task_id} not found."
            raise KeyError(msg)
        if record.status in _FINAL_TASK_STATUSES and task_id not in self._runtime.processes:
            return record

        waiter = self._runtime.waiters.get(task_id)
        if waiter is None:
            msg = f"Task {task_id} is missing a runtime waiter."
            raise RuntimeError(msg)
        return await asyncio.wait_for(asyncio.shield(waiter), timeout=timeout)

    def _load_runtime(self) -> None:
        """Load persisted task metadata into the shared runtime."""

        try:
            payload = _read_json(self._index_path, default=[])
        except OSError as exc:
            raise type(exc)(self._runtime.policy.text(str(exc))) from None
        if not isinstance(payload, list):
            return
        self._runtime.policy.register_config(payload)
        for item in payload:
            if not isinstance(item, dict):
                continue
            record = TaskRecord.from_dict(item)
            if not re.fullmatch(r"task-[0-9a-f]{12}", record.task_id):
                continue
            # Never replay a stored absolute path or redacted display value.
            record = self._project_record(replace(
                record, output_path=self._storage_dir / f"{record.task_id}.log",
            ))
            if record.status == TASK_STATUS_RUNNING:
                record = replace(
                    record,
                    status=TASK_STATUS_STOPPED,
                    finished_at=record.finished_at or _now_iso(),
                )
            self._runtime.records[record.task_id] = record
            self._migrate_log(record)
        self._persist_runtime()

    async def _terminate_process(self, process: Process) -> None:
        """Terminate the owned process group and reap its direct child."""
        with contextlib.suppress(ProcessLookupError):
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGTERM)
            else:
                process.terminate()
        try:
            if process.returncode is None:
                await asyncio.wait_for(process.wait(), timeout=_TERMINATE_TIMEOUT_SECONDS)
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
            await process.wait()
        finally:
            # The parent can exit while a descendant ignores SIGTERM.
            if os.name == "posix":
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)

    async def _monitor_process(
        self, task_id: str, process: Process, output: TaskOutput,
        *, timeout: float | None = None,
    ) -> None:
        """Enforce task lifetime and finalize persisted state on exit."""
        cancelled = False
        timed_out = False
        diagnostic_error: str | None = None
        process_wait = asyncio.create_task(process.wait())
        try:
            done, _ = await asyncio.wait(
                (process_wait, output.failure), timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
            timed_out = not done
        except asyncio.CancelledError:
            cancelled = True
            self._runtime.records[task_id] = replace(
                self._runtime.records[task_id], status=TASK_STATUS_STOPPED,
            )
        # Cleanup remains owned and awaited even if cancellation is repeated.
        cleanup = asyncio.create_task(self._finish_capture(process, output))
        while True:
            try:
                await asyncio.shield(cleanup)
                break
            except asyncio.CancelledError:
                cancelled = True
                self._runtime.records[task_id] = replace(
                    self._runtime.records[task_id], status=TASK_STATUS_STOPPED,
                )
        await process_wait
        if timed_out:
            try:
                output.append_diagnostic(f"\nTask timed out after {timeout:g} seconds.\n")
            except OSError as exc:
                detail = self._runtime.policy.text(str(exc))
                diagnostic_error = self._runtime.policy.text(
                    f"Task timeout; could not write timeout diagnostic: {detail}",
                )
        if output.error:
            diagnostic_error = output.error
        return_code = process.returncode
        current = self._runtime.records[task_id]
        if diagnostic_error is not None:
            current = replace(current, metadata={**current.metadata, "error": diagnostic_error})
        if output.truncated:
            current = replace(current, metadata={**current.metadata, "output_truncated": "true"})
        final_status = (
            TASK_STATUS_STOPPED
            if current.status == TASK_STATUS_STOPPED
            else TASK_STATUS_FAILED
            if timed_out or diagnostic_error is not None
            else TASK_STATUS_COMPLETED
            if return_code == 0
            else TASK_STATUS_FAILED
        )
        finalized = self._project_record(replace(
            current,
            status=final_status,
            finished_at=_now_iso(),
            return_code=return_code,
            pid=None,
        ))
        self._runtime.records[task_id] = finalized
        self._runtime.processes.pop(task_id, None)
        self._runtime.monitors.pop(task_id, None)
        waiter = self._runtime.waiters.pop(task_id, None)
        try:
            self._persist_runtime()
        except OSError as exc:
            detail = self._runtime.policy.text(str(exc))
            finalized = replace(
                finalized, status=TASK_STATUS_FAILED,
                metadata={**finalized.metadata, "error": self._runtime.policy.text(
                    f"Could not persist task status: {detail}",
                )},
            )
            self._runtime.records[task_id] = finalized
        if waiter is not None and not waiter.done():
            waiter.set_result(finalized)
        if cancelled:
            raise asyncio.CancelledError

    async def _finish_capture(self, process: Process, output: TaskOutput) -> None:
        """Reap the owned process/group before closing its bounded reader."""
        try:
            if os.name == "posix" or process.returncode is None:
                await self._terminate_process(process)
        finally:
            await output.finish()

    async def _cancel_launch(
        self, spawn: asyncio.Task[Process] | None, output: TaskOutput,
    ) -> None:
        """Recover any spawned process before releasing the launch's capture."""
        process = None
        if spawn is not None:
            # The original launch exception (or cancellation) is propagated
            # by start_task after its evidence resources are closed.
            with contextlib.suppress(Exception):
                process = await spawn
        if process is None:
            await output.finish()
        else:
            await self._finish_capture(process, output)

    @staticmethod
    async def _await_cleanup(cleanup: asyncio.Task[None]) -> bool:
        """Await owned cleanup to completion and remember repeated cancellation."""
        interrupted = False
        while True:
            try:
                await asyncio.shield(cleanup)
                return interrupted
            except asyncio.CancelledError:
                if cleanup.cancelled():
                    raise
                interrupted = True

    def _persist_runtime(self) -> None:
        """Persist the current task index to project-local storage."""

        payload = [
            self._project_record(record).to_dict()
            for record in sorted(self._runtime.records.values(), key=lambda item: item.created_at)
        ]
        try:
            _write_json(self._index_path, payload)
        except (OSError, ValueError) as exc:
            raise OSError(self._runtime.policy.text(str(exc))) from None
