"""Automatic Black formatting follows actual mutations, not all dirty files."""

import asyncio
import os
import subprocess
import venv
from pathlib import Path

import pytest

from henchman.tools import formatting
from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.builtins.file_edit import EditFileTool
from henchman.tools.builtins.file_read import ReadFileTool
from henchman.tools.builtins.file_write import WriteFileTool
from henchman.tools.builtins.python_exec import PythonExecTool
from henchman.tools.formatting import PythonAutoFormatter
from henchman.tools.registry import ToolRegistry


async def test_write_formats_only_explicit_source_even_outside_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    untouched = workspace / "dirty.py"
    untouched.write_text("dirty=  1\n")
    target = tmp_path / "outside.py"
    tool = WriteFileTool()
    result = await PythonAutoFormatter().run(
        tool,
        {"path": str(target)},
        lambda: tool.execute(path=str(target), content="answer=  42\n"),
    )
    assert result.success, result.content
    assert target.read_text() == "answer = 42\n"
    assert untouched.read_text() == "dirty=  1\n"
    assert "Black" in result.content


async def test_edit_honors_project_black_configuration(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.black]\nskip-string-normalization = true\n")
    target = tmp_path / "source.py"
    target.write_text("label = 'old'\n")
    tool = EditFileTool()
    result = await PythonAutoFormatter().run(
        tool,
        {"path": str(target)},
        lambda: tool.execute(path=str(target), old_str="'old'", new_str="  'new'"),
    )
    assert result.success, result.content
    assert target.read_text() == "label = 'new'\n"
    assert "Black" in result.content


async def test_command_created_sources_are_formatted_but_caches_and_venvs_are_not(
    tmp_path: Path,
) -> None:
    (tmp_path / "dirty.py").write_text("untouched=  1\n")
    (tmp_path / "custom-env").mkdir()
    (tmp_path / "custom-env" / "pyvenv.cfg").write_text("home = example\n")
    tool = PythonExecTool()
    code = (
        "from pathlib import Path\n"
        "Path('created.py').write_text('answer=  42\\n')\n"
        "Path('types.pyi').write_text('answer:int\\n')\n"
        "Path('custom-env/ignored.py').write_text('untouched=  1\\n')\n"
        "Path('__pycache__').mkdir()\n"
        "Path('__pycache__/ignored.py').write_text('untouched=  1\\n')\n"
    )
    result = await PythonAutoFormatter().run(
        tool, {"background": False, "cwd": str(tmp_path)}, lambda: tool.execute(background=False, code=code, cwd=str(tmp_path))
    )
    assert result.success, result.content
    assert (tmp_path / "created.py").read_text() == "answer = 42\n"
    assert (tmp_path / "types.pyi").read_text() == "answer: int\n"
    for name in ("dirty.py", "custom-env/ignored.py", "__pycache__/ignored.py"):
        assert (tmp_path / name).read_text() == "untouched=  1\n"


@pytest.mark.parametrize("failure", ["syntax", "config"])
async def test_black_failure_is_not_successful_tool_completion(
    tmp_path: Path, failure: str
) -> None:
    target = tmp_path / "source.py"
    if failure == "config":
        (tmp_path / "pyproject.toml").write_text('[tool.black]\nline-length = "invalid"\n')
    code = "def broken(:\n" if failure == "syntax" else "answer=  42\n"
    tool = WriteFileTool()
    result = await PythonAutoFormatter().run(
        tool, {"path": str(target)}, lambda: tool.execute(path=str(target), content=code)
    )
    assert not result.success
    assert "Black" in result.content
    assert result.error and "Black" in result.error
    assert "Successfully wrote" in result.content
    assert target.read_text() == code


async def test_partial_write_failure_preserves_diagnostics_and_formats(tmp_path: Path) -> None:
    target = tmp_path / "partial.py"

    async def execute() -> ToolResult:
        target.write_text("answer=  42\n")
        return ToolResult("original failure", False, display="display", error="original error")

    result = await PythonAutoFormatter().run(WriteFileTool(), {"path": str(target)}, execute)
    assert not result.success
    assert result.content.startswith("original failure")
    assert result.error == "original error"
    assert result.display == "display"
    assert target.read_text() == "answer = 42\n"


