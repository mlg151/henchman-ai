"""Independently audit retained results without executing generated files."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any

if not __package__:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evals.staged_delegation_paired.worker import PLAN_SHA256, load_plan, prompt_for

HERE = Path(__file__).resolve().parent


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate(output: Path) -> dict[str, Any]:
    plan = load_plan(HERE / "plan.json")
    raw = (output / "report.json").read_bytes()
    report = json.loads(raw)
    if (report.get("plan_sha256") != PLAN_SHA256 or report.get("source_commit") != plan["source_commit"]
            or report.get("wheel_sha256") != plan["wheel_sha256"] or report.get("harness_version") != "v2-primary-actor-guard"
            or report.get("worker_sha256") != digest((HERE / "worker.py").read_bytes())
            or report.get("runner_sha256") != digest((HERE / "runner.py").read_bytes())):
        raise ValueError("The retained report does not match the frozen comparison")
    rows = report.get("rows")
    if not isinstance(rows, list) or len(rows) != len(plan["arm_order"]):
        raise ValueError("The fixed attempt denominator is incomplete")
    fixtures = {item["id"]: item for item in plan["fixtures"]}
    counts = {"direct": {"accepted": 0, "failed": 0, "unknown": 0, "not_run": 0},
              "staged": {"accepted": 0, "failed": 0, "unknown": 0, "not_run": 0}}
    audited = []
    for index, (row, expected_order) in enumerate(zip(rows, plan["arm_order"], strict=True)):
        case, repeat, arm = expected_order
        if [row.get("case"), row.get("repeat"), row.get("arm")] != expected_order:
            raise ValueError("Attempt order differs from the frozen plan")
        status = row.get("status")
        if status == "not_run":
            counts[arm]["not_run"] += 1
            audited.append({"case": case, "repeat": repeat, "arm": arm, "status": status})
            continue
        if status in {"running", "interrupted_unknown", "worker_timeout", "worker_result_missing", "worker_result_invalid"}:
            counts[arm]["unknown"] += 1
            audited.append({"case": case, "repeat": repeat, "arm": arm, "status": status})
            continue
        if status not in {"accepted", "failed"}:
            raise ValueError("Unknown attempt status")
        root = output / f"{index + 1:02d}-{case}-{repeat}-{arm}"
        worker_path = root / "worker.json"
        target = root / "project" / fixtures[case]["path"]
        if root.is_symlink() or (root / "project").is_symlink() or worker_path.is_symlink() or target.is_symlink():
            raise ValueError("Attempt evidence must not be symlinks")
        worker = json.loads(worker_path.read_text())
        if worker != row.get("worker"):
            raise ValueError("Worker evidence differs from the aggregate report")
        fixture = fixtures[case]
        input_ok = (worker.get("initial_sha256") == digest(fixture["initial"].encode())
                    and worker.get("task_sha256") == digest(fixture["task"].encode())
                    and worker.get("prompt_sha256") == digest(prompt_for(fixture, arm).encode()))
        result_hash: str | None = None
        ast_matches = False
        try:
            data = target.read_bytes()
            if len(data) > 1_048_576:
                raise ValueError("oversized fixture")
            actual_ast = ast.dump(ast.parse(data.decode("utf-8")), include_attributes=False)
            expected_ast = ast.dump(ast.parse(fixture["expected"]), include_attributes=False)
            result_hash = digest(data)
            ast_matches = actual_ast == expected_ast
        except (OSError, UnicodeError, SyntaxError, ValueError):
            pass
        artifact_ok = ast_matches and result_hash == worker.get("result_sha256")
        events = worker.get("events", [])
        if not isinstance(events, list):
            raise ValueError("Invalid event evidence")
        successes = {event.get("tool") for event in events
                     if isinstance(event, dict) and event.get("event") == "result" and event.get("success") is True}
        requests = {event.get("tool") for event in events
                    if isinstance(event, dict) and event.get("event") == "request"}
        route_ok = (bool(successes & {"write_file", "edit_file"}) and "invoke_subagent" not in requests
                    if arm == "direct" else
                    {"invoke_subagent", "manage_subagents", "publish_subagent_proposal"} <= successes)
        if (row.get("independent_exact_ast") is not ast_matches or row.get("independent_sha256") != result_hash
                or row.get("input_matches_plan") is not input_ok or row.get("route_observed") is not route_ok):
            raise ValueError("Aggregate evidence differs from independent observations")
        attempts = worker.get("transport_attempts")
        valid_attempts = type(attempts) is int and 0 <= attempts <= plan["request_limit"]
        accepted = bool(row.get("exit_code") == 0 and worker.get("outcome") == "completed"
                        and worker.get("completion") == "completed" and input_ok and artifact_ok and route_ok
                        and valid_attempts and not worker.get("transport_errors")
                        and worker.get("events_truncated") is False)
        if accepted != (status == "accepted"):
            raise ValueError("Attempt acceptance does not match retained evidence")
        counts[arm]["accepted" if accepted else "failed"] += 1
        audited.append({"case": case, "repeat": repeat, "arm": arm, "status": status,
                        "input_matches": input_ok, "artifact_matches": artifact_ok, "route_observed": route_ok})
    if "accepted" in report and report["accepted"] != sum(item["accepted"] for item in counts.values()):
        raise ValueError("Accepted total differs from the retained rows")
    if "executed" in report and report["executed"] != sum(row.get("status") != "not_run" for row in rows):
        raise ValueError("Executed total differs from the retained rows")
    return {"kind": "staged_delegation_paired_audit", "report_sha256": digest(raw),
            "plan_sha256": PLAN_SHA256, "counts": counts, "rows": audited,
            "limitations": report.get("limitations", [])}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", help="Existing result directory")
    args = parser.parse_args()
    result = validate(Path(args.output).resolve(strict=True))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
