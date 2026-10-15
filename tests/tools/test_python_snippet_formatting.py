"""Snippet formatting cannot scan a workspace or prevent Python execution."""

from __future__ import annotations

import asyncio
import logging
import re
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from henchman.advanced.tasks import TaskService
from henchman.tools import formatting
from henchman.tools.builtins import python_exec
from henchman.tools.builtins.python_exec import PythonExecTool
from henchman.tools.registry import ToolRegistry


@pytest.mark.parametrize("background", [False, True])
async def test_large_workspace_executes_without_source_tracking(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    background: bool,
) -> None:
    """Both runtime routes execute even beyond the workspace formatter's limit."""
    for index in range(5001):
        (tmp_path / f"module_{index}.py").touch()
    (tmp_path / "pyproject.toml").write_text('[tool.black]\nline-length = "invalid"\n')
    monkeypatch.chdir(tmp_path)

    def forbid_tracking(*_args: object, **_kwargs: object) -> None:
        pytest.fail("python_exec must never traverse workspace sources")

    monkeypatch.setattr(formatting, "_snapshot", forbid_tracking)
    registry = ToolRegistry()
    tool = PythonExecTool()
    registry.register(tool)
    result = await registry.execute(
        "python_exec",
        {
            "code": "from pathlib import Path; Path('generated.py').write_text('x=1\\n'); print('done')",
            "cwd": str(tmp_path),
            "background": background,
        },
    )
    assert result.success, result.content
    if background:
        match = re.search(r"task-[0-9a-f]+", result.content)
        assert match is not None
        service = TaskService(tmp_path)
        record = await service.wait_for_task(match.group(), timeout=5)
        assert record.status == "completed"
        assert "done" in service.tail_output(record.task_id)
    else:
        assert "done" in result.content
    assert (tmp_path / "generated.py").read_text() == "x=1\n"


async def test_snippet_uses_black_defaults_and_ignores_project_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Black formats only the string, without searching for workspace settings."""
    from henchman.tools.snippet_formatting import format_python_snippet

    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text('[tool.black]\nline-length = "invalid"\n')
    (tmp_path / "black.py").write_text("raise RuntimeError('workspace module imported')\n")
    assert await format_python_snippet("values= [1,2]\n") == "values = [1, 2]\n"


@pytest.mark.parametrize("background", [False, True])
async def test_formatted_snippet_reaches_both_execution_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    background: bool,
) -> None:
    """Formatting precedes dispatch, including direct tool usage."""
    formatted = "print(42)\n"
    formatter = AsyncMock(return_value=formatted)
    monkeypatch.setattr(python_exec, "format_python_snippet", formatter)
    tool = PythonExecTool()
    tool.bind_runtime(project_root=tmp_path)
    if background:
        start = AsyncMock()
        start.return_value.task_id, start.return_value.status = "task-test", "running"
        monkeypatch.setattr(TaskService, "start_task", start)
    else:
        run = AsyncMock()
        monkeypatch.setattr(python_exec, "_run_python_subprocess", run)
    await tool.execute(code="print( 42 )", background=background)
    formatter.assert_awaited_once_with("print( 42 )")
    if background:
        assert start.call_args.kwargs["argv"][-1] == formatted
    else:
        assert run.call_args.args[0].code == formatted


@pytest.mark.parametrize("failure", ["missing", "crash", "truncated", "empty"])
@pytest.mark.parametrize("background", [False, True])
async def test_formatter_failure_executes_original_with_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    failure: str,
    tmp_path: Path,
    background: bool,
) -> None:
    """No formatter malfunction can turn valid execution into a tool error."""
    from henchman.tools import snippet_formatting
    from henchman.tools.subprocess_utils import BoundedProcessResult

    backend = AsyncMock()
    if failure == "missing":
        backend.side_effect = FileNotFoundError("Black unavailable")
    else:
        backend.return_value = BoundedProcessResult(
            stdout=b"partial" if failure == "truncated" else b"",
            stderr=b"formatter failed",
            returncode=1 if failure == "crash" else 0,
            stdout_truncated=failure == "truncated",
            stderr_truncated=False,
        )
    monkeypatch.setattr(snippet_formatting, "run_bounded_subprocess", backend)
    tool = PythonExecTool()
    tool.bind_runtime(project_root=tmp_path)
    with caplog.at_level(logging.WARNING):
        result = await tool.execute(code="print('original executed')", background=background)
    assert result.success, result.content
    if background:
        match = re.search(r"task-[0-9a-f]+", result.content)
        assert match is not None
        service = TaskService(tmp_path)
        record = await service.wait_for_task(match.group(), timeout=5)
        assert record.status == "completed"
        assert "original executed" in service.tail_output(record.task_id)
    else:
        assert "original executed" in result.content
    assert "Black snippet formatting" in caplog.text
    assert "original" in caplog.text


async def test_formatter_timeout_falls_back_under_half_second_and_reaps_child(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A stalled worker is terminated; formatting does not wait for its sleep."""
    from henchman.tools import snippet_formatting

    marker = tmp_path / "late-worker-output"
    worker = "import pathlib,sys,time; time.sleep(1); pathlib.Path(sys.argv[1]).touch()"
    monkeypatch.setattr(
        snippet_formatting,
        "_BLACK_SNIPPET_COMMAND",
        [
            sys.executable,
            "-I",
            "-c",
            worker,
            str(marker),
        ],
    )
    original = "print('fallback')"
    start = time.monotonic()
    with caplog.at_level(logging.WARNING):
        assert await snippet_formatting.format_python_snippet(original) == original
    assert time.monotonic() - start < 0.5
    assert "timeout" in caplog.text.lower()
    await asyncio.sleep(1.05)
    assert not marker.exists()


