"""Project-local plan execution verification services."""

from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from henchman.advanced.acceptance_checks import CheckSpec, parse_checks, prepare_checks, run_checks
from henchman.config.paths import resolve_project_settings_path
from henchman.utils.file_lock import FileLock

_STEP_PREFIX_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+")


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""

    return datetime.now(UTC).isoformat()


def _read_json(path: Path, *, default: object) -> object:
    """Read one JSON payload or return *default* when absent."""

    if not path.exists():
        return default
    with path.open("rb") as source:
        raw = source.read(16 * 1024 * 1024 + 1)
    if len(raw) > 16 * 1024 * 1024:
        raise ValueError("Plan storage exceeds the 16 MiB limit.")
    return json.loads(raw)


def _write_json(path: Path, payload: object) -> None:
    """Atomically replace a bounded JSON index in the same directory."""
    raw = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    if len(raw) > 16 * 1024 * 1024:
        raise ValueError("Plan storage exceeds the 16 MiB limit.")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as target:
            temporary = target.name
            target.write(raw)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


def _normalize_steps(steps: list[str] | tuple[str, ...] | None, plan: str | None = None) -> tuple[str, ...]:
    """Return a normalized tuple of non-empty plan steps."""

    if steps and any(not isinstance(step, str) for step in steps):
        raise ValueError("Plan steps must be strings.")
    if steps:
        normalized = tuple(step.strip() for step in steps if step.strip())
        if normalized:
            return normalized
    if isinstance(plan, str) and plan.strip():
        parsed = tuple(
            _STEP_PREFIX_RE.sub("", line).strip()
            for line in plan.splitlines()
            if _STEP_PREFIX_RE.match(line) and _STEP_PREFIX_RE.sub("", line).strip()
        )
        if parsed:
            return parsed
    return ()


@dataclass(frozen=True, slots=True)
class PlanStepRecord:
    """One tracked verification step."""

    index: int
    text: str
    done: bool
    evidence: str | None
    completed_at: str | None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "index": self.index,
            "text": self.text,
            "done": self.done,
            "evidence": self.evidence,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> PlanStepRecord:
        """Create one step record from persisted data."""

        if not isinstance(payload.get("done", False), bool):
            raise ValueError("Persisted step done must be a boolean.")
        raw_index = payload.get("index", 0)
        return cls(
            index=int(raw_index) if isinstance(raw_index, int | str) else 0,
            text=str(payload.get("text", "")),
            done=bool(payload.get("done", False)),
            evidence=str(payload["evidence"]) if payload.get("evidence") is not None else None,
            completed_at=(
                str(payload["completed_at"]) if payload.get("completed_at") is not None else None
            ),
        )


@dataclass(frozen=True, slots=True)
class PlanRecord:
    """Tracked plan verification record."""

    plan_id: str
    title: str
    created_at: str
    updated_at: str
    steps: tuple[PlanStepRecord, ...]
    checks: tuple[CheckSpec, ...] = ()
    last_verification: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "plan_id": self.plan_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "steps": [step.to_dict() for step in self.steps],
            "checks": [check.to_dict() for check in self.checks],
            "last_verification": self.last_verification,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> PlanRecord:
        """Create a plan record from persisted data."""

        raw_checks = payload.get("checks", [])
        if not isinstance(raw_checks, list) or len(raw_checks) > 20:
            raise ValueError("Invalid persisted acceptance checks.")
        if any(not isinstance(check, dict) for check in raw_checks):
            raise ValueError("Invalid persisted acceptance check.")
        report = payload.get("last_verification")
        if report is not None and not isinstance(report, dict):
            raise ValueError("Invalid persisted verification report.")
        raw_steps = payload.get("steps", [])
        steps = (
            tuple(PlanStepRecord.from_dict(step) for step in raw_steps if isinstance(step, dict))
            if isinstance(raw_steps, list)
            else ()
        )
        return cls(
            plan_id=str(payload.get("plan_id", "")),
            title=str(payload.get("title", "")),
            created_at=str(payload.get("created_at", "")),
            updated_at=str(payload.get("updated_at", "")),
            steps=steps,
            checks=tuple(CheckSpec.from_dict(check) for check in raw_checks),
            last_verification=report,
        )


