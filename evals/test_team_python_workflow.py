"""Opt-in production-team evaluation with independent Python and CLI checks.

This measures one small task and observed collaboration, not general task safety
or deployment readiness. The temporary workspace is not an OS sandbox.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from collections.abc import Awaitable, Callable
from functools import partial
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from evals.artifact_observation import ArtifactTimeline
from evals.artifact_observation import fingerprint as _fingerprint
from evals.artifact_observation import tool_target as _target
from evals.helpers import EvalTestRig, ToolLog, verify_python
from evals.test_python_reuse import _CALLER, _NORMALIZATION, _TESTS
from henchman.tools.security import sanitize_error_message
from henchman.tools.subprocess_utils import run_bounded_subprocess

SCENARIO = "team_python_workflow"
VERSION = 3
_CLI_STUB = '''def main(argv: list[str] | None = None) -> int:
    """Print a JSON array of unique normalized positional labels."""
    raise NotImplementedError("Reuse label_index.unique_labels")


if __name__ == "__main__":
    raise SystemExit(main())
'''
_QUALITY_CONFIG = """[tool.ruff]
target-version = "py311"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I"]

[tool.black]
line-length = 88
target-version = ["py311"]

[tool.mypy]
python_version = "3.11"
strict = true
"""
_FIXTURES = {
    "normalization.py": _NORMALIZATION,
    "label_index.py": _CALLER,
    "test_labels.py": _TESTS,
    "label_cli.py": _CLI_STUB,
    "pyproject.toml": _QUALITY_CONFIG,
}
_PROTECTED = ("normalization.py", "test_labels.py", "pyproject.toml")
_SOURCES = ("normalization.py", "label_index.py", "label_cli.py")
_EDIT_TOOLS = {"edit_file", "write_file", "patch_apply", "code_format"}
_INSPECT_TOOLS = {"read_file", "grep", "file_overview", "symbol_trace", "pattern_search"}
_PROMPT = """Complete this Python task as a team using the existing specialist roles.
Have a specialist inspect the existing normalizer and caller before implementation.
Have the engineer implement label_index.unique_labels and label_cli.py using
edit_file or write_file. Reuse normalization.normalize_label for EVERY input;
do not duplicate that helper. Return nonempty canonical labels once each in
first-seen order, preserving the original input list, including Unicode casefolding.
The stdlib-only CLI accepts positional labels and prints their unique_labels result
as one JSON array. No arguments prints []; unsupported options exit with status 2.
It must run both as `python -m label_cli` in this directory and as
`python /absolute/path/to/label_cli.py` from another working directory.
Keep normalization.py, test_labels.py, and pyproject.toml byte-for-byte unchanged.
Run the actual pytest_run tool on all of test_labels.py after the final edit;
all four tests must execute and pass, with no selection filters or collection-only.
Have a different specialist inspect and review BOTH completed implementation files.
The harness automatically formats changed Python files with Black before tool
results return. Use type annotations and pass Ruff check (E,F,I, Python 3.11,
line length 88), Black --check, and strict mypy for the three production files.
Use no new dependencies. Report actual checks and unresolved failures accurately.
"""
SPEC_DIGEST = hashlib.sha256(
    json.dumps(
        {
            "scenario": SCENARIO,
            "version": VERSION,
            "fixtures": _FIXTURES,
            "prompt": _PROMPT,
            "quality": "ruff:E,F,I;black:88:py311;python:3.11;mypy:strict",
        },
        sort_keys=True,
    ).encode()
).hexdigest()


def _check(success: bool, error: str | None = None) -> dict[str, Any]:
    return {"success": success, "error": error}


async def _observe(operation: Callable[[], Awaitable[None]]) -> dict[str, Any]:
    try:
        await operation()
    except Exception as exc:
        return _check(False, sanitize_error_message(f"{type(exc).__name__}: {exc}")[:8192])
    return _check(True)


class _ArtifactTimeline(ArtifactTimeline):
    """Observe workflow fixtures with the scenario's fingerprint hook."""

    def __init__(self, workspace: Path, initial: dict[str, str | None]) -> None:
        super().__init__(
            workspace,
            initial,
            implementation_paths=("label_index.py", "label_cli.py"),
            protected_paths=_PROTECTED,
            fingerprint=lambda path: _fingerprint(path),
        )


