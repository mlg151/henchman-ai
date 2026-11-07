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
from typing import TYPE_CHECKING
from uuid import uuid4

from henchman.advanced.acceptance_checks import (
    CheckSpec,
    check_input_paths,
    check_spec_digest,
    consistent_check_results,
    parse_checks,
    prepare_checks,
    run_checks,
)
from henchman.advanced.verification_evidence import (
    UNAVAILABLE,
    evidence_scope,
    project_record,
    project_report,
    require_safe_checks,
)
from henchman.advanced.verification_inputs import input_freshness
from henchman.config.paths import resolve_project_settings_path
from henchman.config.repository import SettingsRepository
from henchman.utils.evidence_redaction import EvidenceRedactor
from henchman.utils.file_lock import FileLock

if TYPE_CHECKING:
    from henchman.config.schema import Settings

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
    checks_unavailable: dict[str, str] | None = None
    project_checks_digest: str | None = None
    last_repair: dict[str, object] | None = None

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
            "checks_unavailable": self.checks_unavailable,
            "project_checks_digest": self.project_checks_digest,
            "last_repair": self.last_repair,
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
        repair = payload.get("last_repair")
        if repair is not None:
            from henchman.advanced.verification_repair import decode_repair_report

            repair = decode_repair_report(repair).to_dict()
            if repair["plan_id"] != payload.get("plan_id"):
                raise ValueError("Repair evidence belongs to a different plan.")
        unavailable = payload.get("checks_unavailable")
        project_digest = payload.get("project_checks_digest")
        if project_digest is not None and (not isinstance(project_digest, str)
                                          or re.fullmatch(r"[0-9a-f]{64}", project_digest) is None):
            raise ValueError("Invalid project check configuration digest.")
        if unavailable is not None and (
            not isinstance(unavailable, dict) or set(unavailable) != {"reason", "spec_digest"}
            or unavailable.get("reason") != "credential_sensitive"
            or not isinstance(unavailable.get("spec_digest"), str)
            or re.fullmatch(r"[0-9a-f]{64}", unavailable["spec_digest"]) is None or raw_checks
        ):
            raise ValueError("Invalid unavailable verification checks.")
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
            checks_unavailable=unavailable,
            project_checks_digest=project_digest,
            last_repair=repair,
        )


