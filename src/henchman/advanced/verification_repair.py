"""Bounded repair observations; persisted reports never authorize more work.

This foundation accepts a trusted, joined repair adapter. The adapter must call
``admit_mutation`` for each deterministic mutation before dispatch. Admission is
not a filesystem sandbox or a replacement for the registry's live authorization.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath, PureWindowsPath
from typing import TYPE_CHECKING, Annotated, Any, Literal
from uuid import uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from henchman.advanced.acceptance_checks import (
    check_input_paths,
    check_spec_digest,
    consistent_check_results,
)
from henchman.advanced.checkpoint_files import WorkspaceFiles
from henchman.advanced.verification_evidence import output_text
from henchman.advanced.verification_inputs import (
    MAX_INPUT_FILE_BYTES,
    capture_inputs_async,
    read_in_worker,
)

if TYPE_CHECKING:
    from henchman.advanced.plans import PlanExecutionService, PlanRecord
    from henchman.utils.evidence_redaction import EvidenceRedactor

MAX_REPAIR_REPORT_BYTES = 128 * 1024
Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
RunIdentity = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")]
PathText = Annotated[str, StringConstraints(min_length=1, max_length=4096)]
Reason = Literal["running", "checks_passed", "attempts_exhausted", "identical_failure_limit",
                 "cancelled", "timeout", "checks_incomplete", "criteria_changed", "authority_changed",
                 "mutation_unavailable", "scope_unavailable", "repair_error", "verification_error",
                 "persistence_error", "credential_sensitive"]
_PYTEST_SUMMARY = re.compile(
    r"^(?:=+\s*)?(?P<counts>(?:\d+ (?:failed|passed|skipped|deselected|xfailed|xpassed|warnings?|errors?)(?:, )?)+|no tests ran)"
    r" in \d+(?:\.\d+)?s(?: \(\d+:\d{2}(?::\d{2})?\))?(?:\s*=+)?(?=\r?$)", re.MULTILINE,
)
_PYTEST_TEMP_RUN = re.compile(r"([\\/]+pytest-of-[^\\/\s'\"<>]+[\\/]+)pytest-\d+([\\/]+)")


def _pytest_failure_text(text: str) -> str:
    """Remove known pytest elapsed-summary and numbered temp-run metadata.

    Assertion values, test identities, filenames and arbitrary command output
    remain significant, including original LF/CRLF framing. This is a bounded
    diagnostic repeat heuristic, not an equivalence proof about failures.
    Original projected diagnostics are retained.
    """
    text = _PYTEST_SUMMARY.sub(lambda match: match["counts"] + " in <elapsed>", text)
    return _PYTEST_TEMP_RUN.sub(lambda match: match[1] + "pytest-<run>" + match[2], text)


def _pytest_check(check: dict[str, Any]) -> bool:
    if check.get("kind") == "pytest":
        return True
    argv = check.get("argv")
    if check.get("kind") != "command" or not isinstance(argv, list) or not argv:
        return False
    executable = re.split(r"[\\/]", argv[0])[-1].lower()
    return executable in {"pytest", "pytest.exe"} or (
        re.fullmatch(r"python(?:\d+(?:\.\d+)*)?(?:\.exe)?", executable) is not None
        and argv[1:3] == ["-m", "pytest"]
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _paths(values: tuple[str, ...]) -> tuple[str, ...]:
    for value in values:
        path = PurePosixPath(value)
        if (not value or "\x00" in value or "\\" in value or path.is_absolute() or PureWindowsPath(value).drive
            or ".." in path.parts or path.as_posix() != value or value == "."):
            raise ValueError("Repair paths must be exact canonical project-relative files")
    if len(values) != len({value.casefold() for value in values}):
        raise ValueError("Repair paths must be distinct")
    return values


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)


class RepairRequest(_Model):
    """Trusted caller scope and limits; never reconstructed from a saved report."""

    plan_id: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.:-]{1,256}$")]
    edit_paths: tuple[PathText, ...] = Field(min_length=1, max_length=64)
    protected_paths: tuple[PathText, ...] = Field(min_length=1, max_length=128)
    max_repairs: int = Field(default=3, ge=0, le=10)
    max_identical_failures: int = Field(default=2, ge=1, le=10)
    timeout_seconds: float = Field(default=120.0, ge=0.01, le=900, allow_inf_nan=False)

    @field_validator("edit_paths", "protected_paths")
    @classmethod
    def validate_paths(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _paths(values)

    @model_validator(mode="after")
    def disjoint(self) -> RepairRequest:
        # A portable explicit scope cannot depend on case-sensitive filesystem
        # behavior. Reject ambiguous aliases even when this host distinguishes them.
        if {path.casefold() for path in self.edit_paths} & {path.casefold() for path in self.protected_paths}:
            raise ValueError("Editable and protected repair paths must be disjoint")
        return self


class RepairObservation(_Model):
    index: int = Field(ge=0, le=10)
    verification_run_id: RunIdentity
    status: Literal["pass", "fail", "incomplete"]
    failure_digest: Digest | None = None
    diagnostics: str = Field(default="", max_length=8192)
    diagnostics_truncated: bool = False

    @model_validator(mode="after")
    def consistent(self) -> RepairObservation:
        if (self.status == "fail") != (self.failure_digest is not None):
            raise ValueError("Invalid repair failure observation")
        return self


class RepairReport(_Model):
    """Bounded historical evidence, separate from current acceptance status."""

    version: Literal[1] = 1
    run_id: RunIdentity
    plan_id: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.:-]{1,256}$")]
    plan_created_at: str = Field(max_length=64)
    spec_digest: Digest
    project_checks_digest: Digest | None
    edit_paths: tuple[PathText, ...] = Field(min_length=1, max_length=64)
    protected_paths: tuple[PathText, ...] = Field(min_length=1, max_length=128)
    criteria_digest: Digest | None = None
    max_repairs: int = Field(ge=0, le=10)
    max_identical_failures: int = Field(ge=1, le=10)
    timeout_seconds: float = Field(ge=0.01, le=900, allow_inf_nan=False)
    repairs_started: int = Field(default=0, ge=0, le=10)
    status: Literal["running", "scoped_pass", "incomplete"] = "running"
    reason: Reason = "running"
    task_verified: Literal[False] = False
    started_at: str = Field(max_length=40)
    updated_at: str = Field(max_length=40)
    observations: tuple[RepairObservation, ...] = Field(default=(), max_length=11)
    error: str = Field(default="", max_length=4096)

    @field_validator("version", "task_verified", mode="before")
    @classmethod
    def strict_constants(cls, value: object, info: Any) -> object:
        if (info.field_name == "version" and (type(value) is not int or value != 1)
            or info.field_name == "task_verified" and (type(value) is not bool or value)):
            raise ValueError("Invalid repair evidence constant")
        return value

    @field_validator("plan_created_at", "started_at", "updated_at")
    @classmethod
    def timestamps(cls, value: str) -> str:
        if datetime.fromisoformat(value).tzinfo is None:
            raise ValueError("Repair timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def consistent(self) -> RepairReport:
        if datetime.fromisoformat(self.updated_at) < datetime.fromisoformat(self.started_at):
            raise ValueError("Repair observation predates its admission")
        if self.repairs_started > self.max_repairs or len(self.observations) > self.repairs_started + 1:
            raise ValueError("Repair observations exceed their admitted budget")
        if any(item.index != index for index, item in enumerate(self.observations)):
            raise ValueError("Repair observation order is invalid")
        if len({item.verification_run_id for item in self.observations}) != len(self.observations):
            raise ValueError("A check observation cannot be replayed as another repair attempt")
        if ((self.status == "running") != (self.reason == "running")
            or (self.status == "scoped_pass") != (self.reason == "checks_passed")):
            raise ValueError("Repair terminal state is inconsistent")
        if self.status == "scoped_pass" and (self.criteria_digest is None or not self.observations
                                             or self.observations[-1].status != "pass"):
            raise ValueError("Repair success requires its final scoped observation")
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def decode_repair_report(payload: object) -> RepairReport:
    """Reject malformed persisted evidence instead of deriving retry authority."""
    try:
        raw = json.dumps(payload, allow_nan=False)
        if len(raw.encode()) > MAX_REPAIR_REPORT_BYTES:
            raise ValueError
        return RepairReport.model_validate_json(raw)
    except (ValueError, TypeError, RecursionError):
        raise ValueError("Repair evidence is invalid or exceeds its bound") from None


def project_repair_report(payload: dict[str, Any] | None, policy: EvidenceRedactor) -> dict[str, Any] | None:
    if payload is None:
        return None
    report = decode_repair_report(payload)
    safe = report.to_dict()
    for key in ("edit_paths", "protected_paths"):
        safe[key] = [policy.text(path) for path in safe[key]]
    if any(safe[key] != payload[key] for key in ("edit_paths", "protected_paths")):
        safe.update(status="incomplete", reason="credential_sensitive")
    for observation in safe["observations"]:
        observation["diagnostics"] = output_text(observation["diagnostics"].encode(),
            truncated=observation["diagnostics_truncated"], policy=policy, limit=8192)
    safe["error"] = output_text(report.error.encode(), truncated=len(report.error) >= 4096, policy=policy, limit=4096)
    return decode_repair_report(safe).to_dict()


@dataclass(frozen=True)
class RepairAttempt:
    repair_index: int
    edit_paths: tuple[str, ...]
    protected_paths: tuple[str, ...]
    observation: RepairObservation


class _Stopped(Exception):
    def __init__(self, reason: Reason, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason


class VerificationRepairSession:
    """One explicitly requested, non-resumable sequence of checks and repairs."""

    def __init__(self, service: PlanExecutionService, request: RepairRequest) -> None:
        self.service = service
        self.request = RepairRequest.model_validate(request.model_dump())
        self.report: RepairReport | None = None
        self._used = False
        self._editing = False
        self._owner: asyncio.Task[Any] | None = None
        self._initial_cancels = 0
        self._workspace: WorkspaceFiles | None = None
        self._criteria: str | None = None
        self._deadline = 0.0
        self._denied: _Stopped | None = None
        self._inputs: tuple[str, ...] = ()

    def _change(self, **values: Any) -> None:
        assert self.report is not None
        updated_at = _now()
        # Wall-clock adjustments cannot invalidate interruption evidence. The
        # independent monotonic deadline continues to control execution.
        if datetime.fromisoformat(updated_at) < datetime.fromisoformat(self.report.updated_at):
            updated_at = self.report.updated_at
        self.report = RepairReport.model_validate({**self.report.model_dump(), **values, "updated_at": updated_at})

    def _save(self, *, start: bool = False) -> None:
        assert self.report is not None
        self.report = decode_repair_report(self.service.save_repair_report(self.request.plan_id, self.report.to_dict(), start=start))

    def _check_cancelled(self) -> None:
        if self._owner is not None and self._owner.cancelling() > self._initial_cancels:
            raise asyncio.CancelledError("Repair cancellation cannot be converted into success")

    def _check_control(self) -> None:
        self._check_cancelled()
        if self._denied is not None:
            raise self._denied
        if time.monotonic() >= self._deadline:
            raise _Stopped("timeout", "Repair deadline reached; inspect retained observations before new work.")

    def _record_failure(self, primary: BaseException, reason: Reason, *, detail: str | None = None) -> None:
        """Best-effort evidence cannot replace the interruption being reported."""
        try:
            safe = self.service._policy.text(str(primary) if detail is None else detail)
            self._change(status="incomplete", reason=reason,
                         error=output_text(safe.encode(), truncated=False, policy=self.service._policy, limit=4096))
            self._save()
        except BaseException:
            primary.add_note("Could not persist repair interruption; inspect repair and verification storage.")

    def _current(self) -> PlanRecord:
        assert self.report is not None
        self._check_control()
        record = self.service._require_plan(self.request.plan_id)
        if any(self.service._policy.text(path) != path for path in (*self.request.edit_paths, *self.request.protected_paths)):
            raise _Stopped("credential_sensitive", "Repair paths became credential-sensitive; explicit review is required.")
        if (record.created_at != self.report.plan_created_at or record.checks_unavailable is not None
            or check_spec_digest(record.checks) != self.report.spec_digest
            or record.project_checks_digest != self.report.project_checks_digest
            or self.service._configuration_status(record) != "current"
            or (record.last_repair or {}).get("run_id") != self.report.run_id
            or (record.last_repair or {}).get("status") != "running"):
            raise _Stopped("authority_changed", "Repair plan, required checks or run ownership changed; explicitly review a new request.")
        if self._workspace is not None:
            try:
                self._workspace.check_root()
            except (OSError, ValueError):
                raise _Stopped("authority_changed", "Repair project or worktree identity changed.") from None
        self._check_control()
        return record

    async def _inspect(self, *, initial: bool = False) -> str:
        self._current()
        paths = tuple(dict.fromkeys((*self.request.protected_paths, *self._inputs)))
        observed = await capture_inputs_async(self.service._project_root, paths, redactor=self.service._policy)
        self._current()
        if observed.get("status") != "available":
            raise _Stopped("scope_unavailable", "Repair requires supported, non-excluded regular text files or explicit editable absence.")
        files = observed["files"]
        if any(files[path]["status"] != "text" for path in self.request.protected_paths):
            raise _Stopped("scope_unavailable", "Protected criterion files must exist and be readable text.")
        identity = _digest({"project": observed["project"], "files": {path: files[path] for path in self.request.protected_paths}})
        if initial:
            self._criteria = identity
            self._change(criteria_digest=identity)
            self._save()
            await asyncio.sleep(0)
            self._current()
        elif identity != self._criteria:
            raise _Stopped("criteria_changed", "Protected criterion contents or modes changed; restore or explicitly review the criteria.")
        return str(observed["digest"])

    async def admit_mutation(self, paths: tuple[str, ...] | None) -> None:
        """Validate deterministic targets; the trusted adapter retains dispatch duties."""
        if not self._editing or asyncio.current_task() is not self._owner:
            self._denied = _Stopped("mutation_unavailable", "Repair mutation admission requires its active foreground adapter.")
            raise self._denied
        try:
            if not isinstance(paths, tuple) or not paths or len(paths) > 64 or any(not isinstance(path, str) for path in paths):
                raise ValueError
            _paths(paths)
            if not set(paths).issubset(self.request.edit_paths):
                raise ValueError
        except (ValueError, TypeError):
            self._denied = _Stopped("mutation_unavailable", "Mutation targets are unknown, unsupported, protected or outside the explicit repair scope.")
            raise self._denied from None
        try:
            await self._inspect()
        except _Stopped as refusal:
            self._denied = refusal
            raise

    def _observation(self, report: dict[str, Any], status: dict[str, object]) -> RepairObservation:
        assert self.report is not None
        failed = [item for item in report["results"] if item["passed"] is not True]
        details = [{key: item.get(key) for key in ("index", "status", "returncode", "error", "stdout", "stderr",
                                                   "stdout_truncated", "stderr_truncated")} for item in failed]
        fingerprints = [dict(detail) for detail in details]
        for item, fingerprint in zip(failed, fingerprints, strict=True):
            if _pytest_check(item["check"]):
                for key in ("stdout", "stderr"):
                    if isinstance(fingerprint[key], str):
                        fingerprint[key] = _pytest_failure_text(fingerprint[key])
        raw = json.dumps(details, ensure_ascii=False, sort_keys=True)
        safe = self.service._policy.text(raw)
        disposition: Literal["pass", "fail", "incomplete"] = "pass" if status["current_checks_passed"] is True else "fail" if status["status"] == "fail" else "incomplete"
        return RepairObservation(index=len(self.report.observations), verification_run_id=report["run_id"],
            status=disposition, failure_digest=_digest(fingerprints) if disposition == "fail" else None,
            diagnostics=output_text(safe.encode(), truncated=False, policy=self.service._policy, limit=8192),
            diagnostics_truncated=len(safe.encode()) > 8192)

    async def _verify(self, verify: Callable[[], Awaitable[object]] | None) -> RepairObservation:
        await self._inspect()
        before = (self._current().last_verification or {}).get("run_id")
        owned: object
        if verify is None:
            owned = await self.service.verify_plan(self.request.plan_id)
        else:
            owned = await verify()
        record = self._current()
        report = record.last_verification
        if not isinstance(owned, dict) or report is None or owned.get("run_id") != report.get("run_id"):
            raise _Stopped("authority_changed", "Repair verification did not retain its own persisted observation.")
        if (report is None or report.get("run_id") == before or report.get("status") != "finished"
            or report.get("spec_digest") != self.report.spec_digest  # type: ignore[union-attr]
            or not consistent_check_results(record.checks, report)):
            raise _Stopped("checks_incomplete", "Repair requires a new, persisted observation of its exact checks.")
        inputs_before = await self._inspect()
        status = await read_in_worker(lambda: self.service.verification_status(self.request.plan_id))
        current = self._current()
        if (status.get("run_id") != report.get("run_id")
            or (current.last_verification or {}).get("run_id") != report.get("run_id")):
            raise _Stopped("authority_changed", "Verification was superseded before repair observation.")
        if await self._inspect() != inputs_before:
            raise _Stopped("checks_incomplete", "Declared check inputs changed during final freshness inspection.")
        if (self._current().last_verification or {}).get("run_id") != report.get("run_id"):
            raise _Stopped("authority_changed", "Verification was superseded during final criterion inspection.")
        observation = self._observation(report, status)
        assert self.report is not None
        self._change(observations=(*self.report.observations, observation))
        self._save()
        await asyncio.sleep(0)
        if (self._current().last_verification or {}).get("run_id") != report.get("run_id"):
            raise _Stopped("authority_changed", "Verification was superseded while persisting repair observation.")
        return observation

    async def run(self, repair: Callable[[RepairAttempt], Awaitable[None]], *,
                  verify: Callable[[], Awaitable[object]] | None = None) -> RepairReport:
        """Use one trusted adapter; no provider, recursive public run or replay is created.

        Synchronous persistence may finish after the deadline. Recheck controls
        after acknowledgement before dispatching more work or returning a pass.
        """
        if self._used:
            raise ValueError("Repair session has already been used; explicit new authority is required")
        self._used = True
        self._owner = asyncio.current_task()
        self._initial_cancels = self._owner.cancelling() if self._owner is not None else 0
        try:
            return await self._run(repair, verify=verify)
        finally:
            self._editing = False
            self._owner = None

    async def _run(self, repair: Callable[[RepairAttempt], Awaitable[None]], *,
                   verify: Callable[[], Awaitable[object]] | None) -> RepairReport:
        """Retain foreground control through terminal persistence acknowledgement."""
        record = self.service._require_plan(self.request.plan_id)
        for path in (*self.request.edit_paths, *self.request.protected_paths):
            if self.service._policy.text(path) != path:
                raise ValueError("Repair scope contains credentials; choose credential-free explicit paths")
        now = _now()
        self.report = RepairReport(run_id=uuid4().hex, plan_id=record.plan_id, plan_created_at=record.created_at,
            spec_digest=check_spec_digest(record.checks), project_checks_digest=record.project_checks_digest,
            edit_paths=self.request.edit_paths, protected_paths=self.request.protected_paths,
            max_repairs=self.request.max_repairs, max_identical_failures=self.request.max_identical_failures,
            timeout_seconds=self.request.timeout_seconds, started_at=now, updated_at=now)
        self._deadline = time.monotonic() + self.request.timeout_seconds
        stage: Reason = "persistence_error"
        try:
            self._save(start=True)
            await asyncio.sleep(0)
            self._current()
            async with asyncio.timeout(max(0.0, self._deadline - time.monotonic())):
                stage = "verification_error"
                self._workspace = WorkspaceFiles(self.service._project_root, self.service._policy, MAX_INPUT_FILE_BYTES, ())
                paths, complete = check_input_paths(record.checks)
                if not complete or not set(self.request.edit_paths).issubset(paths):
                    raise _Stopped("checks_incomplete", "Checks must declare every editable input before bounded repair.")
                self._inputs = paths
                # A pytest target itself is a criterion; directories require a
                # separately reviewed explicit-file specification in this slice.
                if any(check.kind == "pytest" and (check.path or "").split("::", 1)[0] not in self.request.protected_paths
                       for check in record.checks):
                    raise _Stopped("scope_unavailable", "Every pytest target must be an explicitly protected criterion file.")
                await self._inspect(initial=True)
                failures: Counter[str] = Counter()
                while True:
                    stage = "verification_error"
                    observation = await self._verify(verify)
                    if observation.status == "pass":
                        self._change(status="scoped_pass", reason="checks_passed")
                        break
                    if observation.status != "fail":
                        raise _Stopped("checks_incomplete", "Required checks are unavailable, stale, unscoped or incomplete; inspect their observations.")
                    assert observation.failure_digest is not None
                    failures[observation.failure_digest] += 1
                    if failures[observation.failure_digest] >= self.request.max_identical_failures:
                        raise _Stopped("identical_failure_limit", "Identical check failures reached the limit; inspect diagnostics before another request.")
                    if self.report.repairs_started >= self.request.max_repairs:
                        raise _Stopped("attempts_exhausted", "Repair attempts are exhausted; the retained check failure remains unresolved.")
                    await self._inspect()
                    self._change(repairs_started=self.report.repairs_started + 1)
                    stage = "persistence_error"
                    self._save()
                    await asyncio.sleep(0)
                    self._current()
                    stage = "repair_error"
                    self._editing = True
                    try:
                        await repair(RepairAttempt(self.report.repairs_started, self.request.edit_paths,
                                                   self.request.protected_paths, observation))
                    finally:
                        self._editing = False
                    await self._inspect()
        except _Stopped as stopped:
            self._change(status="incomplete", reason=stopped.reason, error=str(stopped))
        except TimeoutError:
            self._change(status="incomplete", reason="timeout", error="Repair deadline or owned operation timeout reached; inspect retained evidence.")
        except BaseException as primary:
            reason: Reason = "cancelled" if isinstance(primary, asyncio.CancelledError) else stage
            self._record_failure(primary, reason)
            raise
        finally:
            self._editing = False
        try:
            self._save()
            # Deliver cancellation queued while synchronous storage held the
            # event loop before publishing the acknowledged terminal result.
            await asyncio.sleep(0)
            try:
                if self.report.status == "scoped_pass":
                    self._check_control()
                else:
                    self._check_cancelled()
            except _Stopped as stopped:
                # Terminal evidence may be downgraded to incomplete under the
                # same run/spec CAS; observed checks and consumed attempts stay.
                self._change(status="incomplete", reason=stopped.reason, error=str(stopped))
                self._save()
                await asyncio.sleep(0)
                self._check_cancelled()
        except BaseException as primary:
            reason = "cancelled" if isinstance(primary, asyncio.CancelledError) else "persistence_error"
            self._record_failure(primary, reason, detail="Repair terminal evidence could not be settled; inspect storage.")
            raise
        return self.report