def _fresh_import_code(code: str) -> str:
    """Ignore previously generated project bytecode in independent child checks."""
    return (
        "import sys, tempfile\n"
        "with tempfile.TemporaryDirectory(prefix='henchman-oracle-cache-') as cache:\n"
        "    sys.pycache_prefix = cache\n"
        "    sys.dont_write_bytecode = True\n"
        f"    exec(compile({code!r}, '<team-oracle>', 'exec'))\n"
    )


async def _verify_behavior(workspace: Path) -> None:
    code = (
        _TESTS
        + "\n"
        + "\n".join(
            f"{name}()"
            for name in (
                "test_normalization_and_duplicates",
                "test_empty_order_and_unicode",
                "test_input_unchanged",
                "test_calls_existing_helper",
            )
        )
    )
    await verify_python(workspace, _fresh_import_code(code), timeout=10)


async def _verify_cli(workspace: Path) -> None:
    # Observe reuse separately from fresh subprocess command-line behavior.
    code = """import contextlib, io, json, runpy, sys
from unittest.mock import patch
import label_index
calls = []
def observed(values):
    calls.append(list(values))
    return ["oracle-sentinel"]
output = io.StringIO()
with patch.object(label_index, "unique_labels", observed), patch.object(sys, "argv", ["label_cli.py", " B ", "A", "b"]), contextlib.redirect_stdout(output):
    try:
        runpy.run_module("label_cli", run_name="__main__")
    except SystemExit as exc:
        assert exc.code in (None, 0), exc.code
assert calls == [[" B ", "A", "b"]], "CLI did not call the shared caller"
assert json.loads(output.getvalue()) == ["oracle-sentinel"], "CLI ignored caller output"
"""
    await verify_python(workspace, _fresh_import_code(code), timeout=10)
    with tempfile.TemporaryDirectory(prefix="henchman-cli-check-") as directory:
        outside = Path(directory)
        cases = [
            (workspace, ["-m", "label_cli"], [], 0, []),
            (
                workspace,
                ["-m", "label_cli"],
                ["  Red Fox ", "RED FOX", "Straße", "STRASSE", ""],
                0,
                ["red-fox", "strasse"],
            ),
            (
                outside,
                [str(workspace / "label_cli.py")],
                ["Zoo", " Apple ", "zoo"],
                0,
                ["zoo", "apple"],
            ),
            (outside, [str(workspace / "label_cli.py")], ["--unsupported-option"], 2, None),
        ]
        for cwd, invocation, arguments, expected_exit, expected_json in cases:
            completed = await run_bounded_subprocess(
                [
                    sys.executable,
                    "-E",
                    "-B",
                    "-X",
                    "utf8",
                    "-X",
                    f"pycache_prefix={outside / 'cache'}",
                    *invocation,
                    *arguments,
                ],
                cwd=cwd,
                timeout=10,
                max_output_bytes=8192,
            )
            assert completed.returncode == expected_exit, (
                f"CLI exit {completed.returncode}, expected {expected_exit}: "
                + completed.stderr.decode("utf-8", errors="replace")
            )
            assert not completed.stdout_truncated, "CLI output exceeded the bound"
            if expected_json is not None:
                assert json.loads(completed.stdout) == expected_json


async def _quality(command: list[str], cwd: Path) -> None:
    completed = await run_bounded_subprocess(
        [sys.executable, "-I", "-X", "utf8", "-m", *command],
        cwd=cwd,
        timeout=30,
        max_output_bytes=8192,
    )
    assert completed.returncode == 0, f"{command[0]} exited {completed.returncode}: " + (
        completed.stdout + completed.stderr
    ).decode("utf-8", errors="replace")


async def verify_team_python_outputs(workspace: Path) -> dict[str, Any]:
    """Run bounded, independent assertions and fixed quality policies serially."""
    if any(_fingerprint(workspace / name) is None for name in _SOURCES):
        return {
            name: _check(False, "Missing, symlinked, or oversized source")
            for name in (
                "behavior",
                "cli",
                "ruff_lint",
                "black_format",
                "mypy",
            )
        }
    checks = {
        "behavior": await _observe(lambda: _verify_behavior(workspace)),
        "cli": await _observe(lambda: _verify_cli(workspace)),
    }
    with tempfile.TemporaryDirectory(prefix="henchman-quality-") as directory:
        external = Path(directory)
        config = external / "mypy.ini"
        config.write_text("[mypy]\nstrict = True\npython_version = 3.11\n", encoding="utf-8")
        black_config = external / "black.toml"
        black_config.write_text(
            '[tool.black]\nline-length = 88\ntarget-version = ["py311"]\n', encoding="utf-8"
        )
        sources = [str(workspace / name) for name in _SOURCES]
        commands = {
            "ruff_lint": [
                "ruff",
                "check",
                "--isolated",
                "--select",
                "E,F,I",
                "--target-version",
                "py311",
                "--line-length",
                "88",
                *sources,
            ],
            "black_format": [
                "black",
                "--check",
                "--config",
                str(black_config),
                "--target-version",
                "py311",
                "--line-length",
                "88",
                *sources,
            ],
            "mypy": [
                "mypy",
                "--config-file",
                str(config),
                "--no-incremental",
                "--cache-dir",
                str(external / "cache"),
                *sources,
            ],
        }
        for name, command in commands.items():
            checks[name] = await _observe(partial(_quality, command, external))
    return checks


