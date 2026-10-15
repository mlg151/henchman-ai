"""Foreground tool results include automatic Black formatting before verification."""

import asyncio
from pathlib import Path

import pytest

from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.builtins.file_edit import EditFileTool
from henchman.tools.builtins.file_read import ReadFileTool
from henchman.tools.builtins.file_write import WriteFileTool
from henchman.tools.builtins.python_exec import PythonExecTool
from henchman.tools.registry import ToolRegistry


@pytest.fixture
def registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ToolRegistry:
    monkeypatch.chdir(tmp_path)
    registry = ToolRegistry()
    for tool in (WriteFileTool(), EditFileTool(), ReadFileTool(), PythonExecTool()):
        registry.register(tool)
    return registry


async def test_write_is_black_formatted_before_success_is_returned(registry, tmp_path):
    untouched = tmp_path / "untouched.py"
    untouched.write_text("old=  1\n")
    result = await registry.execute("write_file", {"path": "new.py", "content": "value= 1\n"})
    assert result.success, result
    assert (tmp_path / "new.py").read_text() == "value = 1\n"
    assert untouched.read_text() == "old=  1\n"


async def test_edit_is_black_formatted_before_success_is_returned(registry, tmp_path):
    source = tmp_path / "module.py"
    source.write_text("value = 1\n")
    result = await registry.execute(
        "edit_file",
        {
            "path": "module.py",
            "old_str": "value = 1",
            "new_str": "value= 2",
        },
    )
    assert result.success, result
    assert source.read_text() == "value = 2\n"


async def test_command_created_python_is_formatted_without_model_formatter_call(registry, tmp_path):
    result = await registry.execute(
        "python_exec",
        {
            "code": "from pathlib import Path; Path('generated.py').write_text('value=1\\n')",
            "timeout": 10,
            "background": False,
        },
    )
    assert result.success, result
    assert (tmp_path / "generated.py").read_text() == "value = 1\n"


async def test_formatter_failure_cannot_be_reported_as_success(registry, tmp_path):
    result = await registry.execute("write_file", {"path": "broken.py", "content": "def broken(\n"})
    assert not result.success
    assert "Black" in result.content
    assert (tmp_path / "broken.py").read_text() == "def broken(\n"


async def test_partial_write_is_formatted_without_hiding_command_failure(registry, tmp_path):
    result = await registry.execute(
        "python_exec",
        {
            "code": "from pathlib import Path; Path('partial.py').write_text('value=1\\n'); raise SystemExit(7)",
            "timeout": 10,
            "background": False,
        },
    )
    assert not result.success
    assert (tmp_path / "partial.py").read_text() == "value = 1\n"


async def test_denied_write_does_not_format_existing_source(registry, tmp_path):
    source = tmp_path / "existing.py"
    source.write_text("old=1\n")
    registry.set_plan_mode(enabled=True)
    result = await registry.execute("write_file", {"path": str(source), "content": "value=1\n"})
    assert not result.success
    assert source.read_text() == "old=1\n"


async def test_read_does_not_reformat_existing_source(registry, tmp_path):
    source = tmp_path / "existing.py"
    source.write_text("old=1\n")
    result = await registry.execute("read_file", {"path": str(source)})
    assert result.success
    assert result.content == "old=1\n"
    assert source.read_text() == "old=1\n"


async def test_scoped_registries_wait_for_formatting_before_verification(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    started, release, checked = asyncio.Event(), asyncio.Event(), asyncio.Event()
    source = tmp_path / "module.py"

    class Writer(Tool):
        name, description, kind = "write_file", "Write source", ToolKind.WRITE

        async def execute(self, **_params: object) -> ToolResult:
            source.write_text("value=1\n")
            started.set()
            await release.wait()
            return ToolResult("Written")

    class Verify(Tool):
        name, description, kind = "verify_source", "Check formatted source", ToolKind.EXECUTE

        async def execute(self, **_params: object) -> ToolResult:
            checked.set()
            content = source.read_text()
            return ToolResult(content, success=content == "value = 1\n")

    parent, child = ToolRegistry(), ToolRegistry()
    child.inherit_policies_from(parent)
    parent.register(Writer())
    child.register(Verify())
    write = asyncio.create_task(parent.execute("write_file", {"path": str(source)}))
    await asyncio.wait_for(started.wait(), timeout=5)
    verify = asyncio.create_task(child.execute("verify_source", {}))
    try:
        await asyncio.sleep(0)
        assert not checked.is_set()
    finally:
        release.set()
        written, verified = await asyncio.wait_for(asyncio.gather(write, verify), timeout=15)
    assert written.success, written
    assert verified.success, verified
