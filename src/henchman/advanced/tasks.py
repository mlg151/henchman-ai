"""Project-local background task management services."""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import sys
from asyncio.subprocess import Process
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar
from uuid import uuid4

from henchman.advanced.task_output import (
    MAX_TASK_OUTPUT_BYTES,
    TaskOutput,
    migrate_evidence,
    open_evidence,
)
from henchman.advanced.task_store import FINAL_STATES, TaskStore, TaskStoreError
from henchman.config.paths import resolve_project_settings_path
from henchman.config.repository import SettingsRepository
from henchman.utils.evidence_redaction import EvidenceRedactor

TASK_STATUS_QUEUED = "queued"
TASK_STATUS_STARTED = "started"
TASK_STATUS_CANCELLED = "cancelled"
TASK_STATUS_RUNNING = "running"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"
TASK_STATUS_STOPPED = "stopped"
TASK_STATUS_OUTCOME_UNKNOWN = "outcome_unknown"
_FINAL_TASK_STATUSES = FINAL_STATES
_TERMINATE_TIMEOUT_SECONDS = 1.0
_DARWIN_EXIT_SETTLE_SECONDS = 0.25


class TaskOwnershipError(RuntimeError):
    """Stored process evidence cannot authorize control of an unowned process."""


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


@dataclass(frozen=True, slots=True)
class TaskRecord:
    """Persisted metadata for one background task."""

    task_id: str
    title: str
    argv: tuple[str, ...]
    cwd: str
    status: str
    created_at: str
    started_at: str | None
    finished_at: str | None
    output_path: Path = field(repr=False)
    pid: int | None
    return_code: int | None
    metadata: dict[str, str]
    revision: int = 0
    owner_id: str | None = None
    operation_context: dict[str, str] | None = None

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
            "revision": self.revision,
            "owner_id": self.owner_id,
            "operation_context": dict(self.operation_context) if self.operation_context is not None else None,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> TaskRecord:
        """Create one task record from persisted JSON data."""

        raw_pid = payload.get("pid")
        raw_return_code = payload.get("return_code")
        raw_revision = payload.get("revision", 0)
        return cls(
            task_id=str(payload.get("task_id", "")),
            title=str(payload.get("title", "")),
            argv=_coerce_argv(payload.get("argv", [])),
            cwd=str(payload.get("cwd", "")),
            status=str(payload.get("status", TASK_STATUS_FAILED)),
            created_at=str(payload.get("created_at", "")),
            started_at=str(payload["started_at"]) if payload.get("started_at") is not None else None,
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
            revision=raw_revision if type(raw_revision) is int else 0,
            owner_id=str(payload["owner_id"]) if payload.get("owner_id") is not None else None,
            operation_context=_coerce_string_mapping(payload["operation_context"]) if payload.get("operation_context") is not None else None,
        )


@dataclass(slots=True)
class _TaskRuntime:
    """In-memory task runtime shared per project root."""

    records: dict[str, TaskRecord] = field(default_factory=dict)
    processes: dict[str, Process] = field(default_factory=dict)
    waiters: dict[str, asyncio.Future[TaskRecord]] = field(default_factory=dict)
    monitors: dict[str, asyncio.Task[None]] = field(default_factory=dict)
    policy: EvidenceRedactor = field(default_factory=EvidenceRedactor)
    owner_id: str = field(default_factory=lambda: uuid4().hex)
    process_id: int = field(default_factory=os.getpid)
    store: TaskStore | None = None
    stopping: set[str] = field(default_factory=set)
    local_failures: dict[str, TaskRecord] = field(default_factory=dict)
    launches: dict[str, asyncio.Task[Any]] = field(default_factory=dict)


