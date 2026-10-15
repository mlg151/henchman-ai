"""Live-model evaluation: inspect and reuse an existing Python helper."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

from evals.helpers import EvalResult, EvalTestRig, ToolLog, eval_test
from henchman.testing.pytest_reporter import PytestEvidence

_NORMALIZATION = '''def normalize_label(value: str) -> str:
    """Canonical project labels: casefold and join whitespace with hyphens."""
    return "-".join(value.casefold().split())
'''

_CALLER = '''def unique_labels(values: list[str]) -> list[str]:
    """Return nonempty canonical labels once each, in first-seen order."""
    raise NotImplementedError("Reuse the project's existing normalizer")
'''

_TESTS = '''import importlib
from unittest.mock import patch
import label_index


def test_normalization_and_duplicates():
    assert label_index.unique_labels(["  Red Fox ", "RED   FOX", "Blue Bird"]) == ["red-fox", "blue-bird"]


def test_empty_order_and_unicode():
    assert label_index.unique_labels(["", " ", "Zoo", "Straße", "STRASSE", "Apple"]) == ["zoo", "strasse", "apple"]
    assert label_index.unique_labels([]) == []


def test_input_unchanged():
    values = [" B ", "A", "b"]
    before = list(values)
    assert label_index.unique_labels(values) == ["b", "a"]
    assert values == before


def test_calls_existing_helper():
    calls = []
    def existing(value):
        calls.append(value)
        return {"one": "shared", "two": "shared", "three": "other"}[value]
    with patch("normalization.normalize_label", existing):
        importlib.reload(label_index)
        assert label_index.unique_labels(["one", "two", "three"]) == ["shared", "other"]
        assert calls == ["one", "two", "three"]
    importlib.reload(label_index)
'''


def _targets_caller(log: ToolLog) -> bool:
    """Identify real file edits to the caller rather than claims in prose."""
    return (
        log.success
        and log.tool_name in {"edit_file", "write_file"}
        and Path(str(log.arguments.get("path", ""))).name == "label_index.py"
    )


def verify_python_reuse(workspace: Path) -> None:
    """Run the unchanged tests independently, requiring four real passed calls."""
    report = workspace / "independent-verification.json"
    command = [
        sys.executable, "-m", "pytest", "-q", "-o", "addopts=",
        "-p", "henchman.testing.pytest_reporter", "--henchman-report", str(report),
        "--", "test_labels.py",
    ]
    environment = {
        **os.environ,
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTEST_ADDOPTS": "",
        "PYTHONIOENCODING": "utf-8",
    }
    completed = subprocess.run(
        command, cwd=workspace, env=environment,
        capture_output=True, text=True, encoding="utf-8", timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    evidence = PytestEvidence.load(report)
    assert evidence is not None, "Independent pytest run produced no execution evidence"
    assert not evidence.collect_only
    assert evidence.executed == evidence.passed == 4
    assert evidence.failed == evidence.skipped == evidence.exit_status == 0


async def run_python_reuse_scenario(rig: EvalTestRig) -> EvalResult:
    """Execute the same live-provider scenario through pytest or an explicit rig."""
    helper = rig.create_file("normalization.py", _NORMALIZATION)
    caller = rig.create_file("label_index.py", _CALLER)
    tests = rig.create_file("test_labels.py", _TESTS)
    helper_before, caller_before, tests_before = helper.read_bytes(), caller.read_bytes(), tests.read_bytes()
    pytest_argv = [sys.executable, "-m", "pytest", "-q", "test_labels.py"]
    pytest_command = subprocess.list2cmdline(pytest_argv) if os.name == "nt" else shlex.join(pytest_argv)

    result = await rig.run(
        "Inspect the Python files in this directory before editing. Implement "
        "unique_labels in label_index.py by calling the existing normalize_label "
        "helper from normalization.py for each input. Return nonempty canonical "
        "labels without duplicates, preserving first-seen order and not changing "
        "the input list. Reuse the helper; do not copy its implementation. Keep "
        "normalization.py and test_labels.py unchanged. Use edit_file or write_file "
        f"to change label_index.py, then run {pytest_command} and "
        "report what you verified.",
        max_iterations=12,
        timeout=300,
    )
    assert result.success, result.error or result.final_response
    assert helper.read_bytes() == helper_before, "The reusable helper was changed"
    assert tests.read_bytes() == tests_before, "Provided tests were changed"
    assert caller.read_bytes() != caller_before, "Caller was not implemented"

    edits = [index for index, log in enumerate(result.tool_logs) if _targets_caller(log)]
    assert edits, "No successful caller edit was observed"
    assert any(
        log.success and log.tool_name in {"read_file", "grep"}
        and "def normalize_label" in log.result
        for log in result.tool_logs[:edits[0]]
    ), "Existing helper was not inspected before implementation"
    assert any(
        log.success and re.search(r"\b4 passed\b", log.result) and (
            log.tool_name == "pytest_run"
            or (log.tool_name == "shell" and "pytest" in str(log.arguments.get("command", "")))
        )
        for log in result.tool_logs[edits[-1] + 1:]
    ), "No successful pytest verification followed the final edit"
    verify_python_reuse(rig.test_dir)
    return result


@eval_test("USUALLY_PASSES")
async def test_reuses_existing_python_helper(rig: EvalTestRig) -> None:
    """Live models must inspect, reuse, edit, and independently pass behavior checks."""
    await run_python_reuse_scenario(rig)
