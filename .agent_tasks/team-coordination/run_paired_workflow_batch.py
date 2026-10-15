"""Run the predeclared six samples sequentially, preserving every outcome."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path

from henchman.tools.subprocess_utils import run_bounded_subprocess

ROOT = Path(__file__).resolve().parent
ORDER = (("baseline", 1), ("candidate", 1), ("candidate", 2),
         ("baseline", 2), ("baseline", 3), ("candidate", 3))
MANIFEST = ROOT / "paired-workflow-manifest.json"
SAMPLE = ROOT / "run_paired_workflow_sample.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(report: dict) -> dict:
    result = report.get("result", {})
    runtime = result.get("runtime", {})
    checks = result.get("checks", {})
    workflow = result.get("workflow", {})
    requests = report.get("requests", [])
    return {
        "success": report.get("success") is True,
        "runtime_success": runtime.get("success") is True,
        "runtime_duration_ms": runtime.get("duration_ms"),
        "requests": len(requests), "usage_complete": report.get("usage_complete"),
        "observed_usage": report.get("observed_usage"),
        "estimated_uncached_cost_usd": report.get("estimated_uncached_cost_usd"),
        "independent_checks": {name: value.get("success") is True
                               for name, value in checks.items()},
        "workflow": {name: workflow.get(name) for name in
                     ("inspection_before_edit", "engineer_edit", "post_edit_tests",
                      "independent_review", "protected_edit_observed")},
        "errors": result.get("errors", []), "error": report.get("error"),
        "http_statuses": [row["http_status"] for row in requests if "http_status" in row],
        "sdk_attested_requests": sum("role_template" in row for row in requests),
    }


async def main() -> None:
    if MANIFEST.exists():
        raise RuntimeError("Batch already exists; refusing to overwrite it")
    for variant, repetition in ORDER:
        prefix = f"paired-workflow-{variant}-{repetition}"
        if any((ROOT / (prefix + suffix)).exists() for suffix in
               ("-report.json", "-artifacts", "-stdout.log", "-stderr.log")):
            raise RuntimeError("A planned sample already exists")
    frozen_paths = [ROOT / f"workflow-prompts-{variant}.json"
                    for variant in ("baseline", "candidate")]
    runtime_paths = [ROOT.parents[1] / name for name in
                     ("evals/team_runtime.py", "evals/test_team_python_workflow.py",
                      "src/henchman/core/agent.py", "src/henchman/agents/delegation.py",
                      "src/henchman/agents/prompts.py", "src/henchman/cli/prompts.py",
                      "src/henchman/tools/registry.py")]
    frozen_hashes = {str(path): digest(path) for path in [*frozen_paths, *runtime_paths, SAMPLE]}
    manifest = {"status": "running", "order": ORDER, "samples": [],
                "frozen_hashes": frozen_hashes, "sample_process_timeout": 720,
                "limitations": ["Three samples per variant on one small task and one model",
                                "Provider-default sampling and provider-selected routing",
                                "No industry comparator or native OS coverage",
                                "Cost is an estimate from recorded model catalog prices"]}
    def persist() -> None:
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    persist()
    for variant, repetition in ORDER:
        if any(digest(Path(path)) != value for path, value in frozen_hashes.items()):
            manifest.update(status="stopped", stop_reason="Frozen inputs changed")
            persist()
            raise RuntimeError("Frozen inputs changed during the batch")
        prefix = f"paired-workflow-{variant}-{repetition}"
        row = {"variant": variant, "repetition": repetition, "status": "running"}
        manifest["samples"].append(row)
        persist()
        print(json.dumps({"sample_started": prefix}), flush=True)
        started = time.perf_counter()
        try:
            process = await run_bounded_subprocess(
                [sys.executable, str(SAMPLE), "--variant", variant,
                 "--repetition", str(repetition)],
                cwd=ROOT.parents[1], timeout=720, max_output_bytes=524288,
            )
            (ROOT / f"{prefix}-stdout.log").write_bytes(process.stdout)
            (ROOT / f"{prefix}-stderr.log").write_bytes(process.stderr)
            row.update(returncode=process.returncode,
                       output_truncated=process.stdout_truncated or process.stderr_truncated)
            if process.returncode != 0 or row["output_truncated"]:
                raise RuntimeError("Sample process failed or output was truncated")
            report_path = ROOT / f"{prefix}-report.json"
            report = json.loads(report_path.read_text())
            row.update(status="completed", report=report_path.name, summary=summarize(report))
            requests = report.get("requests", [])
            if not requests or any("sdk_request_options" not in request or
                                   "role_template" not in request or
                                   not all(request.get("environment_context", {}).values())
                                   for request in requests):
                raise RuntimeError("Sample SDK/environment attestation incomplete")
            if any(digest(Path(path)) != value for path, value in frozen_hashes.items()):
                raise RuntimeError("Frozen inputs changed during sample")
            if report.get("error") or report.get("cleanup_errors") or row["summary"]["http_statuses"]:
                raise RuntimeError("Sample infrastructure or HTTP failure; no retry")
        except BaseException as error:
            row.update(status="stopped", process_error=type(error).__name__ + ": " + str(error))
            manifest.update(status="stopped", stop_reason=row["process_error"])
            raise
        finally:
            row["elapsed_seconds"] = round(time.perf_counter() - started, 3)
            persist()
        print(json.dumps({"sample_finished": prefix, **row["summary"]}), flush=True)
    manifest["status"] = "completed"
    manifest["aggregate"] = {}
    for variant in ("baseline", "candidate"):
        summaries = [row["summary"] for row in manifest["samples"] if row["variant"] == variant]
        manifest["aggregate"][variant] = {
            "samples": len(summaries),
            "task_successes": sum(row["success"] for row in summaries),
            "runtime_successes": sum(row["runtime_success"] for row in summaries),
            "all_independent_checks_passed": sum(bool(row["independent_checks"]) and
                                                all(row["independent_checks"].values())
                                                for row in summaries),
            "post_edit_tests_observed": sum(row["workflow"]["post_edit_tests"] is True for row in summaries),
            "independent_review_observed": sum(row["workflow"]["independent_review"] is True for row in summaries),
            "requests": sum(row["requests"] for row in summaries),
            "runtime_duration_ms": sum(row["runtime_duration_ms"] or 0 for row in summaries),
            "estimated_uncached_cost_usd": sum(row["estimated_uncached_cost_usd"] or 0 for row in summaries),
        }
    persist()
    print(json.dumps({"batch_completed": str(MANIFEST), "aggregate": manifest["aggregate"]}), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