class TaskService:
    """Manage project-local background tasks and their output."""

    _runtimes: ClassVar[dict[Path, _TaskRuntime]] = {}

    def __init__(self, project_root: Path | None = None) -> None:
        """Initialize the task service for one project root."""

        self._project_root = (project_root or Path.cwd()).resolve()
        self._storage_dir = resolve_project_settings_path(self._project_root) / "tasks"
        self._index_path = self._storage_dir / "index.json"
        runtime = self._runtimes.get(self._storage_dir)
        if runtime is None or runtime.process_id != os.getpid():
            runtime = _TaskRuntime(store=TaskStore(self._index_path))
            self._runtimes[self._storage_dir] = runtime
        self._runtime = runtime
        assert runtime.store is not None
        self._store = runtime.store
        self._refresh_policy()
        self._store.initialize()
        self._load_runtime()

    @classmethod
    def has_active_work(cls, project_root: Path) -> bool:
        """Inspect local handles only, without resolving paths or opening storage.

        The caller supplies its already resolved project root. Stored PIDs and
        recovered task states cannot confer ownership or block as live handles.
        """
        key = Path(os.path.abspath(project_root)) / ".henchman" / "tasks"
        runtime = cls._runtimes.get(key)
        return runtime is not None and runtime.process_id == os.getpid() and (
            any(process.returncode is None for process in runtime.processes.values())
            or any(not monitor.done() for monitor in runtime.monitors.values())
            or any(not launch.done() for launch in runtime.launches.values())
        )

    def _owns_live_process(self, task_id: str) -> bool:
        """Observe an in-process, same-loop live handle without adopting a PID."""
        runtime = self._runtime
        process = runtime.processes.get(task_id)
        record = runtime.records.get(task_id)
        if (runtime.process_id != os.getpid() or process is None or process.returncode is not None
            or record is None or record.owner_id != runtime.owner_id):
            return False
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return False
        return getattr(process, "_loop", None) is loop

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
        from henchman.core.runtime_operations import current_operation_call

        invocation = current_operation_call()
        context = ({"operation_id": invocation.binding.operation_id, **asdict(invocation.binding.context)}
                   if invocation is not None else None)
        record = self._project_record(TaskRecord(
            task_id=task_id,
            title=title.strip() if isinstance(title, str) and title.strip() else normalized_argv[0],
            argv=normalized_argv, cwd=resolved_cwd, status=TASK_STATUS_QUEUED,
            created_at=_now_iso(), started_at=None, finished_at=None,
            output_path=output_path, pid=None, return_code=None,
            metadata=_coerce_string_mapping(metadata), owner_id=self._runtime.owner_id,
            operation_context=context,
        ))
        output: TaskOutput | None = None
        process: Process | None = None
        spawn: asyncio.Task[Process] | None = None
        queued = False
        launch_owner = asyncio.current_task()
        assert launch_owner is not None
        self._runtime.launches[task_id] = launch_owner
        try:
            record = self._decode_record(self._store.create(record.to_dict()))
            self._runtime.records[task_id] = record
            queued = True
            output = TaskOutput(output_path, self._runtime.policy)
            record = self._owned_change(task_id, status=TASK_STATUS_STARTED, started_at=_now_iso())
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
            process = await asyncio.shield(spawn)
            self._runtime.processes[task_id] = process
            record = self._owned_change(task_id, status=TASK_STATUS_RUNNING, pid=process.pid)
        except BaseException as exc:
            interrupted = False
            cleanup_failed = False
            if output is not None:
                try:
                    interrupted = await self._await_cleanup(asyncio.create_task(
                        self._cancel_launch(spawn, output),
                    ))
                except BaseException as cleanup:
                    cleanup_failed = True
                    exc.add_note(self._runtime.policy.text(f"Task cleanup also failed: {cleanup}"))
            if process is None and spawn is not None and spawn.done() and not spawn.cancelled():
                with contextlib.suppress(Exception):
                    process = spawn.result()
            live = cleanup_failed and process is not None and process.returncode is None
            if live:
                assert process is not None
                self._runtime.processes[task_id] = process
            else:
                self._runtime.processes.pop(task_id, None)
            if queued:
                observed = self._runtime.records[task_id]
                stopped = isinstance(exc, asyncio.CancelledError) or interrupted
                status = (TASK_STATUS_CANCELLED if observed.status == TASK_STATUS_QUEUED
                          else TASK_STATUS_OUTCOME_UNKNOWN if cleanup_failed or stopped and process is None
                          else TASK_STATUS_STOPPED if stopped else TASK_STATUS_FAILED)
                try:
                    self._owned_change(task_id, status=status, pid=process.pid if live and process is not None else None,
                                       finished_at=None if status == TASK_STATUS_OUTCOME_UNKNOWN else _now_iso(),
                                       metadata={"error": self._runtime.policy.text(str(exc))})
                except (OSError, ValueError) as persistence:
                    exc.add_note(self._runtime.policy.text(f"Task intent retained; status save failed: {persistence}"))
            if interrupted:
                raise asyncio.CancelledError from None
            if isinstance(exc, OSError):
                raise OSError(self._runtime.policy.text(str(exc))) from None
            raise
        finally:
            if output is not None:
                output.close_writer()
            self._runtime.launches.pop(task_id, None)

        self._runtime.waiters[task_id] = asyncio.get_running_loop().create_future()
        self._runtime.monitors[task_id] = asyncio.create_task(
            self._monitor_process(task_id, process, output, timeout=timeout or None),
        )
        try:
            await asyncio.sleep(0)
        except asyncio.CancelledError:
            await self.stop_task(task_id)
            raise
        return record

    def _decode_record(self, payload: dict[str, Any]) -> TaskRecord:
        record = TaskRecord.from_dict(payload)
        return self._project_record(replace(record, output_path=self._storage_dir / f"{record.task_id}.log"))

    def _owned_change(self, task_id: str, *, metadata: dict[str, str] | None = None, **changes: Any) -> TaskRecord:
        """Commit a local observation without overwriting concurrent metadata."""
        self._refresh_policy()
        safe = self._runtime.policy.redact(metadata or {})
        updated = self._decode_record(self._store.update_owned(
            task_id, owner_id=self._runtime.owner_id, changes=changes, metadata=safe,
            project=lambda payload: self._decode_record(payload).to_dict(),
        ))
        self._runtime.records[task_id] = updated
        return updated

    def _refresh_records(self) -> None:
        """Read current evidence without changing local process ownership."""
        payload = self._store.read()
        self._runtime.policy.register_config(payload)
        records = {item["task_id"]: self._decode_record(item) for item in payload}
        for identity in self._runtime.processes:
            current = records.get(identity)
            if current is None or current.owner_id != self._runtime.owner_id:
                raise TaskStoreError("Task index no longer matches local ownership")
        self._runtime.records = records

    def _view(self, record: TaskRecord) -> TaskRecord:
        if record.task_id in self._runtime.local_failures:
            return self._runtime.local_failures[record.task_id]
        if record.status in {TASK_STATUS_STARTED, TASK_STATUS_RUNNING} and record.task_id not in self._runtime.processes:
            record = replace(record, status=TASK_STATUS_OUTCOME_UNKNOWN)
        return self._project_record(record)

    def get_task(self, task_id: str) -> TaskRecord | None:
        """Read fresh evidence; stored lifecycle never confers local ownership."""
        self._refresh_records()
        record = self._runtime.records.get(task_id)
        return self._view(record) if record else None

    def list_tasks(self, *, status: str | None = None) -> list[TaskRecord]:
        """Return refreshed task views without rewriting unowned process state."""
        self._refresh_records()
        records = [self._view(record) for record in sorted(self._runtime.records.values(), key=lambda item: item.created_at)]
        return records if status is None else [record for record in records if record.status == status]

    def tail_output(self, task_id: str, *, lines: int = 25) -> str:
        """Return the trailing output lines for one task."""

        record = self.get_task(task_id)
        if record is None:
            msg = f"Task {task_id} not found."
            raise KeyError(msg)

        self._refresh_policy()
        self._migrate_log(record)
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
        """Never replace an unresolved log which another runtime may be writing."""
        if record.task_id in self._runtime.processes or record.status not in _FINAL_TASK_STATUSES:
            return False

        def project(payload: dict[str, Any]) -> dict[str, Any]:
            current = self._decode_record(payload)
            metadata = dict(current.metadata)
            previous = metadata.pop("evidence_migration_error", None)
            if previous and metadata.get("error") == previous:
                metadata.pop("error")
            try:
                truncated = migrate_evidence(current.output_path, self._runtime.policy)
            except FileNotFoundError:
                return current.to_dict()
            except (OSError, UnicodeError) as exc:
                detail = self._runtime.policy.text(str(exc))
                message = self._runtime.policy.text(f"Task evidence migration failed: {detail}")
                metadata["evidence_migration_error"] = message
                metadata.setdefault("error", message)
            else:
                if truncated:
                    metadata["output_truncated"] = "true"
            return self._project_record(replace(current, metadata=metadata)).to_dict()

        updated = self._decode_record(self._store.project_evidence(record.task_id, project))
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

        self._refresh_records()
        record = self._runtime.records.get(task_id)
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
        updated = self._decode_record(self._store.replace(updated.to_dict(), expected_revision=record.revision))
        self._runtime.records[task_id] = updated
        return self._view(updated)

    async def stop_task(self, task_id: str) -> TaskRecord:
        """Stop only an owned child, even if its durable index became unreadable."""
        process = self._runtime.processes.get(task_id)
        if process is None:
            record = self._runtime.local_failures.get(task_id) or self.get_task(task_id)
            if record is None:
                raise KeyError(f"Task {task_id} not found.")
            if record.status in _FINAL_TASK_STATUSES:
                return record
            raise TaskOwnershipError(
                f"Task {task_id} is not owned by this runtime; its outcome is unknown. "
                "Inspect external process state and captured output before starting new work."
            )
        waiter = self._runtime.waiters.get(task_id)
        if self._runtime.process_id != os.getpid():
            raise TaskOwnershipError("Task process is not owned by this runtime")
        loop = asyncio.get_running_loop()
        # asyncio's subprocess handle has no public loop accessor. Fail
        # closed if its owning loop cannot be established, including for a
        # failed launch that never acquired a monitor waiter.
        if getattr(process, "_loop", None) is not loop or (waiter is not None and waiter.get_loop() is not loop):
            raise TaskOwnershipError("Task process is owned by a different event loop")
        self._runtime.stopping.add(task_id)
        await self._terminate_process(process)
        if waiter is None:
            # A failed launch acknowledgement may retain a live handle after
            # cleanup failed, before a regular monitor could be established.
            try:
                return self._owned_change(task_id, status=TASK_STATUS_STOPPED, pid=None,
                                          return_code=process.returncode, finished_at=_now_iso())
            finally:
                self._runtime.processes.pop(task_id, None)
                self._runtime.stopping.discard(task_id)
        # The monitor may have settled and removed its map entry while the
        # process was terminating. Preserve the captured result rather than
        # mistaking it for an unmonitored failed launch.
        return await asyncio.wait_for(asyncio.shield(waiter), timeout=5.0)

    async def wait_for_task(self, task_id: str, timeout: float | None = None) -> TaskRecord:
        """Await a local observation; an unowned queued/unknown record cannot run."""
        waiter = self._runtime.waiters.get(task_id)
        if waiter is not None:
            return await asyncio.wait_for(asyncio.shield(waiter), timeout=timeout)
        record = self._runtime.local_failures.get(task_id) or self.get_task(task_id)
        if record is None:
            raise KeyError(f"Task {task_id} not found.")
        if record.status in _FINAL_TASK_STATUSES:
            return record
        raise TaskOwnershipError(
            f"Task {task_id} is not owned by this runtime; waiting cannot establish its outcome."
        )

    def _load_runtime(self) -> None:
        """Refresh authority and migrate only completed, unowned log evidence."""
        self._refresh_records()
        for record in tuple(self._runtime.records.values()):
            self._migrate_log(record)

    async def _terminate_process(self, process: Process) -> None:
        """Terminate the owned process group and reap its direct child."""
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except PermissionError as error:
                if sys.platform != "darwin":
                    raise
                # Darwin may report EPERM for an exited, unreaped group leader.
                # Recheck the group after observing this owned child's exit;
                # an unchanged permission failure still means unknown cleanup.
                try:
                    await asyncio.wait_for(process.wait(), timeout=_DARWIN_EXIT_SETTLE_SECONDS)
                except TimeoutError:
                    raise error from None
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    return
        else:
            with contextlib.suppress(ProcessLookupError):
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
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except PermissionError as error:
                    raise PermissionError(error.errno, f"Task group SIGKILL failed: {error.strerror}") from error

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
            self._runtime.stopping.add(task_id)
        # Cleanup remains owned and awaited even if cancellation is repeated.
        cleanup = asyncio.create_task(self._finish_capture(process, output))
        while True:
            try:
                await asyncio.shield(cleanup)
                break
            except asyncio.CancelledError:
                cancelled = True
                self._runtime.stopping.add(task_id)
            except Exception as exc:
                process_wait.cancel()
                await asyncio.gather(process_wait, return_exceptions=True)
                message = self._runtime.policy.text(f"Task cleanup failed: {exc}")
                observed = replace(self._runtime.records[task_id], status=TASK_STATUS_OUTCOME_UNKNOWN,
                                   metadata={**self._runtime.records[task_id].metadata, "error": message})
                try:
                    observed = self._owned_change(task_id, status=TASK_STATUS_OUTCOME_UNKNOWN,
                                                  metadata={"error": message})
                except (OSError, ValueError) as persistence:
                    observed = replace(observed, metadata={**observed.metadata, "status_persisted": "false",
                                       "error": self._runtime.policy.text(f"{message}; status save failed: {persistence}")})
                    self._runtime.local_failures[task_id] = observed
                self._runtime.records[task_id] = observed
                self._runtime.monitors.pop(task_id, None)
                self._runtime.stopping.discard(task_id)
                if process.returncode is not None:
                    self._runtime.processes.pop(task_id, None)
                waiter = self._runtime.waiters.pop(task_id, None)
                if waiter is not None and not waiter.done():
                    waiter.set_result(observed)
                if cancelled:
                    raise asyncio.CancelledError from exc
                return
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
            if task_id in self._runtime.stopping
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
        try:
            observed_metadata = {}
            if diagnostic_error is not None:
                observed_metadata["error"] = diagnostic_error
            if output.truncated:
                observed_metadata["output_truncated"] = "true"
            finalized = self._owned_change(
                task_id, status=final_status, finished_at=finalized.finished_at,
                return_code=return_code, pid=None, metadata=observed_metadata,
            )
        except (OSError, ValueError) as exc:
            detail = self._runtime.policy.text(str(exc))
            finalized = replace(
                finalized, status=TASK_STATUS_FAILED,
                metadata={**finalized.metadata, "status_persisted": "false", "error": self._runtime.policy.text(
                    f"Could not persist task status: {detail}",
                )},
            )
            self._runtime.local_failures[task_id] = finalized
            self._runtime.records[task_id] = finalized
        self._runtime.processes.pop(task_id, None)
        self._runtime.monitors.pop(task_id, None)
        self._runtime.stopping.discard(task_id)
        waiter = self._runtime.waiters.pop(task_id, None)
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
            with contextlib.suppress(Exception, asyncio.CancelledError):
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
