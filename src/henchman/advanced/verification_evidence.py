"""Safe verification evidence, kept separate from executable assertions."""

from __future__ import annotations

import codecs
import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from henchman.utils.evidence_redaction import EvidenceRedactor, EvidenceStreamRedactor

if TYPE_CHECKING:
    from henchman.advanced.acceptance_checks import CheckSpec
    from henchman.advanced.plans import PlanRecord

UNAVAILABLE = "Verification checks are unavailable because they contain credentials; create a new plan using environment references instead of literal credentials."
_FILES = object()
_ERROR = object()
_POLICY: ContextVar[EvidenceRedactor | None] = ContextVar("verification_evidence_policy", default=None)


def _hash(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _identity(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{32}", value) is not None


def _time(value: object) -> bool:
    if not isinstance(value, str) or not 10 <= len(value) <= 40:
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


_CHECK: dict[str, Any] = dict.fromkeys(("path", "text", "argv", "expected_exit", "timeout", "baseline_captured", "baseline_error", "inputs", "requirement_ids"))
_CHECK.update(kind=lambda value: value in {"command", "pytest", "file_exists", "file_contains", "file_changed"},
              baseline_sha256=_hash, baseline_error=_ERROR)
_FILE = {"status": lambda value: value in {"text", "missing"}, "mode": None, "sha256": _hash}
_SNAPSHOT = {"status": lambda value: value in {"available", "unavailable"}, "digest": _hash,
             "reason": None, "project": None, "files": _FILES}
_INPUT = {"version": None, "paths": None, "complete": None, "before": _SNAPSHOT,
          "after": _SNAPSHOT, "observations": [{"before": _SNAPSHOT, "after": _SNAPSHOT}]}
_RESULT: dict[str, Any] = dict.fromkeys(("index", "passed", "size_bytes", "mtime_ns", "error", "stdout", "stderr", "returncode", "stdout_truncated", "stderr_truncated"))
_RESULT.update(check=_CHECK, sha256=_hash, started_at=_time, checked_at=_time,
               status=lambda value: value in {"pass", "fail", "not_run", "timeout", "error"},
               evidence=dict.fromkeys(("collect_only", "collected", "executed", "passed", "failed", "skipped", "exit_status")))
_REPORT: dict[str, Any] = dict.fromkeys(("checks_passed", "current_checks_passed", "task_verified", "scope", "error", "proof_unavailable_reason"))
_REPORT.update(run_id=_identity, observed_run_id=_identity, spec_digest=_hash, checked_at=_time,
               invalidated_at=_time, invalidation_reason=lambda value: value == "checkpoint_restore",
               status=lambda value: value in {"running", "finished", "cancelled", "error", "stale"},
               freshness=lambda value: value in {"current", "stale", "unverified"},
               input_evidence=_INPUT, results=[_RESULT])


def current_policy() -> EvidenceRedactor:
    """Read this verification's shared policy, or an isolated direct-call policy."""
    return _POLICY.get() or EvidenceRedactor()


def refresh_policy(root: Path, policy: EvidenceRedactor) -> None:
    """Learn current project/global credentials without forgetting old values."""
    from henchman.config.repository import SettingsRepository

    policy.register_policy(SettingsRepository(root).evidence_redactor())


@contextmanager
def evidence_scope(policy: EvidenceRedactor) -> Iterator[None]:
    """Keep a shared policy on this coroutine's owned verification stack."""
    token = _POLICY.set(policy)
    try:
        yield
    finally:
        _POLICY.reset(token)


def _project(value: Any, policy: EvidenceRedactor, schema: Any = None) -> Any:
    if schema is _ERROR:
        return _error_text(value, policy) if isinstance(value, str) else policy.redact(value)
    if schema is _FILES and isinstance(value, dict):
        return {policy.text(str(key)): _project(item, policy, _FILE) for key, item in value.items()}
    if callable(schema):
        return value if isinstance(value, str) and schema(value) else policy.redact(value)
    if isinstance(value, dict) and isinstance(schema, dict):
        return {key if key in schema else policy.text(str(key)): _project(item, policy, schema.get(key))
                for key, item in value.items()}
    if isinstance(value, list) and isinstance(schema, list):
        return [_project(item, policy, schema[0]) for item in value]
    return policy.redact(value)


def checks_sensitive(checks: tuple[CheckSpec, ...], policy: EvidenceRedactor) -> bool:
    """Detect changes to executable assertions without producing substitutes."""
    return any(_project(check.to_dict(), policy, _CHECK) != check.to_dict() for check in checks)


def require_safe_checks(checks: tuple[CheckSpec, ...], policy: EvidenceRedactor) -> None:
    """Fail before dispatch or storage instead of executing projected assertions."""
    if checks_sensitive(checks, policy):
        raise ValueError(UNAVAILABLE)


def output_text(raw: bytes, *, truncated: bool, policy: EvidenceRedactor, limit: int) -> str:
    """Mask a captured prefix, including secrets cut inside a UTF-8 character."""
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    stream = EvidenceStreamRedactor(policy)
    safe = stream.feed(decoder.decode(raw, final=not truncated)) + stream.finish(interrupted=truncated)
    return safe.encode("utf-8")[:limit].decode("utf-8", errors="ignore")


def _error_text(value: str, policy: EvidenceRedactor) -> str:
    # Legacy or previously captured errors at the boundary may end in a secret
    # prefix learned only after capture. Treat that boundary conservatively.
    return output_text(value.encode(), truncated=len(value) >= 4096, policy=policy, limit=4096)


def project_report(report: dict[str, Any] | None, policy: EvidenceRedactor) -> dict[str, Any] | None:
    """Project bounded observation text while retaining validated proof identities."""
    if report is None:
        return None
    projected: dict[str, Any] = _project(report, policy, _REPORT)
    original_results = report.get("results")
    results = projected.get("results")
    changed_proof = projected.get("input_evidence") != report.get("input_evidence")
    changed_proof |= any(projected.get(key) != report.get(key) for key in (
        "run_id", "observed_run_id", "spec_digest", "checked_at",
    ))
    if isinstance(results, list) and isinstance(original_results, list):
        for original, result in zip(original_results, results, strict=True):
            if not isinstance(result, dict) or not isinstance(original, dict):
                continue
            changed_proof |= result.get("check") != original.get("check")
            for key in ("stdout", "stderr"):
                value = original.get(key)
                if isinstance(value, str):
                    result[key] = output_text(value.encode(), truncated=original.get(key + "_truncated") is True,
                                              policy=policy, limit=65536)
            if isinstance(original.get("error"), str):
                result["error"] = _error_text(original["error"], policy)
    if changed_proof:
        projected.pop("input_evidence", None)
        projected.update(freshness="unverified", current_checks_passed=False,
                         proof_unavailable_reason="credential_redaction")
    if isinstance(report.get("error"), str):
        projected["error"] = _error_text(report["error"], policy)
    return projected


def project_record(record: PlanRecord, policy: EvidenceRedactor) -> PlanRecord:
    """Project a read/write snapshot and revoke credential-bearing replay."""
    from henchman.advanced.acceptance_checks import check_spec_digest

    # Keep the legacy serializer permissive, but exempt only validated identity
    # fields at the actual display/persistence boundary.
    canonical = re.fullmatch(r"plan-[0-9a-f]{12}", record.plan_id) is not None
    if not canonical and (re.fullmatch(r"[A-Za-z0-9_.:-]{1,256}", record.plan_id) is None
                          or policy.text(record.plan_id) != record.plan_id):
        raise ValueError("Invalid or credential-bearing persisted plan identity.")
    for timestamp in (record.created_at, record.updated_at, *(step.completed_at for step in record.steps)):
        if timestamp not in (None, "") and not _time(timestamp):
            raise ValueError("Invalid persisted plan timestamp.")
    unavailable = record.checks_unavailable
    checks = record.checks
    if checks_sensitive(checks, policy):
        unavailable = {"reason": "credential_sensitive", "spec_digest": check_spec_digest(checks)}
        checks = ()
    report = project_report(record.last_verification, policy)
    if unavailable is not None and report is not None:
        report.pop("input_evidence", None)
        report.update(freshness="unverified", current_checks_passed=False, proof_unavailable_reason="credential_redaction")
    return replace(record, checks=checks, checks_unavailable=unavailable, last_verification=report,
                   title=policy.text(record.title), steps=tuple(replace(
                       step, text=policy.text(step.text), evidence=policy.text(step.evidence) if step.evidence is not None else None,
                   ) for step in record.steps))
