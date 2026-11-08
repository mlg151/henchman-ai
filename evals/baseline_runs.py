"""Bounded repeat-run baseline runner for the release corpus (#13).

Every run is recorded — successes, verification failures, timeouts, and
runtime errors alike — so reports publish explicit denominators instead of
survivorship-biased success counts. Reports are redacted and written
atomically; local cohorts carry zero-cost provenance and hosted cohorts
never fabricate a cost figure.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import math
import os
import tempfile
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass, fields, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.helpers import EvalTestRig, get_eval_provider
from evals.release_corpus import dispatch_case, get_case, list_cases
from henchman.providers.base import ModelProvider
from henchman.utils.evidence_redaction import EvidenceRedactor

#: Outcomes every run is classified into.
OUTCOMES: tuple[str, ...] = ("success", "verification_failure", "timeout", "runtime_error")

_HOSTED_PROVIDERS = frozenset({"deepseek", "anthropic", "openrouter", "openai", "together", "groq", "fireworks"})


@dataclass(frozen=True)
class RunRecord:
    """One bounded execution of a corpus case; failure runs are records, not losses."""

    case_id: str
    run_index: int
    profile: str
    outcome: str
    duration_ms: float
    tokens_in: int | None
    tokens_out: int | None
    task_verified: bool
    error: str | None


# Protect field names; only validated identities are restored after projection.
_CASE_IDS = tuple(metadata.id for metadata in list_cases())
_OUTCOME_SCHEMA = dict.fromkeys(OUTCOMES)
_CASE_SUMMARY_SCHEMA = {"runs": None, "successes": None, "outcome_counts": _OUTCOME_SCHEMA}
_REPORT_SCHEMA = {
    "kind": None,
    "generated_at": None,
    "cohort": None,
    "requested": {
        "cases": None, "runs_per_case": None, "timeout": None,
        "max_iterations": None, "provider": None, "model": None,
    },
    "budget": {"planned_runs": None, "executed_runs": None},
    "cost": {"source": None, "amount_usd": None, "billing": None},
    "summary": {
        "total_runs": None, "successes": None, "failures": None,
        "outcome_counts": _OUTCOME_SCHEMA,
        "cases": dict.fromkeys(_CASE_IDS, _CASE_SUMMARY_SCHEMA),
        "latency_ms": {"p50": None, "p95": None, "min": None, "max": None},
        "usage": {"tokens_in": None, "tokens_out": None, "available": None},
    },
    "runs": [dict.fromkeys(field.name for field in fields(RunRecord))],
}


def cohort_for_provider(provider_name: str) -> str:
    """Classify a provider as a hosted API cohort or a local/model-server cohort."""
    if provider_name.lower() in _HOSTED_PROVIDERS:
        return "hosted"
    return "local"


def cost_provenance(cohort: str) -> dict[str, Any] | None:
    """Zero-cost provenance for local cohorts; hosted cost is never fabricated here."""
    if cohort == "local":
        return {"source": "local", "amount_usd": 0.0, "billing": "none"}
    return None


def _wall_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000


def _percentile(ordered: list[float], pct: float) -> float:
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct / 100.0
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[int(rank)]
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def _latency(durations: list[float]) -> dict[str, float] | None:
    if not durations:
        return None
    ordered = sorted(durations)
    return {
        "p50": _percentile(ordered, 50),
        "p95": _percentile(ordered, 95),
        "min": ordered[0],
        "max": ordered[-1],
    }


def _sum_known(values: list[int | None]) -> int | None:
    known = [value for value in values if value is not None]
    return sum(known) if known else None


def _classify_failure(rig: EvalTestRig, exc_text: str) -> tuple[str, str]:
    """Map a scenario failure onto timeout / runtime_error / verification_failure."""
    last = rig.last_run_outcome
    if last is None:
        return "runtime_error", exc_text
    success, error = last
    if not success and error is not None:
        if "timed out" in error.lower():
            return "timeout", error
        return "runtime_error", error
    return "verification_failure", exc_text


@contextlib.contextmanager
def _bounded_env(timeout: float, max_iterations: int) -> Iterator[None]:
    """Scope per-run timeout and iteration limits to one dispatch call."""
    previous = {
        "EVAL_TIMEOUT": os.environ.get("EVAL_TIMEOUT"),
        "EVAL_MAX_ITERATIONS": os.environ.get("EVAL_MAX_ITERATIONS"),
    }
    os.environ["EVAL_TIMEOUT"] = str(timeout)
    os.environ["EVAL_MAX_ITERATIONS"] = str(max_iterations)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


async def _run_once(
    case_id: str,
    profile: str,
    provider: ModelProvider,
    run_index: int,
    timeout: float,
    max_iterations: int,
) -> RunRecord:
    rig = EvalTestRig(provider=provider, profile=profile)
    start = time.perf_counter()
    deadline = asyncio.get_running_loop().time() + timeout
    try:
        async with asyncio.timeout_at(deadline):
            rig.setup(f"baseline_{case_id}_{run_index}")
            with _bounded_env(timeout, max_iterations):
                result = await dispatch_case(case_id, rig)
            # Synchronous scenario work or a swallowed cancellation cannot turn
            # an expired deadline into a successful recorded observation.
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError
        # A 0/0 reading means the run path did not report usage; an LLM turn
        # always consumes prompt tokens, so zeros are unreported, not free.
        reported = bool(result.tokens_in or result.tokens_out)
        record = RunRecord(
            case_id=case_id,
            run_index=run_index,
            profile=profile,
            outcome="success",
            duration_ms=0.0,
            tokens_in=result.tokens_in if reported else None,
            tokens_out=result.tokens_out if reported else None,
            task_verified=result.success,
            error=result.error,
        )
    except TimeoutError as exc:
        record = RunRecord(
            case_id=case_id, run_index=run_index, profile=profile, outcome="timeout",
            duration_ms=0.0, tokens_in=None, tokens_out=None,
            task_verified=False, error=str(exc) or f"Scenario timed out after its {timeout:g}s wall-clock budget",
        )
    except AssertionError as exc:
        outcome, error = _classify_failure(rig, str(exc))
        record = RunRecord(
            case_id=case_id,
            run_index=run_index,
            profile=profile,
            outcome=outcome,
            duration_ms=0.0,
            tokens_in=None,
            tokens_out=None,
            task_verified=False,
            error=error,
        )
    except Exception as exc:
        record = RunRecord(
            case_id=case_id,
            run_index=run_index,
            profile=profile,
            outcome="runtime_error",
            duration_ms=0.0,
            tokens_in=None,
            tokens_out=None,
            task_verified=False,
            error=str(exc),
        )
    finally:
        rig.cleanup()

    return replace(record, duration_ms=_wall_ms(start))

async def run_case_repeated(
    case_id: str,
    *,
    provider: ModelProvider,
    runs: int = 1,
    timeout: float = 120.0,
    max_iterations: int = 10,
    evidence_redactor: EvidenceRedactor | None = None,
) -> list[RunRecord]:
    """Record every attempt; a supplied report policy retains per-attempt credentials."""
    metadata, _ = get_case(case_id)
    records: list[RunRecord] = []
    for index in range(1, runs + 1):
        if evidence_redactor is not None:
            _refresh_policy(evidence_redactor, provider)
        records.append(
            await _run_once(case_id, metadata.profile, provider, index, timeout, max_iterations)
        )
        if evidence_redactor is not None:
            _refresh_policy(evidence_redactor, provider)
    return records


def summarize_runs(records: list[RunRecord]) -> dict[str, Any]:
    """Aggregate run records with explicit denominators, latency and usage."""
    total = len(records)
    successes = sum(1 for record in records if record.outcome == "success")
    outcome_counts = dict.fromkeys(OUTCOMES, 0)
    for record in records:
        outcome_counts[record.outcome] += 1
    by_case: dict[str, dict[str, Any]] = {}
    for record in records:
        case = by_case.setdefault(
            record.case_id,
            {"runs": 0, "successes": 0, "outcome_counts": dict.fromkeys(OUTCOMES, 0)},
        )
        case["runs"] += 1
        if record.outcome == "success":
            case["successes"] += 1
        case["outcome_counts"][record.outcome] += 1
    return {
        "total_runs": total,
        "successes": successes,
        "failures": total - successes,
        "outcome_counts": outcome_counts,
        "cases": by_case,
        "latency_ms": _latency([record.duration_ms for record in records]),
        "usage": {
            "tokens_in": _sum_known([record.tokens_in for record in records]),
            "tokens_out": _sum_known([record.tokens_out for record in records]),
            "available": any(record.tokens_in is not None for record in records),
        },
    }


def build_report(
    *,
    cohort: str,
    requested: dict[str, Any],
    summary: dict[str, Any],
    records: list[RunRecord],
) -> dict[str, Any]:
    """Assemble the repeat-run report with budget, cost provenance and per-run records."""
    return {
        "kind": "baseline_repeat_runs",
        "generated_at": datetime.now(UTC).isoformat(),
        "cohort": cohort,
        "requested": requested,
        "budget": {
            "planned_runs": len(requested["cases"]) * requested["runs_per_case"],
            "executed_runs": len(records),
        },
        "cost": cost_provenance(cohort),
        "summary": summary,
        "runs": [asdict(record) for record in records],
    }


def _restore_known_identity(
    source: Any, projected: Any, key: str, allowed: tuple[str, ...],
) -> None:
    """Retain only exact source-controlled enum values, never arbitrary labels."""
    if isinstance(source, dict) and isinstance(projected, dict):
        value = source.get(key)
        if isinstance(value, str) and value in allowed:
            projected[key] = value


def _restore_report_identities(source: dict[str, Any], projected: dict[str, Any]) -> None:
    """Keep validated protocol values intact after projecting all supplied evidence."""
    _restore_known_identity(source, projected, "kind", ("baseline_repeat_runs",))
    _restore_known_identity(source, projected, "cohort", ("local", "hosted"))
    timestamp = source.get("generated_at")
    if isinstance(timestamp, str) and 25 <= len(timestamp) <= 32:
        with contextlib.suppress(ValueError):
            parsed = datetime.fromisoformat(timestamp)
            if parsed.tzinfo == UTC and parsed.isoformat() == timestamp:
                projected["generated_at"] = timestamp
    original_cost, projected_cost = source.get("cost"), projected.get("cost")
    _restore_known_identity(original_cost, projected_cost, "source", ("local",))
    _restore_known_identity(original_cost, projected_cost, "billing", ("none",))
    requested, safe_requested = source.get("requested"), projected.get("requested")
    if isinstance(requested, dict) and isinstance(safe_requested, dict):
        cases, safe_cases = requested.get("cases"), safe_requested.get("cases")
        if isinstance(cases, list) and isinstance(safe_cases, list):
            for index, case_id in enumerate(cases):
                if isinstance(case_id, str) and case_id in _CASE_IDS:
                    safe_cases[index] = case_id
    runs, safe_runs = source.get("runs"), projected.get("runs")
    if isinstance(runs, list) and isinstance(safe_runs, list):
        for record, safe_record in zip(runs, safe_runs, strict=True):
            _restore_known_identity(record, safe_record, "case_id", _CASE_IDS)
            _restore_known_identity(record, safe_record, "outcome", OUTCOMES)


def write_report(
    path: Path,
    report: dict[str, Any],
    *,
    evidence_redactor: EvidenceRedactor | None = None,
) -> None:
    """Atomically publish a detached evidence projection, retaining report structure.

    Pass a held policy to retain explicitly registered and rotated credentials.
    Every write also refreshes credential-named environment values.
    """
    policy = evidence_redactor if evidence_redactor is not None else EvidenceRedactor()
    projected = policy.redact(report, schema=_REPORT_SCHEMA)
    _restore_report_identities(report, projected)
    text = json.dumps(projected, indent=2, sort_keys=True)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
        os.replace(temporary, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temporary)
        raise


def _refresh_policy(policy: EvidenceRedactor, provider: ModelProvider) -> None:
    """Retain actual provider and environment credentials at report boundaries."""
    policy.register_environment()
    key = getattr(provider, "api_key", None)
    if isinstance(key, str):
        policy.register_secret(key)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evals.baseline_runs",
        description="Run corpus cases for a bounded number of attempts and report every run.",
    )
    parser.add_argument(
        "--cases",
        nargs="*",
        default=None,
        help="Corpus case IDs to run (default: every registered case).",
    )
    parser.add_argument("--runs", type=int, default=2, help="Runs per case (default: 2).")
    parser.add_argument("--timeout", type=float, default=120.0, help="Per-run wall-clock timeout in seconds.")
    parser.add_argument("--max-iterations", type=int, default=10, help="Max agent tool iterations per turn.")
    parser.add_argument("--report", required=True, help="Path to write the JSON report.")
    return parser


def main(argv: list[str]) -> int:
    """Run the declared budget of repeated cases and write a redacted report."""
    import asyncio

    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.runs < 1:
        parser.error("--runs must be a positive integer")
    if not (math.isfinite(args.timeout) and args.timeout > 0):
        parser.error("--timeout must be a finite positive number")
    if args.max_iterations < 0:
        parser.error("--max-iterations must be a nonnegative integer")

    case_ids = list(args.cases) if args.cases else sorted(
        metadata.id for metadata in list_cases()
    )
    for case_id in case_ids:
        try:
            get_case(case_id)
        except ValueError:
            parser.error(f"unknown case: {case_id}")

    try:
        provider = get_eval_provider()
    except RuntimeError as exc:
        parser.error(str(exc))

    policy = EvidenceRedactor()
    _refresh_policy(policy, provider)

    records: list[RunRecord] = []
    for case_id in case_ids:
        records.extend(
            asyncio.run(
                run_case_repeated(
                    case_id,
                    provider=provider,
                    runs=args.runs,
                    timeout=args.timeout,
                    max_iterations=args.max_iterations,
                    evidence_redactor=policy,
                )
            )
        )
        _refresh_policy(policy, provider)

    summary = summarize_runs(records)
    cohort = cohort_for_provider(provider.name)
    requested = {
        "cases": case_ids,
        "runs_per_case": args.runs,
        "timeout": args.timeout,
        "max_iterations": args.max_iterations,
        "provider": provider.name,
        "model": getattr(provider, "default_model", None) or getattr(provider, "model", None),
    }
    report = build_report(cohort=cohort, requested=requested, summary=summary, records=records)
    _refresh_policy(policy, provider)
    write_report(Path(args.report), report, evidence_redactor=policy)
    return 0 if (records and all(record.outcome == "success" for record in records)) else 1


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
