"""Bounded, explicit acceptance observations for persisted development plans.

These checks describe only their configured assertions. Passing them does not
establish that an entire task is correct or that its requirements are complete.
"""

from __future__ import annotations

import hashlib
import json
import re
import stat
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from functools import partial
from pathlib import Path, PurePosixPath, PureWindowsPath
from tempfile import TemporaryDirectory
from typing import Any

from henchman.advanced.verification_evidence import (
    current_policy,
    evidence_scope,
    output_text,
    project_report,
    refresh_policy,
    require_safe_checks,
)
from henchman.advanced.verification_inputs import (
    MAX_INPUT_FILES,
    capture_inputs_async,
    fingerprint_identity,
    read_in_worker,
)
from henchman.testing.pytest_reporter import PytestEvidence
from henchman.tools.subprocess_utils import run_bounded_subprocess

MAX_CHECKS = 20
MAX_FILE_BYTES = 1024 * 1024
MAX_TEXT_LENGTH = 4096
MAX_ARGV_LENGTH = 64
MAX_ARGV_BYTES = 16 * 1024
MAX_OUTPUT_BYTES = 65536
MAX_CHECK_SPEC_BYTES = 512 * 1024
DEFAULT_TIMEOUT = 60
_KINDS = {
    "file_exists": {"kind", "path"},
    "file_contains": {"kind", "path", "text"},
    "file_changed": {"kind", "path"},
    "command": {"kind", "argv", "expected_exit", "timeout"},
    "pytest": {"kind", "path", "timeout"},
}
_BASELINE_FIELDS = {"baseline_captured", "baseline_sha256", "baseline_error"}
_SCOPE_FIELDS = {"inputs", "requirement_ids"}