async def test_invalid_python_preserves_execution_syntax_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        result = await PythonExecTool().execute(code="def broken(", background=False)
    assert not result.success
    assert "SyntaxError" in result.content
    assert "Black snippet formatting" in caplog.text


async def test_large_snippet_skips_formatter_without_preventing_execution(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The formatting input bound must not become an execution input bound."""
    from henchman.tools import snippet_formatting

    backend = AsyncMock()
    monkeypatch.setattr(snippet_formatting, "run_bounded_subprocess", backend)
    code = "#" + "x" * snippet_formatting.MAX_SNIPPET_BYTES + "\nprint('large snippet ran')"
    with caplog.at_level(logging.WARNING):
        result = await PythonExecTool().execute(code=code, background=False)
    assert result.success, result.content
    assert "large snippet ran" in result.content
    assert "formatting limit" in caplog.text
    backend.assert_not_awaited()


async def test_formatter_cancellation_prevents_snippet_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    formatter = AsyncMock(side_effect=asyncio.CancelledError)
    run = AsyncMock()
    monkeypatch.setattr(python_exec, "format_python_snippet", formatter)
    monkeypatch.setattr(python_exec, "_run_python_subprocess", run)
    with pytest.raises(asyncio.CancelledError):
        await PythonExecTool().execute(code="print('never')", background=False)
    run.assert_not_awaited()


@pytest.mark.parametrize("background", [False, True])
async def test_expanded_snippet_uses_original_before_exceeding_process_argument_limits(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    background: bool,
) -> None:
    """Black expansion must not turn a small executable argv into an oversized one."""
    import black

    from henchman.tools import snippet_formatting
    from henchman.tools.subprocess_utils import BoundedProcessResult

    original = "values = " + "[" * 100 + "0," * 10 + "]" * 100
    expanded = black.format_str(original, mode=black.Mode()).encode("utf-8")
    assert len(expanded) > 32767
    backend = AsyncMock(return_value=BoundedProcessResult(expanded, b"", 0, False, False))
    monkeypatch.setattr(snippet_formatting, "run_bounded_subprocess", backend)
    tool = PythonExecTool()
    tool.bind_runtime(project_root=tmp_path)
    if background:
        start = AsyncMock()
        start.return_value.task_id, start.return_value.status = "task-test", "running"
        monkeypatch.setattr(TaskService, "start_task", start)
    else:
        run = AsyncMock()
        monkeypatch.setattr(python_exec, "_run_python_subprocess", run)

    with caplog.at_level(logging.WARNING):
        await tool.execute(code=original, background=background)
    if background:
        assert start.call_args.kwargs["argv"][-1] == original
    else:
        assert run.call_args.args[0].code == original
    assert "formatting limit" in caplog.text
