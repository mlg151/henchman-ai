"""Project-local background task management services."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import signal
from asyncio.subprocess import Process
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar
from uuid import uuid4

from henchman.config.paths import resolve_project_settings_path

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

    if not path.exists():
        return default
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, payload: object) -> None:
    """Persist one JSON payload with stable formatting."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


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
    output_path: Path
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
            "output_path": str(self.output_path),
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
        if not runtime.records:
            self._load_runtime()

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

        resolved_cwd = str(Path(cwd).expanduser().resolve()) if cwd else str(self._project_root)
        task_id = f"task-{uuid4().hex[:12]}"
        output_path = self._storage_dir / f"{task_id}.log"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # A file transport captures output without pipe backpressure or inherited
        # descendant pipes preventing process completion from being observed.
        with output_path.open("wb") as output:
            if shell:
                process = await asyncio.create_subprocess_shell(
                    normalized_argv[0], cwd=resolved_cwd, env=env, stdout=output,
                    stderr=asyncio.subprocess.STDOUT, stdin=asyncio.subprocess.DEVNULL,
                    start_new_session=os.name == "posix",
                )
            else:
                process = await asyncio.create_subprocess_exec(
                    *normalized_argv, cwd=resolved_cwd, env=env, stdout=output,
                    stderr=asyncio.subprocess.STDOUT, stdin=asyncio.subprocess.DEVNULL,
                    start_new_session=os.name == "posix",
                )

        record = TaskRecord(
            task_id=task_id,
            title=title.strip() if isinstance(title, str) and title.strip() else normalized_argv[0],
            argv=normalized_argv,
            cwd=resolved_cwd,
            status=TASK_STATUS_RUNNING,
            created_at=_now_iso(),
            started_at=_now_iso(),
            finished_at=None,
            output_path=output_path,
            pid=process.pid,
            return_code=None,
            metadata=_coerce_string_mapping(metadata),
        )
        self._runtime.records[task_id] = record
        self._runtime.processes[task_id] = process
        self._runtime.waiters[task_id] = asyncio.get_running_loop().create_future()
        try:
            self._persist_runtime()
        except OSError:
            await self._terminate_process(process)
            self._runtime.records.pop(task_id, None)
            self._runtime.processes.pop(task_id, None)
            self._runtime.waiters.pop(task_id, None)
            raise
        self._runtime.monitors[task_id] = asyncio.create_task(
            self._monitor_process(task_id, process, timeout=timeout or None),
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

        return self._runtime.records.get(task_id)

    def list_tasks(self, *, status: str | None = None) -> list[TaskRecord]:
        """Return all known tasks, optionally filtered by status."""

        records = sorted(self._runtime.records.values(), key=lambda item: item.created_at)
        if status is None:
            return records
        return [record for record in records if record.status == status]

    def tail_output(self, task_id: str, *, lines: int = 25) -> str:
        """Return the trailing output lines for one task."""

        record = self.get_task(task_id)
        if record is None:
            msg = f"Task {task_id} not found."
            raise KeyError(msg)

        if not record.output_path.exists():
            return ""

        output_lines = record.output_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if lines <= 0:
            return "\n".join(output_lines)
        return "\n".join(output_lines[-lines:])

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

        merged_metadata = dict(record.metadata)
        merged_metadata.update(_coerce_string_mapping(metadata))
        updated = replace(
            record,
            title=title.strip() if isinstance(title, str) and title.strip() else record.title,
            metadata=merged_metadata,
        )
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

        payload = _read_json(self._index_path, default=[])
        if not isinstance(payload, list):
            return
        for item in payload:
            if not isinstance(item, dict):
                continue
            record = TaskRecord.from_dict(item)
            if record.status == TASK_STATUS_RUNNING:
                record = replace(
                    record,
                    status=TASK_STATUS_STOPPED,
                    finished_at=record.finished_at or _now_iso(),
                )
            self._runtime.records[record.task_id] = record
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
        self, task_id: str, process: Process, *, timeout: float | None = None,
    ) -> None:
        """Enforce task lifetime and finalize persisted state on exit."""
        cancelled = False
        timed_out = False
        diagnostic_error: str | None = None
        try:
            await asyncio.wait_for(process.wait(), timeout=timeout)
        except TimeoutError:
            timed_out = True
            await self._terminate_process(process)
            try:
                with self._runtime.records[task_id].output_path.open("a", encoding="utf-8") as handle:
                    handle.write(f"\nTask timed out after {timeout:g} seconds.\n")
            except OSError as exc:
                diagnostic_error = f"Task timeout; could not write timeout diagnostic: {exc}"
        except asyncio.CancelledError:
            cancelled = True
            await self._terminate_process(process)
            self._runtime.records[task_id] = replace(
                self._runtime.records[task_id], status=TASK_STATUS_STOPPED,
            )
        else:
            # The task owns a process group, including children that outlive its
            # leader. They must not escape tracking when that leader exits.
            if os.name == "posix":
                await self._terminate_process(process)
        return_code = process.returncode
        current = self._runtime.records[task_id]
        if diagnostic_error is not None:
            current = replace(current, metadata={**current.metadata, "error": diagnostic_error})
        final_status = (
            TASK_STATUS_STOPPED
            if current.status == TASK_STATUS_STOPPED
            else TASK_STATUS_FAILED
            if timed_out
            else TASK_STATUS_COMPLETED
            if return_code == 0
            else TASK_STATUS_FAILED
        )
        finalized = replace(
            current,
            status=final_status,
            finished_at=_now_iso(),
            return_code=return_code,
            pid=None,
        )
        self._runtime.records[task_id] = finalized
        self._runtime.processes.pop(task_id, None)
        self._runtime.monitors.pop(task_id, None)
        waiter = self._runtime.waiters.pop(task_id, None)
        try:
            self._persist_runtime()
        except OSError as exc:
            finalized = replace(
                finalized, status=TASK_STATUS_FAILED,
                metadata={**finalized.metadata, "error": f"Could not persist task status: {exc}"},
            )
            self._runtime.records[task_id] = finalized
        if waiter is not None and not waiter.done():
            waiter.set_result(finalized)
        if cancelled:
            raise asyncio.CancelledError

    def _persist_runtime(self) -> None:
        """Persist the current task index to project-local storage."""

        payload = [
            record.to_dict()
            for record in sorted(self._runtime.records.values(), key=lambda item: item.created_at)
        ]
        _write_json(self._index_path, payload)