def _inspected(log: ToolLog, workspace: Path, name: str, symbol: str) -> bool:
    return bool(
        log.success
        and log.tool_name in _INSPECT_TOOLS
        and symbol in log.result
        and (_target(log, workspace) == name or name in log.result)
    )


def assess_team_workflow(
    logs: list[ToolLog],
    workspace: Path,
    artifact_observation: dict[str, Any],
) -> dict[str, Any]:
    """Assess attributed production tool observations, never model completion prose."""

    def timed(log: ToolLog) -> bool:
        return (
            isinstance(log.request_index, int)
            and isinstance(log.result_index, int)
            and 0 <= log.request_index < log.result_index
        )

    def specialist(log: ToolLog) -> bool:
        return log.source_agent not in (None, "tech_lead", "orchestrator")

    edits = [
        log
        for log in logs
        if log.success and log.tool_name in _EDIT_TOOLS and _target(log, workspace) in _FIXTURES
    ]
    timed_edits = [log for log in edits if timed(log)]
    complete_timing = (
        bool(edits) and len(timed_edits) == len(edits) and artifact_observation["complete"]
    )
    first = min(
        (log.request_index for log in timed_edits if log.request_index is not None), default=-1
    )
    last = max(
        (log.result_index for log in timed_edits if log.result_index is not None), default=-1
    )
    actual_first = artifact_observation["first_implementation_change"]
    actual_last = artifact_observation["last_implementation_change"]
    if actual_first is not None:
        first = min(first, actual_first)
    if actual_last is not None:
        last = max(last, actual_last)
    before_edit = [
        log
        for log in logs
        if timed(log) and log.result_index is not None and log.result_index < first
    ]
    after_edit = [
        log
        for log in logs
        if timed(log) and log.request_index is not None and log.request_index > last
    ]
    inspected = complete_timing and all(
        any(specialist(log) and _inspected(log, workspace, name, symbol) for log in before_edit)
        for name, symbol in (
            ("normalization.py", "normalize_label"),
            ("label_index.py", "unique_labels"),
        )
    )
    engineer_files = {
        _target(log, workspace)
        for log in timed_edits
        if log.tool_name in {"edit_file", "write_file"} and log.source_agent == "engineer"
    }
    expected_heading = (
        "Test execution passed (4 collected, 4 executed; 4 passed, 0 failed, 0 skipped)"
    )
    verified = complete_timing and any(
        log.success
        and log.tool_name == "pytest_run"
        and _target(log, workspace) == "test_labels.py"
        and not any(log.arguments.get(option) for option in ("keyword", "markers", "collect_only"))
        and log.result.splitlines()[:1] == [expected_heading]
        for log in after_edit
    )
    reviewers = {
        log.source_agent for log in after_edit if specialist(log) and log.source_agent != "engineer"
    }
    reviewed = complete_timing and any(
        all(
            any(
                log.source_agent == reviewer and _inspected(log, workspace, name, symbol)
                for log in after_edit
            )
            for name, symbol in (("label_index.py", "unique_labels"), ("label_cli.py", "main"))
        )
        for reviewer in reviewers
    )
    protected_edits = artifact_observation["protected_change_observed"] or any(
        log.success and log.tool_name in _EDIT_TOOLS and _target(log, workspace) in _PROTECTED
        for log in logs
    )
    return {
        "artifact_observation": artifact_observation,
        "inspection_before_edit": inspected,
        "engineer_edit": {"label_index.py", "label_cli.py"} <= engineer_files,
        "post_edit_tests": verified,
        "independent_review": reviewed,
        "protected_edit_observed": protected_edits,
        "last_observed_edit": last if edits else None,
        "observations": [
            {
                "index": index,
                "source_agent": getattr(log, "source_agent", None),
                "tool_call_id": log.tool_call_id,
                "tool_name": log.tool_name,
                "request_index": log.request_index,
                "result_index": log.result_index,
                "success": log.success,
                "path": _target(log, workspace),
            }
            for index, log in enumerate(logs)
        ],
    }


