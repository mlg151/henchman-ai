"""Evaluate team-produced packages with an independent offline lifecycle oracle."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, cast

from evals.artifact_observation import ArtifactTimeline, fingerprint, tool_target
from evals.helpers import EvalTestRig
from evals.models import ToolLog
from evals.package_oracle import (
    EDITABLE_FILES,
    PACKAGE_TASK,
    SPEC_DIGEST,
    prepare_package_workspace,
    verify_package_artifacts,
)
from henchman.tools.security import sanitize_error_message

SCENARIO = "team_python_package"
VERSION = 1
_INSPECTION_FILES = (
    EDITABLE_FILES[0],
    "reference/label_rules.py",
    "pyproject.toml",
    "tests/test_installed.py",
    ".github/workflows/ci.yml",
)
_TEAM_TASK = """
Delegate inspection of the existing implementation, reference/label_rules.py,
pyproject.toml, protected tests and CI YAML to a specialist before editing;
use read_file for those artifacts.
The engineer owns both implementation files and the final wheel. After final edits,
delegate review to a different specialist who reads both implementation files and
returns a completed review. The leader must finish after the handoffs return.
The independent evaluator's clean install/test/CLI pipeline is separate from any
checks performed by the team. Report team commands accurately.
"""
_SPEC_DIGEST = hashlib.sha256((SPEC_DIGEST + _TEAM_TASK).encode()).hexdigest()


def _timed(log: ToolLog) -> bool:
    return (
        type(log.request_index) is int
        and type(log.result_index) is int
        and 0 <= log.request_index < log.result_index
    )


def assess_package_team(
    logs: list[ToolLog],
    workspace: Path,
    observation: dict[str, Any],
) -> dict[str, bool]:
    """Require ordered, attributed tool evidence and a returned review delegation."""
    first = observation["first_implementation_change"]
    last = observation["last_implementation_change"]
    if not observation["complete"] or first is None or last is None:
        return {
            "inspection_before_edit": False,
            "engineer_edit": False,
            "independent_review_completed": False,
        }
    reads = [log for log in logs if _timed(log) and log.success and log.tool_name == "read_file"]
    inspection = all(
        any(
            log.source_agent not in (None, "tech_lead", "orchestrator")
            and log.result_index < first
            and tool_target(log, workspace) == name
            for log in reads
        )
        for name in _INSPECTION_FILES
    )
    engineer_files = {
        tool_target(log, workspace)
        for log in logs
        if _timed(log)
        and log.success
        and log.source_agent == "engineer"
        and log.tool_name in ("write_file", "edit_file")
    }
    handoffs = [
        log
        for log in logs
        if _timed(log)
        and log.success
        and log.tool_name == "delegate_task"
        and log.source_agent in ("tech_lead", "orchestrator")
    ]
    engineer = (
        set(EDITABLE_FILES) <= engineer_files
        and any(
            _timed(log)
            and log.success
            and log.source_agent == "engineer"
            and log.tool_name in ("write_file", "edit_file", "python_exec", "shell")
            and cast(int, log.request_index) <= last <= cast(int, log.result_index)
            for log in logs
        )
        and any(
            log.arguments.get("agent") == "engineer" and log.result_index > last for log in handoffs
        )
    )
    reviewed = any(
        handoff.request_index > last
        and handoff.arguments.get("agent") not in (None, "engineer", "tech_lead", "orchestrator")
        and all(
            any(
                read.source_agent == handoff.arguments["agent"]
                and cast(int, handoff.request_index)
                < cast(int, read.request_index)
                < cast(int, read.result_index)
                < cast(int, handoff.result_index)
                and tool_target(read, workspace) == name
                for read in reads
            )
            for name in EDITABLE_FILES
        )
        for handoff in handoffs
    )
    return {
        "inspection_before_edit": inspection,
        "engineer_edit": engineer,
        "independent_review_completed": reviewed,
    }


async def run_team_python_package(
    rig: EvalTestRig,
    *,
    max_iterations: int = 25,
    timeout: float = 300,
) -> dict[str, Any]:
    """Separate delivered artifacts, runtime completion and observed collaboration."""
    report: dict[str, Any] = {
        "scenario": SCENARIO,
        "version": VERSION,
        "spec_digest": _SPEC_DIGEST,
        "success": False,
        "task_verified": False,
        "runtime": {},
        "workflow": {},
        "package": {},
        "checks": {},
        "errors": [],
        "agent_install_test_execution": "not_attested",
    }
    try:
        if rig.profile_metadata.get("profile") != "team":
            raise ValueError("This scenario requires the production team evaluation profile")
        workspace = rig.test_dir
        baseline = await prepare_package_workspace(workspace)
        initial: dict[str, str | None] = dict(baseline.initial_hashes)
        protected = tuple(dict(baseline.protected_hashes))
        timeline = ArtifactTimeline(
            workspace, initial, implementation_paths=EDITABLE_FILES, protected_paths=protected
        )
        result = await rig.run(
            PACKAGE_TASK + _TEAM_TASK,
            max_iterations=max_iterations,
            timeout=timeout,
            observe_event=timeline,
        )
        observation = timeline.finish(len(result.events))
        workflow = assess_package_team(result.tool_logs, workspace, observation)
        report["workflow"] = dict(workflow, artifact_observation=observation)
        report["tool_observations"] = [
            {
                "tool_name": log.tool_name,
                "source_agent": log.source_agent,
                "tool_call_id": log.tool_call_id,
                "path": tool_target(log, workspace),
                "request_index": log.request_index,
                "result_index": log.result_index,
                "success": log.success,
            }
            for log in result.tool_logs
        ]
        report["runtime"] = {
            "success": result.success,
            "error": result.error,
            "duration_ms": result.duration_ms,
            "final_response": result.final_response,
            "profile": rig.profile_metadata,
            "tool_calls": len(result.tool_logs),
            "diagnostics": result.diagnostics,
        }
        before = {name: fingerprint(workspace / name) for name in initial}
        report["package"] = await verify_package_artifacts(workspace, baseline)
        final = {name: fingerprint(workspace / name) for name in initial}
        report["fingerprints"] = {"initial": initial, "final": final}
        checks = {
            "artifact_observation_complete": observation["complete"],
            "fixtures_unchanged": not observation["protected_change_observed"]
            and all(final[name] == initial[name] for name in protected),
            "implementation_changed": all(
                final[name] is not None and final[name] != initial[name] for name in EDITABLE_FILES
            ),
            "artifacts_stable_during_checks": before == final,
            "independent_package_pipeline": report["package"]["success"] is True,
        }
        report["checks"] = {name: {"success": passed} for name, passed in checks.items()}
        if not result.success:
            report["errors"].append(result.error or "Production team runtime failed")
        report["errors"].extend(
            f"Missing team evidence: {name}" for name, passed in workflow.items() if not passed
        )
        report["errors"].extend(
            f"Independent check failed: {name}" for name, passed in checks.items() if not passed
        )
        report["success"] = not report["errors"]
    except Exception as exc:
        report["errors"].append(sanitize_error_message(f"{type(exc).__name__}: {exc}")[:8192])
    return report
