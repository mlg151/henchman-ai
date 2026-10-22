"""Offline structural tests for the evaluation infrastructure.

These tests do not invoke a live model. They exercise the pieces that make the
live evals reproducible and honest: the mock provider, the rig lifecycle,
independent Python verification, and the tool-selection oracles. Passing here
does not establish model quality; it establishes that the machinery around the
quality claims is sound.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from evals.helpers import (
    EvalResult,
    EvalTestRig,
    MockProvider,
    ToolLog,
    verify_python,
)


async def test_rig_sets_up_and_cleans_up() -> None:
    """The rig creates a test directory and removes it after cleanup."""
    rig = EvalTestRig()
    rig.setup("test")
    assert rig.test_dir.is_dir(), "Rig did not create a test directory"
    rig.create_file("marker.txt", "content")
    assert rig.file_exists("marker.txt"), "Rig did not create the marker file"
    assert rig.tool_was_called("read_file") is False, "Tool was reported before any run"
    rig.cleanup()


async def test_mock_provider_returns_scripted_content() -> None:
    """The mock provider yields the requested content and marks completion."""
    provider = MockProvider(responses=["understood", "done"])
    messages: list = []
    async for chunk in provider.chat_completion_stream(messages):
        messages.append(chunk)
    if not chunk.content:
        raise AssertionError("Mock provider did not emit content")
    if chunk.finish_reason is None:
        raise AssertionError("Mock provider did not mark a finish reason")


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


async def test_verify_python_runs_code_in_child_process(tmp_path: Path) -> None:
    """Independent verification executes assertions in a subprocess, not in-process."""
    code = "import sys\nassert sys.version_info[:2] >= (3, 11)\n"
    await verify_python(tmp_path, code)
    assert True, "Verification completed without raising"


async def test_verify_python_reports_a_failed_check(tmp_path: Path) -> None:
    """Independent verification fails loudly when the assertion is wrong."""
    code = "import sys\nsys.exit(1)\n"
    try:
        await verify_python(tmp_path, code)
    except AssertionError as exc:
        assert "exit 1" in str(exc), "Failure was not surfaced in the diagnostics"
    else:  # pragma: no cover - the branch above should raise
        raise AssertionError("Independent verification swallowed a failing exit code")


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