@dataclass(frozen=True)
class CheckSpec:
    """Immutable check with an optional internally captured change baseline."""

    kind: str
    path: str | None = None
    text: str | None = None
    argv: tuple[str, ...] = ()
    expected_exit: int = 0
    timeout: int = DEFAULT_TIMEOUT
    baseline_captured: bool = False
    baseline_sha256: str | None = None
    baseline_error: str | None = None
    inputs: tuple[str, ...] = ()
    requirement_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize applicable fields, including persisted change baselines."""
        fields = _KINDS.get(self.kind, {"kind"})
        payload = {key: getattr(self, key) for key in fields}
        if self.kind == "command":
            payload["argv"] = list(self.argv)
        if self.kind == "file_changed":
            payload.update({key: getattr(self, key) for key in _BASELINE_FIELDS})
        if self.inputs:
            payload["inputs"] = list(self.inputs)
        if self.requirement_ids:
            payload["requirement_ids"] = list(self.requirement_ids)
        return payload

    @classmethod
    def from_dict(cls, payload: object) -> CheckSpec:
        """Restore a validated persisted specification, including its baseline."""
        return _parse_spec(payload, persisted=True)


def _validate_path(raw: object, *, pytest_path: bool = False) -> str:
    if not isinstance(raw, str) or not raw.strip() or len(raw) > MAX_TEXT_LENGTH:
        raise ValueError("path must be a nonempty project-relative string")
    path = raw.split("::", 1)[0] if pytest_path else raw
    if not path or "\x00" in raw or "\\" in raw or path.startswith("-"):
        raise ValueError("path must use relative forward-slash file syntax")
    if (
        PurePosixPath(path).is_absolute()
        or PureWindowsPath(path).drive
        or ".." in PurePosixPath(path).parts
    ):
        raise ValueError("path cannot be absolute or contain parent traversal")
    return raw


def _bounded_integer(value: object, name: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer between {low} and {high}")
    return value


def _parse_argv(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_ARGV_LENGTH:
        raise ValueError(f"argv must contain 1..{MAX_ARGV_LENGTH} strings")
    if any(not isinstance(arg, str) or "\x00" in arg for arg in raw):
        raise ValueError("argv must contain strings without NUL bytes")
    if not raw[0].strip():
        raise ValueError("argv must name an executable")
    if sum(len(arg.encode("utf-8")) for arg in raw) > MAX_ARGV_BYTES:
        raise ValueError(f"argv exceeds {MAX_ARGV_BYTES} bytes")
    return tuple(raw)


def _restore_baseline(spec: CheckSpec, payload: dict[str, Any]) -> CheckSpec:
    captured = payload.get("baseline_captured", False)
    fingerprint = payload.get("baseline_sha256")
    error = payload.get("baseline_error")
    if type(captured) is not bool:
        raise ValueError("baseline_captured must be a boolean")
    if fingerprint is not None and (
        not isinstance(fingerprint, str)
        or len(fingerprint) != 64
        or any(char not in "0123456789abcdef" for char in fingerprint)
    ):
        raise ValueError("baseline_sha256 must be a SHA-256 hexadecimal digest")
    if error is not None and (
        not isinstance(error, str) or len(error) > MAX_TEXT_LENGTH
    ):
        raise ValueError("baseline_error must be bounded text")
    if not captured and (fingerprint is not None or error is not None):
        raise ValueError("uncaptured baseline cannot contain evidence")
    return replace(
        spec,
        baseline_captured=captured,
        baseline_sha256=fingerprint,
        baseline_error=error,
    )


def _parse_spec(payload: object, *, persisted: bool = False) -> CheckSpec:
    if not isinstance(payload, dict) or not isinstance(payload.get("kind"), str):
        raise ValueError("each check must be an object with a kind")
    kind = payload["kind"]
    if kind not in _KINDS:
        raise ValueError(f"unsupported check kind: {kind}")
    allowed = _KINDS[kind] | _SCOPE_FIELDS | (
        _BASELINE_FIELDS if persisted and kind == "file_changed" else set()
    )
    if payload.keys() - allowed:
        raise ValueError(
            "check contains unsupported or caller-supplied evidence fields"
        )
    path = None
    if kind != "command":
        path = _validate_path(payload.get("path"), pytest_path=kind == "pytest")
    text = payload.get("text")
    if kind == "file_contains" and (
        not isinstance(text, str) or not text or len(text) > MAX_TEXT_LENGTH
    ):
        raise ValueError(f"text must contain 1..{MAX_TEXT_LENGTH} characters")
    spec = CheckSpec(
        kind=kind,
        path=path,
        text=text,
        argv=_parse_argv(payload.get("argv")) if kind == "command" else (),
        expected_exit=_bounded_integer(
            payload.get("expected_exit", 0),
            "expected_exit",
            -(2**31),
            2**31 - 1,
        ),
        timeout=_bounded_integer(
            payload.get("timeout", DEFAULT_TIMEOUT), "timeout", 1, 300
        ),
        inputs=_parse_inputs(payload["inputs"]) if "inputs" in payload else (),
        requirement_ids=_parse_requirement_ids(payload.get("requirement_ids", [])),
    )
    return _restore_baseline(spec, payload) if persisted else spec


def _parse_inputs(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_INPUT_FILES:
        raise ValueError("inputs must contain 1..256 explicit project-relative files")
    paths = tuple(PurePosixPath(_validate_path(path)).as_posix() for path in raw)
    if "." in paths or len(set(paths)) != len(paths):
        raise ValueError("inputs must contain distinct explicit files")
    return paths


def _parse_requirement_ids(raw: object) -> tuple[str, ...]:
    if (not isinstance(raw, list) or len(raw) > 32
        or any(not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,128}", value) for value in raw)
        or len(set(raw)) != len(raw)):
        raise ValueError("requirement_ids must contain at most 32 distinct bounded identifiers")
    return tuple(raw)


def check_input_paths(checks: tuple[CheckSpec, ...]) -> tuple[tuple[str, ...], bool]:
    """Return declared input coverage; command/test dependencies are never inferred."""
    paths: set[str] = set()
    complete = True
    for spec in checks:
        paths.update(spec.inputs)
        if spec.kind.startswith("file_") and spec.path is not None:
            paths.add(PurePosixPath(spec.path).as_posix())
        elif not spec.inputs:
            complete = False
    return tuple(sorted(paths)), complete and bool(paths) and len(paths) <= MAX_INPUT_FILES


def check_spec_digest(checks: tuple[CheckSpec, ...]) -> str:
    """Bind observations to the exact immutable configured assertions."""
    return hashlib.sha256(json.dumps([spec.to_dict() for spec in checks], sort_keys=True,
                                    separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def consistent_check_results(checks: tuple[CheckSpec, ...], report: dict[str, object]) -> bool:
    """Reject contradictory or incomplete observations before claiming current proof."""
    results = report.get("results")
    if type(report.get("checks_passed")) is not bool or not isinstance(results, list) or len(results) != len(checks):
        return False
    for index, (spec, result) in enumerate(zip(checks, results, strict=True)):
        if (not isinstance(result, dict) or type(result.get("index")) is not int or result["index"] != index
            or result.get("check") != spec.to_dict() or type(result.get("passed")) is not bool
            or result.get("status") not in {"pass", "fail", "not_run", "error", "timeout"}
            or result["passed"] != (result["status"] == "pass")):
            return False
        if spec.kind in {"file_contains", "file_changed"} and result["passed"]:
            digest = result.get("sha256")
            if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
                return False
        if report.get("freshness") == "current" and spec.kind in {"file_contains", "file_changed"} and "sha256" in result:
            evidence = report.get("input_evidence")
            final = evidence.get("after") if isinstance(evidence, dict) else None
            files = final.get("files") if isinstance(final, dict) else None
            observed = files.get(PurePosixPath(spec.path or "").as_posix()) if isinstance(files, dict) else None
            if not isinstance(observed, dict) or observed.get("sha256") != result["sha256"]:
                return False
    passed = all(result["passed"] for result in results)
    return report["checks_passed"] == (passed and report.get("freshness") != "stale")


def parse_checks(raw: object) -> tuple[CheckSpec, ...]:
    """Validate caller assertions; callers cannot supply baseline or provenance."""
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_CHECKS:
        raise ValueError(f"checks must contain 1..{MAX_CHECKS} check objects")
    result = tuple(_parse_spec(payload) for payload in raw)
    _check_spec_size(result)
    return result


def _check_spec_size(checks: tuple[CheckSpec, ...]) -> None:
    if len(json.dumps([spec.to_dict() for spec in checks], ensure_ascii=True).encode()) > MAX_CHECK_SPEC_BYTES:
        raise ValueError("Acceptance check specifications exceed the 512 KiB limit")


def _checked_specs(checks: tuple[CheckSpec, ...]) -> tuple[CheckSpec, ...]:
    if not isinstance(checks, tuple) or not 1 <= len(checks) <= MAX_CHECKS:
        raise ValueError(f"checks must contain 1..{MAX_CHECKS} specifications")
    if any(not isinstance(spec, CheckSpec) for spec in checks):
        raise ValueError("checks must contain CheckSpec instances")
    result = tuple(CheckSpec.from_dict(spec.to_dict()) for spec in checks)
    _check_spec_size(result)
    return result


def _project_root(root: Path) -> Path:
    resolved = root.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("project root must be a directory")
    return resolved


def _resolve_path(root: Path, spec: CheckSpec) -> Path:
    raw = _validate_path(spec.path, pytest_path=spec.kind == "pytest")
    relative = raw.split("::", 1)[0] if spec.kind == "pytest" else raw
    try:
        target = (root / relative).resolve()
    except RuntimeError as exc:
        # Python 3.12 reports symlink cycles as RuntimeError rather than OSError.
        raise ValueError(f"cannot resolve check path: {exc}") from exc
    if not target.is_relative_to(root):
        raise ValueError("check path escapes the project through a symlink")
    return target


def _read_file(path: Path) -> bytes:
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError("check target is not a regular file")
    if metadata.st_size > MAX_FILE_BYTES:
        raise ValueError(f"file exceeds {MAX_FILE_BYTES}-byte read limit")
    with path.open("rb") as handle:
        data = handle.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"file exceeds {MAX_FILE_BYTES}-byte read limit")
    return data


def prepare_checks(root: Path, checks: tuple[CheckSpec, ...]) -> tuple[CheckSpec, ...]:
    """Capture file-change baselines from the project, never from model claims."""
    root = _project_root(root)
    policy = current_policy()
    refresh_policy(root, policy)
    prepared = []
    for spec in _checked_specs(checks):
        if spec.kind != "file_changed":
            prepared.append(spec)
            continue
        fingerprint = error = None
        try:
            fingerprint = hashlib.sha256(
                _read_file(_resolve_path(root, spec))
            ).hexdigest()
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as exc:
            error = output_text(str(exc).encode(), truncated=False, policy=policy, limit=MAX_TEXT_LENGTH)
        prepared.append(
            replace(
                spec,
                baseline_captured=True,
                baseline_sha256=fingerprint,
                baseline_error=error,
            )
        )
    result = tuple(prepared)
    _check_spec_size(result)
    return result


def _file_result(root: Path, spec: CheckSpec) -> dict[str, Any]:
    path = _resolve_path(root, spec)
    if spec.kind == "file_exists":
        metadata = path.stat()
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("check target is not a regular file")
        return {
            "passed": True,
            "size_bytes": metadata.st_size,
            "mtime_ns": metadata.st_mtime_ns,
        }
    data = _read_file(path)
    fingerprint = hashlib.sha256(data).hexdigest()
    if spec.kind == "file_contains":
        passed = spec.text in data.decode("utf-8") if spec.text is not None else False
        error = None if passed else "required literal text was not found"
    else:
        if not spec.baseline_captured:
            raise ValueError("file_changed requires a captured baseline")
        if spec.baseline_error is not None:
            raise ValueError(f"baseline unavailable: {spec.baseline_error}")
        passed = fingerprint != spec.baseline_sha256
        error = None if passed else "file content has not changed from its baseline"
    return {
        "passed": passed,
        "sha256": fingerprint,
        "size_bytes": len(data),
        "error": error,
    }


async def _command_result(root: Path, spec: CheckSpec) -> dict[str, Any]:
    process = await run_bounded_subprocess(
        list(spec.argv),
        cwd=root,
        timeout=spec.timeout,
        max_output_bytes=MAX_OUTPUT_BYTES,
    )
    passed = process.returncode == spec.expected_exit
    return {
        "passed": passed,
        "returncode": process.returncode,
        "stdout": output_text(process.stdout, truncated=process.stdout_truncated, policy=current_policy(), limit=MAX_OUTPUT_BYTES),
        "stderr": output_text(process.stderr, truncated=process.stderr_truncated, policy=current_policy(), limit=MAX_OUTPUT_BYTES),
        "stdout_truncated": process.stdout_truncated,
        "stderr_truncated": process.stderr_truncated,
        "error": None
        if passed
        else f"expected exit {spec.expected_exit}, got {process.returncode}",
    }


async def _pytest_result(root: Path, spec: CheckSpec) -> dict[str, Any]:
    # Builtin registration imports plan services; defer this reverse dependency.
    from henchman.tools.builtins.pytest_run import (
        PytestConfig,
        _build_pytest_args,
        _verification_error,
    )

    _resolve_path(root, spec)
    with TemporaryDirectory(prefix="henchman-acceptance-") as report_dir:
        report_path = Path(report_dir) / "session.json"
        command = _build_pytest_args(
            PytestConfig(path=spec.path or ".", timeout=spec.timeout),
            report_path,
        )
        result = await _command_result(root, replace(spec, argv=tuple(command)))
        evidence = None
        if report_path.exists():
            evidence = PytestEvidence.from_dict(json.loads(_read_file(report_path)))
        error = _verification_error(evidence, collect_only=False)
        result["evidence"] = asdict(evidence) if evidence is not None else None
        if error is not None:
            result.update(passed=False, error=error)
        return result


async def run_checks(root: Path, checks: tuple[CheckSpec, ...]) -> dict[str, object]:
    """Run sequential bounded checks and report observations without certification."""
    policy = current_policy()
    refresh_policy(root, policy)
    with evidence_scope(policy):
        result = await _run_checks(root, checks)
    projected = project_report(result, policy)
    assert projected is not None
    return projected


async def _run_checks(root: Path, checks: tuple[CheckSpec, ...]) -> dict[str, object]:
    root = _project_root(root)
    specs = _checked_specs(checks)
    policy = current_policy()
    require_safe_checks(specs, policy)
    digest = check_spec_digest(specs)
    paths, complete = check_input_paths(specs)
    before = await capture_inputs_async(root, paths, redactor=policy)
    results = []
    observations = []
    for index, spec in enumerate(specs):
        refresh_policy(root, policy)
        check_before = await capture_inputs_async(root, paths, redactor=policy)
        refresh_policy(root, policy)
        require_safe_checks(specs, policy)
        started_at = datetime.now(UTC).isoformat()
        try:
            if spec.kind == "command":
                result = await _command_result(root, spec)
            elif spec.kind == "pytest":
                result = await _pytest_result(root, spec)
            else:
                result = await read_in_worker(partial(_file_result, root, spec))
        except TimeoutError:
            result = {
                "passed": False,
                "status": "timeout",
                "error": f"check timed out after {spec.timeout}s",
            }
        except (OSError, ValueError) as exc:
            state = "fail" if spec.kind.startswith("file_") and isinstance(exc, FileNotFoundError) else "error"
            if spec.kind in {"command", "pytest"} and isinstance(exc, FileNotFoundError):
                state = "not_run"
            result = {"passed": False, "status": state, "error": policy.text(str(exc))[:MAX_TEXT_LENGTH]}
        result.setdefault("status", "pass" if result["passed"] else "fail")
        check_after = await capture_inputs_async(root, paths, redactor=policy)
        observations.append({"before": fingerprint_identity(check_before), "after": fingerprint_identity(check_after)})
        results.append(
            {
                "index": index,
                "check": spec.to_dict(),
                "started_at": started_at,
                "checked_at": datetime.now(UTC).isoformat(),
                **result,
            }
        )
    after = await capture_inputs_async(root, paths, redactor=policy)
    snapshots = [fingerprint_identity(before), fingerprint_identity(after),
                 *(item[phase] for item in observations for phase in ("before", "after"))]
    available = all(snapshot["status"] == "available" for snapshot in snapshots)
    changed = any(snapshot != fingerprint_identity(after) for snapshot in snapshots)
    # Bind file assertions to the actual bytes they inspected as well as the
    # surrounding observations; a concurrently replaced file cannot borrow proof.
    for spec, result in zip(specs, results, strict=True):
        if spec.kind in {"file_contains", "file_changed"} and "sha256" in result and available:
            observed = after["files"][PurePosixPath(spec.path or "").as_posix()]
            changed |= result["sha256"] != observed["sha256"]
    freshness = "stale" if available and changed else "current" if available and complete else "unverified"
    passed = all(result["passed"] for result in results)
    return {
        "checks_passed": passed and freshness != "stale",
        "current_checks_passed": passed and freshness == "current",
        "freshness": freshness,
        "input_evidence": {"version": 1, "paths": list(paths), "complete": complete, "before": fingerprint_identity(before), "after": after,
                           "observations": observations},
        "task_verified": False,
        "checked_at": datetime.now(UTC).isoformat(),
        "spec_digest": digest,
        "results": results,
        "scope": (
            "Only these configured checks were evaluated; "
            "whole-task correctness is unverified."
        ),
    }