async def test_exception_after_partial_write_is_preserved_and_source_formatted(
    tmp_path: Path,
) -> None:
    target = tmp_path / "partial.py"
    error = RuntimeError("original exception")

    async def execute() -> ToolResult:
        target.write_text("answer=  42\n")
        raise error

    with pytest.raises(RuntimeError) as raised:
        await PythonAutoFormatter().run(WriteFileTool(), {"path": str(target)}, execute)
    assert raised.value is error
    assert target.read_text() == "answer = 42\n"


async def test_exception_and_failed_formatting_both_reach_exception_message(tmp_path: Path) -> None:
    target = tmp_path / "broken.py"
    error = RuntimeError("original sentinel failure")

    async def execute() -> ToolResult:
        target.write_text("def broken(:\n")
        raise error

    with pytest.raises(Exception) as raised:
        await PythonAutoFormatter().run(WriteFileTool(), {"path": str(target)}, execute)
    assert "original sentinel failure" in str(raised.value)
    assert "Black" in str(raised.value)
    assert raised.value.__cause__ is error


async def test_cancellation_does_not_start_formatting(tmp_path: Path) -> None:
    target = tmp_path / "partial.py"

    async def execute() -> ToolResult:
        target.write_text("answer=  42\n")
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await PythonAutoFormatter().run(WriteFileTool(), {"path": str(target)}, execute)
    assert target.read_text() == "answer=  42\n"


async def test_read_tool_bypasses_tracking_and_formatting(tmp_path: Path) -> None:
    target = tmp_path / "dirty.py"
    target.write_text("answer=  42\n")
    tool = ReadFileTool()
    result = await PythonAutoFormatter().run(
        tool, {"path": str(target)}, lambda: tool.execute(path=str(target))
    )
    assert result.success
    assert result.content == "answer=  42\n"
    assert target.read_text() == "answer=  42\n"


async def test_explicit_symlink_target_preserves_file_tool_resolution(tmp_path: Path) -> None:
    original = tmp_path / "original.py"
    original.write_text("answer=  1\n")
    target = tmp_path / "link.py"
    try:
        target.symlink_to(original)
    except OSError:
        pytest.skip("Symlinks unavailable")
    tool = WriteFileTool()
    result = await PythonAutoFormatter().run(
        tool,
        {"path": str(target)},
        lambda: tool.execute(path=str(target), content="answer=  2\n"),
    )
    assert result.success, result.content
    assert original.read_text() == "answer = 2\n"


async def test_changed_oversized_source_fails_formatting(tmp_path: Path) -> None:
    target = tmp_path / "large.py"
    source = "#" + "a" * (2 * 1024 * 1024)
    tool = WriteFileTool()
    result = await PythonAutoFormatter().run(
        tool,
        {"path": str(target)},
        lambda: tool.execute(path=str(target), content=source),
    )
    assert not result.success
    assert "limit" in result.content.lower()
    assert target.read_text() == source


async def test_unchanged_oversized_source_does_not_block_command(tmp_path: Path) -> None:
    large = tmp_path / "large.py"
    original = "#" + "a" * (2 * 1024 * 1024)
    large.write_text(original)
    tool = PythonExecTool()
    result = await PythonAutoFormatter().run(
        tool,
        {"background": False, "cwd": str(tmp_path)},
        lambda: tool.execute(background=False,
            code="from pathlib import Path; Path('small.py').write_text('answer=  42\\n')",
            cwd=str(tmp_path),
        ),
    )
    assert result.success, result.content
    assert (tmp_path / "small.py").read_text() == "answer = 42\n"
    assert large.read_text() == original


async def test_command_workspace_alias_resolves_before_source_tracking(tmp_path: Path) -> None:
    project = tmp_path / "real-project"
    project.mkdir()
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(project, target_is_directory=True)
    except OSError:
        pytest.skip("Symlinks unavailable")
    tool = PythonExecTool()
    result = await PythonAutoFormatter().run(
        tool,
        {"background": False, "cwd": str(alias)},
        lambda: tool.execute(background=False,
            code="from pathlib import Path; Path('source.py').write_text('answer=  42\\n')",
            cwd=str(alias),
        ),
    )
    assert result.success, result.content
    assert (project / "source.py").read_text() == "answer = 42\n"


async def test_failure_is_visible_before_long_original_output(tmp_path: Path) -> None:
    target = tmp_path / "broken.py"

    async def execute() -> ToolResult:
        target.write_text("def broken(:\n")
        return ToolResult("x" * 60_000, False, display="original display", error="original error")

    result = await PythonAutoFormatter().run(WriteFileTool(), {"path": str(target)}, execute)
    assert not result.success
    assert "Black" in result.content[:100]
    assert "x" * 60_000 in result.content
    assert result.display == "original display"
    assert result.error and "original error" in result.error


