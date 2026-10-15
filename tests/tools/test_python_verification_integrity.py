"""Python checks report executed work and clean up interrupted processes."""

from __future__ import annotations

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.tools.builtins.lint_check import LintCheckTool, _run_linter_command
from henchman.tools.builtins.pytest_run import PytestRunTool, _run_pytest_subprocess


@pytest.mark.parametrize("target", ["--version", "--help", " "])
async def test_pytest_rejects_targets_that_cannot_execute_tests(target):
    result = await PytestRunTool().execute(path=target)
    assert not result.success
    assert result.error


@pytest.mark.parametrize("linter", ["pyright", "", "RUFF"])
async def test_lint_rejects_unknown_checker(tmp_path, linter):
    result = await LintCheckTool().execute(path=str(tmp_path), linter=linter)
    assert not result.success
    assert "linter" in result.content.lower()


@pytest.mark.parametrize("options", [
    {"timeout": -1}, {"timeout": "oops"}, {"timeout": True},
    {"parallel": 0}, {"parallel": -1}, {"parallel": "oops"},
    {"collect_only": "false"}, {"coverage": "false"}, {"verbose": "true"},
])
async def test_pytest_invalid_options_return_failure_without_launch(options):
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as launch:
        result = await PytestRunTool().execute(path="tests/", **options)
    assert not result.success
    assert result.error
    launch.assert_not_called()


async def test_real_pytest_reports_run_collection_and_empty_selection(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    test_path = tmp_path / "test_sample.py"
    test_path.write_text("def test_ok():\n    assert True\n\ndef test_bad():\n    assert False\n")
    tool = PytestRunTool()
    passed = await tool.execute(path=f"{test_path}::test_ok", verbose=True)
    failed = await tool.execute(path=f"{test_path}::test_bad")
    collected = await tool.execute(path=str(test_path), collect_only=True)
    empty = await tool.execute(path=str(test_path), keyword="no_such_test")

    assert passed.success and "Test execution passed" in passed.content
    assert not failed.success and "1 failed" in failed.content
    assert collected.success and "no tests were executed" in collected.content.lower()
    assert "test_ok" in collected.content and "test_bad" in collected.content
    assert not empty.success and "No tests" in empty.error


@pytest.mark.parametrize("source", ["environment", "project"])
@pytest.mark.parametrize("option", ["--collect-only", "--version"])
async def test_configured_pytest_early_exit_is_not_reported_as_execution(tmp_path, monkeypatch, source, option):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "test_sample.py"
    path.write_text(
        "from pathlib import Path\ndef test_ok():\n"
        "    Path(__file__).with_suffix('.ran').write_text('executed')\n",
    )
    if source == "environment":
        monkeypatch.setenv("PYTEST_ADDOPTS", option)
    else:
        (tmp_path / "pytest.ini").write_text(f"[pytest]\naddopts = {option}\n")

    result = await PytestRunTool().execute(path=str(path))

    if option == "--collect-only":
        assert not result.success
        assert "Test execution passed" not in result.content
        assert result.error
    else:
        # Pytest versions can process inherited --version without an early exit.
        assert result.success == path.with_suffix(".ran").exists()


async def test_all_setup_skipped_is_not_execution_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "test_skip.py"
    path.write_text("import pytest\n@pytest.mark.skip(reason='not available')\ndef test_skip():\n    pass\n")
    result = await PytestRunTool().execute(path=str(path))
    assert not result.success
    assert "no tests were executed" in result.content.lower()


async def test_all_runtime_skipped_is_not_passing_verification(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "test_skip.py"
    path.write_text("import pytest\ndef test_skip():\n    pytest.skip('not available')\n")
    result = await PytestRunTool().execute(path=str(path))
    assert not result.success
    assert "0 passed" in result.content and "1 skipped" in result.content


async def test_zero_exit_without_execution_evidence_is_unverified():
    with patch(
        "henchman.tools.builtins.pytest_run._run_pytest_subprocess",
        AsyncMock(return_value=(b"Everything passed!", b"", 0)),
    ):
        result = await PytestRunTool().execute(path="tests")
    assert not result.success
    assert "evidence" in result.error.lower()


async def test_missing_report_preserves_original_pytest_failure():
    with patch(
        "henchman.tools.builtins.pytest_run._run_pytest_subprocess",
        AsyncMock(return_value=(b"", b"No module named pytest", 1)),
    ):
        result = await PytestRunTool().execute(path="tests")
    assert not result.success
    assert "exit code 1" in result.error
    assert "No module named pytest" in result.content


async def test_verification_preserves_project_configured_junit_artifact(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pytest.ini").write_text("[pytest]\naddopts = --junitxml=ci-results.xml\n")
    path = tmp_path / "test_sample.py"
    path.write_text("def test_ok():\n    assert True\n")

    result = await PytestRunTool().execute(path=str(path))

    assert result.success
    artifact = tmp_path / "ci-results.xml"
    assert artifact.exists()
    assert 'name="test_ok"' in artifact.read_text()


@pytest.mark.parametrize("runner", ["pytest", "lint"])
async def test_timeout_terminates_and_reaps_child(runner):
    process = MagicMock()
    process.returncode = None
    process.communicate = AsyncMock(side_effect=TimeoutError())
    process.wait = AsyncMock(return_value=0)
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
        if runner == "pytest":
            with pytest.raises(TimeoutError):
                await _run_pytest_subprocess([sys.executable], timeout=1)
        else:
            success, message = await _run_linter_command([sys.executable], "ruff")
            assert not success and "Timed out" in message
    assert process.terminate.called or process.kill.called
    process.wait.assert_awaited()


@pytest.mark.parametrize("runner", ["pytest", "lint"])
async def test_cancellation_cleans_up_and_preserves_cancellation(runner):
    process = MagicMock()
    process.returncode = None
    process.communicate = AsyncMock(side_effect=asyncio.CancelledError("original cancel"))
    process.wait = AsyncMock(return_value=0)
    with (
        patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)),
        pytest.raises(asyncio.CancelledError, match="original cancel"),
    ):
        if runner == "pytest":
            await _run_pytest_subprocess([sys.executable], timeout=1)
        else:
            await _run_linter_command([sys.executable], "ruff")
    assert process.terminate.called or process.kill.called
    process.wait.assert_awaited()


async def test_python_child_output_is_utf8_even_with_non_utf8_parent_environment(monkeypatch):
    monkeypatch.setenv("PYTHONIOENCODING", "ascii")
    stdout, stderr, returncode = await _run_pytest_subprocess(
        [sys.executable, "-c", "print('caf\\u00e9')"], timeout=5,
    )
    assert returncode == 0, stderr
    assert stdout.decode("utf-8").strip() == "café"


async def test_missing_checker_reports_failure():
    success, output = await _run_linter_command([sys.executable, "-S", "-m", "ruff"], "ruff")
    assert not success
    assert "No module named ruff" in output


async def test_real_cancellation_reaps_child_before_returning(monkeypatch):
    created = []
    started = asyncio.Event()
    create = asyncio.create_subprocess_exec

    async def capture(*args, **kwargs):
        process = await create(*args, **kwargs)
        created.append(process)
        started.set()
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", capture)
    task = asyncio.create_task(_run_pytest_subprocess(
        [sys.executable, "-c", "import time; time.sleep(30)"], timeout=0,
    ))
    await asyncio.wait_for(started.wait(), timeout=5)
    task.cancel("user stopped verification")
    with pytest.raises(asyncio.CancelledError, match="user stopped verification"):
        await task
    assert created[0].returncode is not None


async def test_cleanup_escalates_and_closes_inherited_output_pipes():
    process = MagicMock()
    process.returncode = None
    process.communicate = AsyncMock(side_effect=TimeoutError())
    process.wait = AsyncMock(side_effect=[TimeoutError(), 0])
    with (
        patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)),
        pytest.raises(TimeoutError),
    ):
        await _run_pytest_subprocess([sys.executable], timeout=1)
    process.terminate.assert_called_once()
    process.kill.assert_called_once()
    assert process.wait.await_count == 2
    assert process._transport.get_pipe_transport.return_value.close.call_count == 2