async def run_team_python_workflow(
    rig: EvalTestRig,
    *,
    max_iterations: int = 25,
    timeout: float = 300,
) -> dict[str, Any]:
    """Return a JSON-safe report even when execution or independent checks fail."""
    report: dict[str, Any] = {
        "scenario": SCENARIO,
        "version": VERSION,
        "spec_digest": SPEC_DIGEST,
        "success": False,
        "task_verified": False,
        "runtime": {},
        "workflow": {},
        "checks": {},
        "fingerprints": {"initial": {}, "final": {}},
        "errors": [],
    }
    try:
        profile = rig.profile_metadata
        if profile.get("profile") != "team":
            raise ValueError("This scenario requires the production team evaluation profile")
        workspace = rig.test_dir
        for name, content in _FIXTURES.items():
            rig.create_file(name, content)
        initial = {name: _fingerprint(workspace / name) for name in _FIXTURES}
        report["fingerprints"]["initial"] = initial
        timeline = _ArtifactTimeline(workspace, initial)
        with patch.dict(
            os.environ,
            {
                "PYTHONOPTIMIZE": "0",
                "PYTEST_ADDOPTS": "",
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            },
        ):
            result = await rig.run(
                _PROMPT,
                max_iterations=max_iterations,
                timeout=timeout,
                observe_event=timeline,
            )
        artifact_observation = timeline.finish(len(result.events))
        report["runtime"] = {
            "success": result.success,
            "error": result.error,
            "final_response": result.final_response,
            "duration_ms": result.duration_ms,
            "profile": rig.profile_metadata,
            "tool_calls": len(result.tool_logs),
            "diagnostics": getattr(result, "diagnostics", []),
        }
        before_checks = {name: _fingerprint(workspace / name) for name in _FIXTURES}
        independent = await verify_team_python_outputs(workspace)
        final = {name: _fingerprint(workspace / name) for name in _FIXTURES}
        report["fingerprints"]["final"] = final
        workflow = assess_team_workflow(result.tool_logs, workspace, artifact_observation)
        report["workflow"] = workflow
        report["checks"] = {
            "artifact_observation_complete": _check(
                artifact_observation["complete"],
                (
                    "Incomplete or unreadable artifact snapshots"
                    if not artifact_observation["complete"]
                    else None
                ),
            ),
            "fixtures_unchanged": _check(
                not workflow["protected_edit_observed"]
                and all(final[name] == initial[name] for name in _PROTECTED),
                (
                    "Protected fixture changed"
                    if workflow["protected_edit_observed"]
                    or any(final[name] != initial[name] for name in _PROTECTED)
                    else None
                ),
            ),
            "implementation_changed": _check(
                all(
                    final[name] is not None and final[name] != initial[name]
                    for name in ("label_index.py", "label_cli.py")
                )
            ),
            "artifacts_stable_during_checks": _check(
                before_checks == final,
                "Artifacts changed during independent checks" if before_checks != final else None,
            ),
            **independent,
        }
        if not result.success:
            report["errors"].append(result.error or "Production team runtime failed")
        for name in (
            "inspection_before_edit",
            "engineer_edit",
            "post_edit_tests",
            "independent_review",
        ):
            if not workflow[name]:
                report["errors"].append(f"Missing workflow evidence: {name}")
        for name, check in report["checks"].items():
            if not check["success"]:
                report["errors"].append(
                    f"Independent check failed: {name}: {check['error'] or 'requirement not met'}"
                )
        report["success"] = not report["errors"]
    except Exception as exc:
        report["errors"].append(sanitize_error_message(f"{type(exc).__name__}: {exc}")[:8192])
    return report


@pytest.mark.skipif(
    os.environ.get("RUN_ALL_EVALS", "").lower() not in {"1", "true", "yes"}
    or os.environ.get("EVAL_PROFILE") != "team",
    reason="Opt in with RUN_ALL_EVALS=1 EVAL_PROFILE=team",
)
async def test_team_python_workflow() -> None:
    """Run real inference only when the team evaluation is explicitly selected."""
    rig = EvalTestRig(profile="team")
    try:
        rig.setup(SCENARIO)
        report = await run_team_python_workflow(rig)
        assert report["success"], json.dumps(report, indent=2)
    finally:
        rig.cleanup()