async def test_manual_backend_directory_uses_same_bounded_black(tmp_path: Path) -> None:
    for index in range(66):
        (tmp_path / f"source{index}.py").write_text("answer=  42\n")
    backend = getattr(formatting, "format_python_files", None)
    assert backend is not None, "A single shared Black backend is required"
    await backend([tmp_path], cwd=tmp_path)
    assert all(path.read_text() == "answer = 42\n" for path in tmp_path.glob("*.py"))


async def test_missing_black_fails_explicitly_without_installation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    environment = tmp_path / "empty-env"
    # Preserve relative shared-library resolution for managed POSIX interpreters.
    venv.EnvBuilder(with_pip=False, symlinks=os.name != "nt").create(environment)
    interpreter = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    probe = subprocess.run(
        [str(interpreter), "-I", "-c", "import sys; print(sys.prefix)"],
        capture_output=True, text=True, check=True, timeout=10,
    )
    assert Path(probe.stdout.strip()) == environment
    monkeypatch.setattr(
        formatting, "_BLACK_COMMAND", [str(interpreter), *formatting._BLACK_COMMAND[1:]]
    )
    target = tmp_path / "source.py"
    tool = WriteFileTool()
    result = await PythonAutoFormatter().run(
        tool,
        {"path": str(target)},
        lambda: tool.execute(path=str(target), content="answer=  42\n"),
    )
    assert not result.success
    assert "No module named black" in result.content
    assert target.read_text() == "answer=  42\n"


async def test_tracking_overflow_prevents_tool_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(formatting, "MAX_FILES", 1)
    (tmp_path / "one.py").write_text("one=1\n")
    (tmp_path / "two.py").write_text("two=2\n")
    tool = PythonExecTool()
    result = await PythonAutoFormatter().run(
        tool,
        {"background": False, "cwd": str(tmp_path)},
        lambda: tool.execute(background=False, code="raise RuntimeError('must not run')", cwd=str(tmp_path)),
    )
    assert not result.success
    assert "file limit" in result.content
    assert "must not run" not in result.content


async def test_black_timeout_fails_without_losing_tool_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(formatting, "FORMAT_TIMEOUT", 0.001)
    target = tmp_path / "source.py"
    tool = WriteFileTool()
    result = await PythonAutoFormatter().run(
        tool,
        {"path": str(target)},
        lambda: tool.execute(path=str(target), content="answer=  42\n"),
    )
    assert not result.success
    assert "Black" in result.content and "timeout" in result.content
    assert "Successfully wrote" in result.content


async def test_unchanged_formatted_source_does_not_claim_formatter_changes(tmp_path: Path) -> None:
    target = tmp_path / "source.py"
    tool = WriteFileTool()
    result = await PythonAutoFormatter().run(
        tool,
        {"path": str(target)},
        lambda: tool.execute(path=str(target), content="answer = 42\n"),
    )
    assert result.success, result.content
    assert "Black formatted" not in result.content


async def test_composite_awaits_nested_registry_write_without_deadlock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    registry = ToolRegistry()
    registry.register(WriteFileTool())

    class Composite(Tool):
        name, description, kind = "composite", "Nested write", ToolKind.EXECUTE

        async def execute(self, **params: object) -> ToolResult:
            return await registry.execute("write_file", {"path": "nested.py", "content": "x=1\n"})

    registry.register(Composite())
    result = await asyncio.wait_for(registry.execute("composite", {}), timeout=3)
    assert result.success, result.content
    assert (tmp_path / "nested.py").read_text() == "x = 1\n"


async def test_nested_batch_serializes_siblings_and_allows_grandchild_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    parent, child = ToolRegistry(), ToolRegistry()
    child.inherit_policies_from(parent)
    child.register(WriteFileTool())
    active = 0
    maximum = 0

    class Branch(Tool):
        name, description, kind = "branch", "Nested branch", ToolKind.EXECUTE

        async def execute(self, **params: object) -> ToolResult:
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            try:
                await asyncio.sleep(0)
                return await child.execute(
                    "write_file", {"path": params["path"], "content": "x=1\n"}
                )
            finally:
                active -= 1

    class Composite(Tool):
        name, description, kind = "composite", "Nested batch", ToolKind.EXECUTE

        async def execute(self, **params: object) -> ToolResult:
            batch = await child.execute_batch(
                [("branch", {"path": "one.py"}), ("branch", {"path": "two.py"})]
            )
            return ToolResult("batch complete", success=batch.successful == 2)

    child.register(Branch())
    parent.register(Composite())
    result = await asyncio.wait_for(parent.execute("composite", {}), timeout=5)
    assert result.success, result.content
    assert maximum == 1
    assert (tmp_path / "one.py").read_text() == "x = 1\n"
    assert (tmp_path / "two.py").read_text() == "x = 1\n"