class PlanExecutionService:
    """Manage project-local plan verification records."""

    def __init__(self, project_root: Path | None = None, *, redactor: EvidenceRedactor | None = None,
                 settings: Settings | None = None) -> None:
        """Initialize the plan execution service for one project root."""

        self._project_root = (project_root or Path.cwd()).resolve()
        self._storage_dir = resolve_project_settings_path(self._project_root) / "plans"
        self._index_path = self._storage_dir / "verification.json"
        self._lock_path = self._storage_dir / "verification.lock"
        self._records: dict[str, PlanRecord] = {}
        self._policy = redactor or EvidenceRedactor()
        self._settings = settings

    def _refresh_policy(self) -> None:
        self._policy.register_policy(SettingsRepository(self._project_root).evidence_redactor())
        self._refresh_runtime_policy()

    def _refresh_runtime_policy(self) -> None:
        """Learn injected credential changes at each verification boundary."""
        if self._settings is not None:
            self._policy.register_config(self._settings.model_dump())

    def _configured_checks(self) -> tuple[CheckSpec, ...]:
        """Read the held runtime settings, or the normal project settings loader."""
        from henchman.config import load_settings

        settings = self._settings if self._settings is not None else load_settings(project_root=self._project_root)
        checks = settings.verification.checks
        return parse_checks(checks) if checks else ()

    def _configuration_status(self, record: PlanRecord) -> str:
        checks = self._configured_checks()
        digest = check_spec_digest(checks) if checks else None
        if digest == record.project_checks_digest:
            recorded = {replace(check, baseline_captured=False, baseline_sha256=None,
                                baseline_error=None) for check in record.checks}
            if not all(check in recorded for check in checks):
                return "unbound"
            return "current"
        return "unbound" if record.project_checks_digest is None else "changed"

    def sanitize_persisted_evidence(self) -> None:
        """Explicitly scrub existing evidence under the normal writer lock.

        Read-only inspection revokes unsafe replay in memory but leaves historical
        bytes untouched until this operation or the next authorized write.
        """
        self._refresh_policy()
        if not self._index_path.exists():
            return
        with FileLock(self._lock_path):
            original = _read_json(self._index_path, default=[])
            self._records = self._load_records()
            if original != [record.to_dict() for record in sorted(self._records.values(), key=lambda item: item.created_at)]:
                self._persist_records()

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
        self._refresh_policy()
        configured = self._configured_checks()
        supplied = parse_checks(checks) if checks is not None else ()
        parsed = tuple(dict.fromkeys((*configured, *supplied)))
        require_safe_checks(parsed, self._policy)
        with evidence_scope(self._policy, refresh=self._refresh_runtime_policy):
            prepared = prepare_checks(self._project_root, parsed) if parsed else ()
        now = _now_iso()
        record = PlanRecord(
            plan_id=f"plan-{uuid4().hex[:12]}",
            title=title.strip() if isinstance(title, str) and title.strip() else "plan",
            created_at=now,
            updated_at=now,
            checks=prepared,
            project_checks_digest=check_spec_digest(configured) if configured else None,
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
            require_safe_checks(record.checks, self._policy)
            record = project_record(record, self._policy)
            self._records[record.plan_id] = record
            self._persist_records(new_plan_id=record.plan_id)
        return self._records[record.plan_id]

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
            return self._records[plan_id]

    async def verify_plan(self, plan_id: str) -> dict[str, object]:
        """Run recorded checks and persist historical observations, not task truth."""
        self.sanitize_persisted_evidence()
        self._assert_no_pending_restore()
        run_id = uuid4().hex
        with FileLock(self._lock_path):
            record = self._require_plan(plan_id)
            if record.checks_unavailable is not None:
                raise ValueError(UNAVAILABLE)
            if self._configuration_status(record) != "current":
                raise ValueError("Project check configuration changed or was never bound; create a new plan and explicitly review its required checks.")
            if not record.checks:
                raise ValueError("This plan has no acceptance checks.")
            pending: dict[str, object] = {
                "run_id": run_id, "status": "running", "checks_passed": False,
                "task_verified": False, "checked_at": _now_iso(), "results": [],
            }
            self._records[plan_id] = replace(record, last_verification=pending)
            self._persist_records()
        report: dict[str, object] = pending
        try:
            with evidence_scope(self._policy, refresh=self._refresh_runtime_policy):
                report = await run_checks(self._project_root, record.checks)
            configuration_status = self._configuration_status(record)
            report = dict(report, run_id=run_id, status="finished", task_verified=False,
                          configuration_status=configuration_status)
            if configuration_status != "current":
                report.update(checks_passed=False, current_checks_passed=False)
        except (asyncio.CancelledError, Exception) as exc:
            failed = dict(report, run_id=run_id,
                          status="cancelled" if isinstance(exc, asyncio.CancelledError) else "error",
                          checks_passed=False, current_checks_passed=False, task_verified=False,
                          checked_at=_now_iso(), error=self._policy.text(str(exc))[:4096])
            try:
                self._save_report(plan_id, record.checks, run_id, failed)
            except Exception:
                exc.add_note("Could not save verification interruption; inspect verification storage.")
                raise exc from None
            raise
        try:
            self._save_report(plan_id, record.checks, run_id, report)
        except Exception as error:
            # A bounded report may outgrow the remaining index capacity. Retain
            # a small terminal failure when possible instead of leaving running
            # authority behind; never rerun the checks to repair persistence.
            failed = dict(pending, status="error", checked_at=_now_iso(),
                          error="Verification results could not be persisted; correct storage before verifying again.")
            try:
                self._save_report(plan_id, record.checks, run_id, failed)
            except Exception:
                error.add_note("Could not save verification persistence failure; inspect verification storage.")
            raise
        safe = project_report(report, self._policy)
        assert safe is not None
        return safe

    def _save_report(
        self, plan_id: str, checks: tuple[CheckSpec, ...], run_id: str,
        report: dict[str, object],
    ) -> None:
        """Preserve concurrent step updates and reject superseded observations."""
        # Acquire checkpoint authority before the plan lock: restores hold their
        # checkpoint lock while invalidating plan observations in this order.
        self._assert_no_pending_restore()
        with FileLock(self._lock_path):
            current = self._require_plan(plan_id)
            if current.checks_unavailable is not None:
                if ((current.last_verification or {}).get("run_id") == run_id
                    and current.checks_unavailable["spec_digest"] == check_spec_digest(checks)):
                    failed = dict(report, status="error", checks_passed=False,
                                  current_checks_passed=False, task_verified=False, error=UNAVAILABLE)
                    self._records[plan_id] = replace(current, updated_at=_now_iso(), last_verification=failed)
                self._persist_records()
                raise ValueError(UNAVAILABLE)
            if current.checks != checks or (current.last_verification or {}).get("run_id") != run_id:
                raise ValueError("Verification was superseded or its checks changed; run verify again.")
            self._records[plan_id] = replace(current, updated_at=_now_iso(), last_verification=report)
            self._persist_records()

    def _assert_no_pending_restore(self) -> None:
        """Refuse observations while a workspace restore is incomplete."""
        from henchman.advanced.checkpoints import CheckpointService

        storage = resolve_project_settings_path(self._project_root) / "tungsten/checkpoints"
        if (storage.exists() or storage.is_symlink()) and CheckpointService(self._project_root).pending_restores():
            raise ValueError("Workspace restore is incomplete; recover it before running verification.")

    def save_repair_report(self, plan_id: str, report: dict[str, object], *, start: bool = False) -> dict[str, object]:
        """Persist bounded advisory repair evidence with exact run/spec ownership.

        Explicitly starting another repair supersedes the older observer. Reading
        this record never returns a permit or resumes a callback.
        """
        from henchman.advanced.verification_repair import (
            decode_repair_report,
            project_repair_report,
        )

        self._assert_no_pending_restore()
        with FileLock(self._lock_path):
            current = self._require_plan(plan_id)
            safe = project_repair_report(report, self._policy)
            assert safe is not None
            incoming = decode_repair_report(safe)
            if incoming.plan_id != plan_id:
                raise ValueError("Repair evidence belongs to a different plan.")
            previous = current.last_repair
            if start:
                if (incoming.status != "running" or incoming.repairs_started or incoming.observations
                    or incoming.criteria_digest is not None or (previous or {}).get("run_id") == incoming.run_id):
                    raise ValueError("A repair must begin without prior execution observations.")
            else:
                if previous is None or previous.get("run_id") != incoming.run_id:
                    raise ValueError("Repair observation was superseded; inspect current state.")
                fixed = ("plan_id", "plan_created_at", "spec_digest", "project_checks_digest", "edit_paths",
                         "protected_paths", "max_repairs", "max_identical_failures", "timeout_seconds", "started_at")
                if any(previous[key] != safe[key] for key in fixed):
                    raise ValueError("Repair scope or budget changed after admission.")
                old = decode_repair_report(previous)
                if (incoming.repairs_started < old.repairs_started or incoming.repairs_started > old.repairs_started + 1
                    or incoming.observations[:len(old.observations)] != old.observations
                    or (old.criteria_digest is not None and incoming.criteria_digest != old.criteria_digest)
                    or (old.status != "running" and incoming.status != "incomplete")):
                    raise ValueError("Repair evidence cannot erase observations or resume terminal authority.")
            if incoming.status != "incomplete" and (
                current.checks_unavailable is not None or not current.checks
                or incoming.plan_created_at != current.created_at or incoming.spec_digest != check_spec_digest(current.checks)
                or incoming.project_checks_digest != current.project_checks_digest
                or self._configuration_status(current) != "current"
            ):
                raise ValueError("Repair plan or required check authority changed.")
            if incoming.status == "scoped_pass":
                observed = current.last_verification
                if (observed is None or observed.get("run_id") != incoming.observations[-1].verification_run_id
                    or observed.get("current_checks_passed") is not True
                    or observed.get("spec_digest") != incoming.spec_digest
                    or not consistent_check_results(current.checks, observed)):
                    raise ValueError("Repair pass lacks its final persisted check observation.")
            self._records[plan_id] = replace(current, updated_at=_now_iso(), last_repair=incoming.to_dict())
            self._persist_records()
            result = self._records[plan_id].last_repair
            assert result is not None
            return result

    def invalidate_checks(self) -> None:
        """Retain observations but revoke their success and running-save authority."""
        if not self._index_path.exists():
            return
        with FileLock(self._lock_path):
            self._records = self._load_records()
            changed = False
            for identity, record in self._records.items():
                if record.last_verification is None:
                    continue
                previous = record.last_verification
                report = dict(previous, status="stale", checks_passed=False, task_verified=False,
                              observed_run_id=previous.get("observed_run_id", previous.get("run_id")),
                              run_id=uuid4().hex, invalidated_at=_now_iso(),
                              invalidation_reason="checkpoint_restore")
                self._records[identity] = replace(record, updated_at=_now_iso(), last_verification=report)
                changed = True
            if changed:
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
        current = self.verification_status(plan_id)
        return (f"Reported step progress:\n{progress}\nRecorded checks: {checks}\n{outcome}\n"
                f"Current declared-input checks: {current['status']}. "
                "Task verification is not established.")

    def verification_status(self, plan_id: str) -> dict[str, object]:
        """Inspect declared-input freshness without changing historical observations.

        A current pass concerns only the configured assertions and explicitly
        declared contents. It does not certify requirement coverage or a task.
        """
        record = self._require_plan(plan_id)
        report = record.last_verification
        requirements = sorted({identity for check in record.checks for identity in check.requirement_ids})
        status = "not_run"
        freshness = "unverified"
        configuration_status = self._configuration_status(record)
        if record.checks_unavailable is not None:
            status = "unavailable"
        elif configuration_status != "current":
            status = "stale" if configuration_status == "changed" else "unverified"
        elif report is not None and report.get("configuration_status") in {"changed", "unbound"}:
            status = "stale"
        elif (report is not None and report.get("status") == "finished"
              and record.project_checks_digest is not None and report.get("configuration_status") != "current"):
            status = "unverified"
        elif report is not None:
            saved_status = report.get("status")
            if saved_status in {"running", "cancelled", "error", "stale"}:
                status = str(saved_status)
            elif saved_status == "finished":
                paths, complete = check_input_paths(record.checks)
                if (report.get("freshness") in {"current", "stale"}
                    and report.get("spec_digest") == check_spec_digest(record.checks)
                    and consistent_check_results(record.checks, report)):
                    freshness = input_freshness(report.get("input_evidence"), root=self._project_root,
                                                paths=paths, complete=complete, count=len(record.checks), redactor=self._policy)
                status = ("pass" if report.get("checks_passed") is True else "fail") if freshness == "current" else freshness
                results = report.get("results")
                if isinstance(results, list) and any(
                    isinstance(result, dict) and result.get("status") in {"not_run", "timeout", "error"}
                    for result in results
                ):
                    status = "incomplete"
            else:
                status = "unverified"
        return {"plan_id": plan_id, "status": status, "freshness": freshness,
                "configuration_status": configuration_status,
                "project_checks_digest": record.project_checks_digest,
                "current_checks_passed": status == "pass", "task_verified": False,
                "run_id": report.get("run_id") if report else None,
                "checked_at": report.get("checked_at") if report else None,
                "spec_digest": record.checks_unavailable["spec_digest"] if record.checks_unavailable else check_spec_digest(record.checks), "requirement_ids": requirements,
                "scope": "Only configured assertions over declared input files; task acceptance is not established."}

    def _require_plan(self, plan_id: str) -> PlanRecord:
        """Return one plan record or raise when absent."""

        record = self.get_plan(plan_id)
        if record is None:
            msg = f"Plan {plan_id} not found."
            raise KeyError(msg)
        return record

    def _load_records(self) -> dict[str, PlanRecord]:
        """Load persisted plan records from disk."""

        self._refresh_policy()
        payload = _read_json(self._index_path, default=[])
        if not isinstance(payload, list):
            raise ValueError("Plan storage must contain a list.")
        records: dict[str, PlanRecord] = {}
        for item in payload:
            if not isinstance(item, dict):
                raise ValueError("Invalid persisted plan record.")
            record = project_record(PlanRecord.from_dict(item), self._policy)
            if not record.plan_id or record.plan_id in records:
                raise ValueError("Missing or duplicate persisted plan identifier.")
            records[record.plan_id] = record
        return records

    def _persist_records(self, *, new_plan_id: str | None = None) -> None:
        """Persist the current plan records to project-local storage."""

        self._refresh_policy()
        if new_plan_id is not None:
            require_safe_checks(self._records[new_plan_id].checks, self._policy)
        self._records = {identity: project_record(record, self._policy) for identity, record in self._records.items()}
        payload = [
            record.to_dict()
            for record in sorted(self._records.values(), key=lambda item: item.created_at)
        ]
        _write_json(self._index_path, payload)