async def test_cleanup_error_does_not_mask_original_cancellation():
    process = MagicMock()
    process.returncode = None
    process.communicate = AsyncMock(side_effect=asyncio.CancelledError("original"))
    process.terminate.side_effect = OSError("cleanup failed")
    with (
        patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)),
        pytest.raises(asyncio.CancelledError, match="original"),
    ):
        await _run_pytest_subprocess([sys.executable], timeout=1)


async def test_cancelled_cleanup_task_does_not_retry_forever():
    process = MagicMock()
    process.communicate = AsyncMock(side_effect=asyncio.CancelledError("original"))
    with (
        patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)),
        patch("henchman.tools.subprocess_utils._stop_subprocess", AsyncMock(side_effect=asyncio.CancelledError())),
        pytest.raises(asyncio.CancelledError, match="original"),
    ):
        await asyncio.wait_for(_run_pytest_subprocess([sys.executable], timeout=1), timeout=2)


@pytest.mark.skipif(os.name == "nt", reason="SIGTERM resistance exercises the POSIX kill fallback")
async def test_real_timeout_kills_resistant_child_and_reaps(monkeypatch):
    created = []
    create = asyncio.create_subprocess_exec

    async def capture(*args, **kwargs):
        process = await create(*args, **kwargs)
        created.append(process)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", capture)
    with pytest.raises(TimeoutError):
        await _run_pytest_subprocess([
            sys.executable, "-c",
            "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)",
        ], timeout=1)
    assert len(created) == 1
    assert created[0].returncode is not None