async def test_cancelled_nested_call_releases_transaction_for_reuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    registry = ToolRegistry()
    entered, ended = asyncio.Event(), asyncio.Event()

    class Inner(Tool):
        name, description, kind = "inner", "Wait for cancellation", ToolKind.EXECUTE

        async def execute(self, **params: object) -> ToolResult:
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                ended.set()
            return ToolResult("unreachable")

    class Composite(Tool):
        name, description, kind = "composite", "Nested cancellation", ToolKind.EXECUTE

        async def execute(self, **params: object) -> ToolResult:
            return await asyncio.create_task(registry.execute("inner", {}))

    registry.register(Inner())
    registry.register(Composite())
    registry.register(WriteFileTool())
    task = asyncio.create_task(registry.execute("composite", {}))
    try:
        await asyncio.wait_for(entered.wait(), timeout=2)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert ended.is_set()
    result = await asyncio.wait_for(
        registry.execute("write_file", {"path": "reused.py", "content": "x=1\n"}), timeout=3
    )
    assert result.success, result.content
    assert (tmp_path / "reused.py").read_text() == "x = 1\n"


async def test_parent_waits_for_admitted_background_child_before_formatting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    registry = ToolRegistry()
    entered, release, returned = asyncio.Event(), asyncio.Event(), asyncio.Event()
    children: list[asyncio.Task[ToolResult]] = []

    class Inner(Tool):
        name, description, kind = "inner", "Delayed mutation", ToolKind.EXECUTE

        async def execute(self, **params: object) -> ToolResult:
            entered.set()
            await release.wait()
            Path("background.py").write_text("x=1\n")
            return ToolResult("written")

    class Composite(Tool):
        name, description, kind = "composite", "Spawn mutation", ToolKind.EXECUTE

        async def execute(self, **params: object) -> ToolResult:
            children.append(asyncio.create_task(registry.execute("inner", {})))
            await entered.wait()
            returned.set()
            return ToolResult("parent callback returned")

    registry.register(Inner())
    registry.register(Composite())
    task = asyncio.create_task(registry.execute("composite", {}))
    try:
        await asyncio.wait_for(returned.wait(), timeout=2)
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        release.set()
        result = await asyncio.wait_for(task, timeout=5)
        await asyncio.gather(*children)
    assert result.success, result.content
    assert (tmp_path / "background.py").read_text() == "x = 1\n"


async def test_inherited_closed_frame_waits_for_unrelated_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    registry = ToolRegistry()
    begin, held, release, late_started = (asyncio.Event() for _ in range(4))
    children: list[asyncio.Task[ToolResult]] = []

    class Late(Tool):
        name, description, kind = "late", "Late operation", ToolKind.EXECUTE

        async def execute(self, **params: object) -> ToolResult:
            late_started.set()
            return ToolResult("late")

    class Hold(Tool):
        name, description, kind = "hold", "Hold transaction", ToolKind.EXECUTE

        async def execute(self, **params: object) -> ToolResult:
            held.set()
            await release.wait()
            return ToolResult("released")

    class Composite(Tool):
        name, description, kind = "composite", "Schedule late call", ToolKind.EXECUTE

        async def execute(self, **params: object) -> ToolResult:
            async def later() -> ToolResult:
                await begin.wait()
                return await registry.execute("late", {})

            children.append(asyncio.create_task(later()))
            return ToolResult("scheduled")

    for tool in (Late(), Hold(), Composite()):
        registry.register(tool)
    result = await registry.execute("composite", {})
    assert result.success
    holding = asyncio.create_task(registry.execute("hold", {}))
    try:
        await asyncio.wait_for(held.wait(), timeout=2)
        begin.set()
        await asyncio.sleep(0)
        assert not late_started.is_set()
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(holding, *children), timeout=5)
    assert late_started.is_set()
