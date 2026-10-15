"""Manual formatting uses the same Black backend as automatic formatting."""

import asyncio
from pathlib import Path

import pytest

from henchman.tools.base import ConfirmationRequest, ToolKind
from henchman.tools.builtins import code_format
from henchman.tools.builtins.code_format import CodeFormatTool
from henchman.tools.formatting import FormattingError
from henchman.tools.registry import ToolRegistry


def test_tool_keeps_write_contract_and_describes_black() -> None:
    tool = CodeFormatTool()
    assert tool.name == "code_format"
    assert tool.kind == ToolKind.WRITE
    assert "Black" in tool.description
    assert "ruff" not in tool.description.lower()
    assert tool.parameters["required"] == ["path"]


async def test_format_uses_black_project_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        "[tool.black]\nskip-string-normalization = true\n",
        encoding="utf-8",
    )
    source = tmp_path / "example.py"
    source.write_text("message='hello'\n", encoding="utf-8")

    result = await CodeFormatTool().execute(path="example.py")

    assert result.success, result
    assert source.read_text(encoding="utf-8") == "message = 'hello'\n"
    assert "Black formatting completed" in result.content


@pytest.mark.parametrize("contents", ["x = 1\n", ""])
async def test_clean_or_empty_file_does_not_claim_a_change(
    tmp_path: Path,
    contents: str,
) -> None:
    source = tmp_path / "clean.py"
    source.write_text(contents, encoding="utf-8")

    result = await CodeFormatTool().execute(path=str(source))

    assert result.success, result
    assert source.read_text(encoding="utf-8") == contents
    assert "Black formatting completed" in result.content
    assert "changed" not in result.content.lower()


async def test_directory_formats_python_files_and_stubs(tmp_path: Path) -> None:
    source = tmp_path / "example.py"
    stub = tmp_path / "example.pyi"
    note = tmp_path / "notes.txt"
    source.write_text("x=1\ny    =2\n", encoding="utf-8")
    stub.write_text("def f(x:int)->str: ...\n", encoding="utf-8")
    note.write_text("x=1\n", encoding="utf-8")

    result = await CodeFormatTool().execute(path=str(tmp_path))

    assert result.success, result
    assert source.read_text(encoding="utf-8") == "x = 1\ny = 2\n"
    assert stub.read_text(encoding="utf-8") == "def f(x: int) -> str: ...\n"
    assert note.read_text(encoding="utf-8") == "x=1\n"


async def test_invalid_syntax_is_explicit_failure_without_modifying_source(tmp_path: Path) -> None:
    source = tmp_path / "broken.py"
    source.write_text("def broken(\n", encoding="utf-8")

    result = await CodeFormatTool().execute(path=str(source))

    assert not result.success
    assert result.error
    assert "Black" in result.content
    assert source.read_text(encoding="utf-8") == "def broken(\n"


@pytest.mark.parametrize("path", ["", "does-not-exist.py"])
async def test_invalid_paths_fail_before_formatting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    result = await CodeFormatTool().execute(path=path)
    assert not result.success
    assert result.error
    assert "No path" in result.content if not path else "Path not found" in result.content


async def test_registry_requires_approval_before_formatting(tmp_path: Path) -> None:
    source = tmp_path / "example.py"
    source.write_text("x=1\n", encoding="utf-8")
    registry = ToolRegistry()
    registry.register(CodeFormatTool())

    async def deny(_request: ConfirmationRequest) -> bool:
        return False

    registry.set_confirmation_handler(deny)
    result = await registry.execute("code_format", {"path": str(source)})

    assert not result.success
    assert source.read_text(encoding="utf-8") == "x=1\n"


@pytest.mark.parametrize(
    "failure",
    [
        RuntimeError("Black backend failed"),
        FileNotFoundError("Black backend is unavailable"),
        FormattingError("Black exited 1: No module named black"),
    ],
)
async def test_backend_failures_are_reported_without_claiming_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
) -> None:
    source = tmp_path / "example.py"
    source.write_text("x=1\n", encoding="utf-8")

    async def fail(_paths: list[Path], *, cwd: Path) -> None:
        assert cwd == Path.cwd()
        raise failure

    monkeypatch.setattr(code_format, "format_python_files", fail)
    result = await CodeFormatTool().execute(path=str(source))

    assert not result.success
    assert str(failure) in result.content
    assert result.error
    assert source.read_text(encoding="utf-8") == "x=1\n"


async def test_backend_diagnostics_are_sanitized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "example.py"
    source.write_text("x=1\n", encoding="utf-8")

    async def fail(_paths: list[Path], *, cwd: Path) -> None:
        assert cwd == Path.cwd()
        raise RuntimeError("Black failed: api_key=private-formatter-secret")

    monkeypatch.setattr(code_format, "format_python_files", fail)
    result = await CodeFormatTool().execute(path=str(source))

    assert not result.success
    assert "private-formatter-secret" not in result.content
    assert "private-formatter-secret" not in (result.error or "")
    assert "Black failed" in result.content


async def test_backend_timeout_preserves_timeout_category(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "example.py"
    source.write_text("x=1\n", encoding="utf-8")

    async def fail(_paths: list[Path], *, cwd: Path) -> None:
        assert cwd == Path.cwd()
        raise TimeoutError("Black exceeded its time limit")

    monkeypatch.setattr(code_format, "format_python_files", fail)
    result = await CodeFormatTool().execute(path=str(source))

    assert not result.success
    assert result.error == "Timeout"
    assert "timed out" in result.content


async def test_backend_cancellation_propagates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "example.py"
    source.write_text("x=1\n", encoding="utf-8")

    async def cancel(_paths: list[Path], *, cwd: Path) -> None:
        assert cwd == Path.cwd()
        raise asyncio.CancelledError

    monkeypatch.setattr(code_format, "format_python_files", cancel)
    with pytest.raises(asyncio.CancelledError):
        await CodeFormatTool().execute(path=str(source))