class PlanExecutionService:
    """Manage project-local plan verification records."""

    def __init__(self, project_root: Path | None = None) -> None:
        """Initialize the plan execution service for one project root."""

        self._project_root = (project_root or Path.cwd()).resolve()
        self._storage_dir = resolve_project_settings_path(self._project_root) / "plans"
        self._index_path = self._storage_dir / "verification.json"
        self._lock_path = self._storage_dir / "verification.lock"
        self._records: dict[str, PlanRecord] = {}

    def create_plan(
        self,
        *,
        title: str | None = None,
        steps: list[str] | tuple[str, ...] | None = None,
        plan: str | None = None,
        checks: object = None,
    ) -> PlanRecord:
        """Create one tracked plan verification record."""

        normalized_steps = _normalize_steps(steps, plan)
        if not normalized_steps:
            msg = "At least one plan step is required."
            raise ValueError(msg)
        now = _now_iso()
        record = PlanRecord(
            plan_id=f"plan-{uuid4().hex[:12]}",
            title=title.strip() if isinstance(title, str) and title.strip() else "plan",
            created_at=now,
            updated_at=now,
            checks=prepare_checks(self._project_root, parse_checks(checks)) if checks is not None else (),
            steps=tuple(
                PlanStepRecord(
                    index=index,
                    text=text,
                    done=False,
                    evidence=None,
                    completed_at=None,
                )
                for index, text in enumerate(normalized_steps, start=1)
            ),
        )
        with FileLock(self._lock_path):
            self._records = self._load_records()
            self._records[record.plan_id] = record
            self._persist_records()
        return record

    def list_plans(self) -> list[PlanRecord]:
        """Return all tracked plan records."""

        self._records = self._load_records()
        return sorted(self._records.values(), key=lambda record: record.created_at)

    def get_plan(self, plan_id: str) -> PlanRecord | None:
        """Return one plan record when present."""

        self._records = self._load_records()
        return self._records.get(plan_id)

    def next_step(self, plan_id: str) -> PlanStepRecord | None:
        """Return the next pending step for one plan."""

        record = self._require_plan(plan_id)
        return next((step for step in record.steps if not step.done), None)

    def complete_step(
        self,
        plan_id: str,
        *,
        step: int,
        evidence: str | None = None,
    ) -> PlanRecord:
        """Mark the next pending plan step as complete."""

        if isinstance(step, bool) or not isinstance(step, int):
            raise ValueError("Step must be an integer.")
        with FileLock(self._lock_path):
            record = self._require_plan(plan_id)
            next_pending = next((item for item in record.steps if not item.done), None)
            if next_pending is None:
                return record
            if next_pending.index != step:
                msg = f"Step {step} is out of order; next pending step is {next_pending.index}."
                raise ValueError(msg)

            updated_steps = tuple(
                replace(
                    current,
                    done=True,
                    evidence=evidence.strip() if isinstance(evidence, str) and evidence.strip() else None,
                    completed_at=_now_iso(),
                )
                if current.index == step
                else current
                for current in record.steps
            )
            updated = replace(record, updated_at=_now_iso(), steps=updated_steps)
            self._records[plan_id] = updated
            self._persist_records()
            return updated

    async def verify_plan(self, plan_id: str) -> dict[str, object]:
        """Run recorded checks and persist historical observations, not task truth."""
        run_id = uuid4().hex
        with FileLock(self._lock_path):
            record = self._require_plan(plan_id)
            if not record.checks:
                raise ValueError("This plan has no acceptance checks.")
            pending: dict[str, object] = {
                "run_id": run_id, "status": "running", "checks_passed": False,
                "task_verified": False, "checked_at": _now_iso(), "results": [],
            }
            self._records[plan_id] = replace(record, last_verification=pending)
            self._persist_records()
        try:
            report = await run_checks(self._project_root, record.checks)
        except (asyncio.CancelledError, Exception) as exc:
            failed = dict(pending, status="cancelled" if isinstance(exc, asyncio.CancelledError)
                          else "error", checked_at=_now_iso(), error=str(exc))
            try:
                self._save_report(plan_id, record.checks, run_id, failed)
            except Exception as persistence_error:
                exc.add_note(f"Could not save verification interruption: {persistence_error}")
                raise exc from persistence_error
            raise
        report = dict(report, run_id=run_id, status="finished", task_verified=False)
        self._save_report(plan_id, record.checks, run_id, report)
        return report

    def _save_report(
        self, plan_id: str, checks: tuple[CheckSpec, ...], run_id: str,
        report: dict[str, object],
    ) -> None:
        """Preserve concurrent step updates and reject superseded observations."""
        with FileLock(self._lock_path):
            current = self._require_plan(plan_id)
            if current.checks != checks or (current.last_verification or {}).get("run_id") != run_id:
                raise ValueError("Verification was superseded or its checks changed; run verify again.")
            self._records[plan_id] = replace(current, updated_at=_now_iso(), last_verification=report)
            self._persist_records()

    def render_status(self, plan_id: str) -> str:
        """Render a readable verification status report."""

        record = self._require_plan(plan_id)
        progress = "\n".join(
            f"[{'done' if step.done else 'pending'}] {step.index}. {step.text}"
            for step in record.steps
        )

        report = record.last_verification
        outcome = (
            f"Historical checks: {report.get('status')}; passed={report.get('checks_passed')}; "
            f"checked_at={report.get('checked_at')}. Re-run verify after changes."
            if report else "Acceptance checks have not run."
        )
        checks = json.dumps([check.to_dict() for check in record.checks], sort_keys=True)
        return (f"Reported step progress:\n{progress}\nRecorded checks: {checks}\n{outcome}\n"
                "Task verification is not established.")

    def _require_plan(self, plan_id: str) -> PlanRecord:
        """Return one plan record or raise when absent."""

        record = self.get_plan(plan_id)
        if record is None:
            msg = f"Plan {plan_id} not found."
            raise KeyError(msg)
        return record

    def _load_records(self) -> dict[str, PlanRecord]:
        """Load persisted plan records from disk."""

        payload = _read_json(self._index_path, default=[])
        if not isinstance(payload, list):
            raise ValueError("Plan storage must contain a list.")
        records: dict[str, PlanRecord] = {}
        for item in payload:
            if not isinstance(item, dict):
                raise ValueError("Invalid persisted plan record.")
            record = PlanRecord.from_dict(item)
            if not record.plan_id or record.plan_id in records:
                raise ValueError("Missing or duplicate persisted plan identifier.")
            records[record.plan_id] = record
        return records

    def _persist_records(self) -> None:
        """Persist the current plan records to project-local storage."""

        payload = [
            record.to_dict()
            for record in sorted(self._records.values(), key=lambda item: item.created_at)
        ]
        _write_json(self._index_path, payload)
