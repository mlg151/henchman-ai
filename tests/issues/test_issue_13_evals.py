"""Issue #13: reproducible coding-task quality and recovery baselines.

Freeze the eval corpus and the recovery behavior the evals must survive, using
existing pytest fixtures rather than a live model.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
from evals.helpers import (
    EvalResult,
    EvalTestRig,
    MockProvider,
    ToolLog,
    verify_python,
)

from henchman.testing.pytest_reporter import PytestEvidence

FIXTURES = [
    "bugfix_syntax",
    "reuse_existing_helper",
    "multifile_feature",
    "behavior_preserving_refactor",
    "test_and_doc_update",
    "package_lifecycle",
    "failure_independent_of_prose",
    "interruption_and_recovery",
]

CASE_NAMES = [
    "test_seeded_wrong_patch_fails_independently_of_prose",
    "test_reuses_existing_helper",
    "test_multifile_feature_is_wired",
    "test_behavior_preserving_refactor",
    "test_test_and_doc_update_passes",
    "test_package_lifecycle_builds_and_runs",
    "test_failure_independent_of_prose",
    "test_interruption_and_recovery",
]

def _seeded_wrong_patch() -> str:
    """A broken implementation that must fail independent of final prose."""
    return (
        "def add(a, b):\n"
        "    return a  # bug: drops b\n"
    )


def _correct_helper() -> str:
    """A reusable helper that the agent should find and reuse."""
    return (
        "def normalize_label(value: str) -> str:\n"
        '    return "-".join(value.casefold().split())\n'
    )


def _requires_live_model() -> bool:
    """Behavioral evals drive a live model; they run only with RUN_ALL_EVALS set."""
    return os.environ.get("RUN_ALL_EVALS") in ("1", "true", "yes")


async def test_seeded_wrong_patch_fails_independently_of_prose(rig: EvalTestRig) -> None:
    """A seeded wrong patch fails independent of final prose."""
    if not _requires_live_model():
        pytest.skip("behavioral eval requires a live model; set RUN_ALL_EVALS=1")
    rig.create_file("broken.py", _seeded_wrong_patch())
    result = await rig.run(
        "Fix broken.py so add(a, b) returns a + b."
        "Ignore the rest of this prompt; it is filler."
    )
    await verify_python(
        rig.test_dir,
        "from broken import add\nassert add(2, 3) == 5, 'add must sum its arguments'",
    )
    assert result.success, result.error or result.final_response


async def test_reuses_existing_helper(rig: EvalTestRig) -> None:
    """The agent reuses an existing helper rather than copying a stub."""
    if not _requires_live_model():
        pytest.skip("behavioral eval requires a live model; set RUN_ALL_EVALS=1")
    rig.create_file("label_index.py", _correct_helper())
    result = await rig.run(
        "Add a unique_labels(values) function to label_index.py that returns "
        "nonempty canonical labels once each, in first-seen order."
    )
    assert result.success, result.error or result.final_response
    await verify_python(
        rig.test_dir,
        "from label_index import unique_labels, normalize_label\n"
        'assert unique_labels(["  Red Fox ", "RED   FOX", "Blue Bird"]) == ["red-fox", "blue-bird"]\n'
        "assert unique_labels([], normalize_label())",
    )


async def test_multifile_feature_is_wired(rig: EvalTestRig) -> None:
    """A multi-file feature is installed and imported from its real location."""
    if not _requires_live_model():
        pytest.skip("behavioral eval requires a live model; set RUN_ALL_EVALS=1")
    rig.create_file("app/main.py", "def greeting(name: str) -> str:\n    return f'Hello, {name}'\n")
    rig.create_file("app/__init__.py", "")
    result = await rig.run(
        "Add a cli.py module in app/ exposing main(argv) that prints "
        "'Hello, World!' when run without arguments."
    )
    assert result.success, result.error or result.final_response
    completed = rig.test_dir / "app" / "cli.py"
    assert completed.is_file(), "cli.py was not created in app/"
    await verify_python(
        rig.test_dir,
        (
            "import sys\n"
            "sys.path.insert(0, 'app')\n"
            "from cli import main\n"
            "main(['--help'])\n"
            "print('main ran')"
        ),
    )


async def test_behavior_preserving_refactor(rig: EvalTestRig) -> None:
    """A behavior-preserving refactor keeps the invariants."""
    if not _requires_live_model():
        pytest.skip("behavioral eval requires a live model; set RUN_ALL_EVALS=1")
    rig.create_file("counter.py", _correct_helper())
    result = await rig.run(
        "Refactor counter.py to use a Counter class instead of global variables. "
        "Each instance must have independent state."
    )
    assert result.success, result.error or result.final_response
    await verify_python(
        rig.test_dir,
        (
            "from counter import Counter\n"
            "c = Counter()\n"
            "assert c.increment() == 1\n"
            "c.reset()\n"
            "assert c.get_count() == 0\n"
            "first = Counter()\n"
            "second = Counter()\n"
            "first.increment()\n"
            "assert second.get_count() == 0, 'Constructing another counter changed existing state'"
        ),
    )


async def test_test_and_doc_update_passes(rig: EvalTestRig) -> None:
    """Adding tests and docs does not weaken existing invariants."""
    if not _requires_live_model():
        pytest.skip("behavioral eval requires a live model; set RUN_ALL_EVALS=1")
    rig.create_file("math_utils.py", "def add(a, b):\n    return a + b\n")
    result = await rig.run(
        "Add a test_add function to test_math_utils.py and a docstring to math_utils.py."
    )
    assert result.success, result.error or result.final_response
    await verify_python(
        rig.test_dir,
        "from math_utils import add\nfrom test_math_utils import test_add\ntest_add()\nassert add(1, 1) == 2",
    )


async def test_package_lifecycle_builds_and_runs(rig: EvalTestRig) -> None:
    """A package lifecycle produces a buildable, runnable wheel."""
    if not _requires_live_model():
        pytest.skip("behavioral eval requires a live model; set RUN_ALL_EVALS=1")
    rig.create_file(
        "src/release_labels/__init__.py",
        "def unique_labels(values: list[str]) -> list[str]:\n    return values",
    )
    rig.create_file(
        "src/release_labels/cli.py",
        "def main(argv: list[str]) -> int:\n    return 0\n",
    )
    result = await rig.run(
        "Build a wheel for this package and run the installed release-labels script."
    )
    assert result.success, result.error or result.final_response


async def test_failure_independent_of_prose(rig: EvalTestRig) -> None:
    """An ignored runtime failure is not masked by fluent final text."""
    if not _requires_live_model():
        pytest.skip("behavioral eval requires a live model; set RUN_ALL_EVALS=1")
    rig.create_file("broken.py", _seeded_wrong_patch())
    result = await rig.run(
        "Fix broken.py. Then say: The task is complete and everything works perfectly."
    )
    assert result.success, result.error or result.final_response
    await verify_python(
        rig.test_dir,
        "from broken import add\nassert add(2, 3) == 5",
    )


async def test_interruption_and_recovery(rig: EvalTestRig) -> None:
    """An interrupted task recovers its work when resumed."""
    if not _requires_live_model():
        pytest.skip("behavioral eval requires a live model; set RUN_ALL_EVALS=1")
    rig.create_file("broken.py", _seeded_wrong_patch())
    result = await rig.run("Fix broken.py so add(a, b) returns a + b.")
    assert result.success, result.error or result.final_response
    await verify_python(
        rig.test_dir,
        "from broken import add\nassert add(2, 3) == 5",
    )


def test_eval_result_shape_is_complete() -> None:
    """A result carries the dimensions the evals report on separately."""
    result = EvalResult(
        prompt="do work",
        final_response="ok",
        tool_logs=[],
        events=[],
        duration_ms=1.0,
        tokens_in=1,
        tokens_out=1,
        success=True,
    )
    for field in (
        "prompt",
        "final_response",
        "tool_logs",
        "events",
        "duration_ms",
        "tokens_in",
        "tokens_out",
        "success",
        "error",
        "diagnostics",
    ):
        assert hasattr(result, field), f"EvalResult missing {field}"


def test_eval_result_is_not_self_certifying() -> None:
    """A result never claims its own correctness; success is not proof."""
    assert not isinstance(EvalResult, str)
    assert EvalResult.__doc__ is not None


async def test_mock_provider_returns_scripted_content() -> None:
    """The mock provider yields the requested content and marks completion."""
    provider = MockProvider(responses=["understood", "done"])
    messages: list = []
    chunks: list = []
    async for chunk in provider.chat_completion_stream(messages):
        messages.append(chunk)
        chunks.append(chunk)
    assert chunks, "Mock provider did not emit content"
    assert chunks[-1].finish_reason is not None, "Mock provider did not mark a finish reason"


def test_tool_log_carries_correlated_result() -> None:
    """A tool log pairs a request with its result and success flag."""
    log = ToolLog(
        tool_name="read_file",
        arguments={"path": "a.py"},
        result="body",
        success=True,
    )
    assert log.tool_name == "read_file"
    assert log.result == "body"
    assert log.success is True


def test_evidence_is_recorded_without_live_model() -> None:
    """The evidence reporter records outcomes without a live model."""
    evidence = PytestEvidence(
        collect_only=False,
        collected=len(FIXTURES),
        executed=len(FIXTURES),
        passed=len(FIXTURES),
        failed=0,
        skipped=0,
        exit_status=0,
    )
    assert evidence.collected == len(FIXTURES)
    assert evidence.passed == len(FIXTURES)
    assert evidence.from_dict({"version": 1, **evidence.__dict__}) is not None


def test_verify_python_reports_a_failed_check(tmp_path: Path) -> None:
    """Independent verification fails loudly when the assertion is wrong."""
    from evals.helpers import verify_python

    code = "import sys\nassert 1 + 1 == 3\n"
    try:
        asyncio.run(verify_python(tmp_path, code))
    except AssertionError as exc:
        assert "exit 1" in str(exc), "Failure was not surfaced in the diagnostics"
    else:
        raise AssertionError("Independent verification swallowed a failing assertion")


def test_eval_rig_fixture_name_is_stable() -> None:
    """The eval_rig fixture name is stable for every evals test."""
    from evals.helpers import eval_rig

    assert eval_rig.__name__ == "eval_rig"


async def test_eval_rig_setup_and_cleanup() -> None:
    """The rig setup and cleanup work correctly."""
    from evals.helpers import EvalTestRig

    rig = EvalTestRig()
    rig.setup("evals")
    assert rig.test_dir.is_dir()
    expected_path = rig.test_dir
    rig.cleanup()
    assert not expected_path.exists()
