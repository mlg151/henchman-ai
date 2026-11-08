"""Frozen local-only direct versus staged comparison; no requests in plan mode."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

import henchman

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evals.staged_delegation_paired.worker import PLAN_SHA256, load_plan, prompt_for

HERE = Path(__file__).resolve().parent
PLAN = HERE / "plan.json"
WORKER = HERE / "worker.py"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_wheel(wheel: Path, expected: str) -> None:
    """Verify both the held wheel and installed package bytes before each attempt."""
    if sha(wheel.read_bytes()) != expected:
        raise ValueError("The comparison wheel does not match the frozen plan")
    package = Path(henchman.__file__).resolve().parent
    if "site-packages" not in package.parts:
        raise ValueError("The comparison requires an installed wheel, not source imports")
    with zipfile.ZipFile(wheel) as archive:
        names = {name for name in archive.namelist() if name.startswith("henchman/") and not name.endswith("/")}
        if not names:
            raise ValueError("The comparison wheel has no package files")
        for name in names:
            relative = Path(name).relative_to("henchman")
            target = package / relative
            if not target.is_file() or target.is_symlink() or target.read_bytes() != archive.read(name):
                raise ValueError("The installed package differs from the held wheel")
        installed_python = {path.relative_to(package).as_posix() for path in package.rglob("*.py")}
        wheel_python = {Path(name).relative_to("henchman").as_posix() for name in names if name.endswith(".py")}
        if installed_python != wheel_python:
            raise ValueError("The installed package contains unexpected Python modules")


def oracle(path: Path, expected: str) -> tuple[bool, str | None]:
    """Compare current bytes using a narrow AST oracle without executing them."""
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1_048_576:
            return False, None
        data = path.read_bytes()
        actual = ast.dump(ast.parse(data.decode("utf-8")), include_attributes=False)
        reference = ast.dump(ast.parse(expected), include_attributes=False)
        return actual == reference, sha(data)
    except (OSError, UnicodeError, SyntaxError, ValueError):
        return False, None


def route_observed(arm: str, events: list[dict[str, Any]]) -> bool:
    successful = {item.get("tool") for item in events if item.get("event") == "result" and item.get("success") is True}
    requested = {item.get("tool") for item in events if item.get("event") == "request"}
    if arm == "direct":
        return bool(successful & {"write_file", "edit_file"}) and "invoke_subagent" not in requested
    return {"invoke_subagent", "manage_subagents", "publish_subagent_proposal"} <= successful


def save_report(path: Path, report: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_live(plan: dict[str, Any], output: Path, wheel: Path) -> None:
    if not output.is_absolute() or output.exists() or output.is_symlink():
        raise ValueError("Output must be a new absolute directory")
    parent = output.parent.resolve(strict=True)
    if parent != output.parent.absolute():
        raise ValueError("Output parent must be a physical directory")
    verify_wheel(wheel, plan["wheel_sha256"])
    worker_hash = sha(WORKER.read_bytes())
    runner_hash = sha(Path(__file__).read_bytes())
    fixtures = {item["id"]: item for item in plan["fixtures"]}
    rows = [{"case": case, "repeat": repeat, "arm": arm, "status": "not_run"}
            for case, repeat, arm in plan["arm_order"]]
    report: dict[str, Any] = {"kind": plan["kind"], "harness_version": "v2-primary-actor-guard", "plan_sha256": PLAN_SHA256,
        "source_commit": plan["source_commit"], "wheel_sha256": plan["wheel_sha256"],
        "worker_sha256": worker_hash, "runner_sha256": runner_hash,
        "endpoint": plan["endpoint"], "model": plan["model"], "planned": len(rows), "rows": rows,
        "limitations": ["Local provider route only; no hosted fallback.",
                        "Serialized test transport is not production provider scheduling.",
                        "Client peak RSS covers the worker process only; it excludes formatter subprocesses, the shared model server and GPU.",
                        "Request counts are recorded; complete token usage and hardware or electricity costs are not measured.",
                        "The AST oracle is deliberately narrow and does not execute generated code.",
                        "The shared server is checked for an idle slot but is not exclusively reserved."]}
    output.mkdir()
    report_path = output / "report.json"
    save_report(report_path, report)
    for index, row in enumerate(rows):
        verify_wheel(wheel, plan["wheel_sha256"])
        if sha(WORKER.read_bytes()) != worker_hash or sha(Path(__file__).read_bytes()) != runner_hash:
            raise RuntimeError("The comparison harness changed during execution")
        load_plan(PLAN)
        fixture = fixtures[row["case"]]
        root = output / f"{index + 1:02d}-{row['case']}-{row['repeat']}-{row['arm']}"
        root.mkdir()
        home, temp = root / "home", root / "tmp"
        home.mkdir()
        temp.mkdir()
        environment = {"PATH": "/usr/bin:/bin", "HOME": str(home), "USERPROFILE": str(home),
                       "XDG_CONFIG_HOME": str(home / "config"), "TMPDIR": str(temp), "PYTHONNOUSERSITE": "1"}
        command = [sys.executable, str(WORKER), "--plan", str(PLAN), "--case", row["case"],
                   "--arm", row["arm"], "--root", str(root)]
        started = time.monotonic()
        exit_code: int | None = None
        row["status"] = "running"
        save_report(report_path, report)
        try:
            result = subprocess.run(command, cwd=root, env=environment, capture_output=True, text=True,
                                    timeout=plan["timeout_seconds"] + 30, check=False)
            exit_code = result.returncode
            (root / "stdout.txt").write_text(result.stdout[:8192], encoding="utf-8")
            (root / "stderr.txt").write_text(result.stderr[:8192], encoding="utf-8")
            if result.stdout:
                print(result.stdout.strip()[:1000], flush=True)
        except subprocess.TimeoutExpired:
            row["error"] = "worker_timeout"
        except KeyboardInterrupt:
            row["status"] = "interrupted_unknown"
            row["elapsed_seconds"] = round(time.monotonic() - started, 3)
            save_report(report_path, report)
            raise
        except OSError as error:
            row["error"] = f"launch_error:{type(error).__name__}"
        row["elapsed_seconds"] = round(time.monotonic() - started, 3)
        row["exit_code"] = exit_code
        worker_path = root / "worker.json"
        if not worker_path.is_file():
            row["status"] = "worker_timeout" if row.get("error") == "worker_timeout" else "worker_result_missing"
            save_report(report_path, report)
            print(f"{index + 1}/{len(rows)} {row['case']} {row['arm']}: worker result missing", flush=True)
            continue
        try:
            worker = json.loads(worker_path.read_text())
        except (OSError, ValueError):
            row["status"] = "worker_result_invalid"
            save_report(report_path, report)
            print(f"{index + 1}/{len(rows)} {row['case']} {row['arm']}: worker result invalid", flush=True)
            continue
        matches, result_hash = oracle(root / "project" / fixture["path"], fixture["expected"])
        observed = route_observed(row["arm"], worker["events"])
        completed = worker["outcome"] == "completed" and worker["completion"] == "completed"
        initial_hash = sha(fixture["initial"].encode())
        task_hash = sha(fixture["task"].encode())
        prompt_hash = sha(prompt_for(fixture, row["arm"]).encode())
        input_matches = (worker["initial_sha256"] == initial_hash and worker["task_sha256"] == task_hash
                         and worker["prompt_sha256"] == prompt_hash)
        accepted = bool(exit_code == 0 and completed and matches and observed
                        and result_hash == worker["result_sha256"] and not worker["transport_errors"]
                        and worker.get("events_truncated") is False and input_matches)
        row.update({"status": "accepted" if accepted else "failed", "worker": worker,
                    "independent_exact_ast": matches, "independent_sha256": result_hash,
                    "route_observed": observed, "input_matches_plan": input_matches,
                    "initial_sha256": initial_hash, "task_sha256": task_hash, "prompt_sha256": prompt_hash})
        save_report(report_path, report)
        print(f"{index + 1}/{len(rows)} {row['case']} {row['arm']}: {row['status']}", flush=True)
    report["accepted"] = sum(row["status"] == "accepted" for row in rows)
    report["executed"] = sum(row["status"] != "not_run" for row in rows)
    save_report(report_path, report)
    print(f"Retained {report['executed']}/{report['planned']} attempts; {report['accepted']} accepted.", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("plan", "live"))
    parser.add_argument("--output")
    parser.add_argument("--wheel")
    args = parser.parse_args()
    plan = load_plan(PLAN)
    if args.mode == "plan":
        print(json.dumps({"plan_sha256": PLAN_SHA256, "source_commit": plan["source_commit"],
                          "model": plan["model"], "attempts": plan["arm_order"]}, indent=2))
        return
    if not args.output or not args.wheel:
        parser.error("live requires --output and --wheel")
    run_live(plan, Path(args.output), Path(args.wheel).resolve(strict=True))


if __name__ == "__main__":
    main()
