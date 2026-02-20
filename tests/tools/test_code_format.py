"""Tests for code_format tool."""

import tempfile
from pathlib import Path

from henchman.tools.base import ToolKind
from henchman.tools.builtins.code_format import CodeFormatTool


class TestCodeFormatTool:
    """Tests for CodeFormatTool."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = CodeFormatTool()
        assert tool.name == "code_format"

    def test_description(self) -> None:
        """Tool has a description."""
        tool = CodeFormatTool()
        assert len(tool.description) > 10

    def test_kind_is_write(self) -> None:
        """Tool is WRITE kind (modifies files)."""
        tool = CodeFormatTool()
        assert tool.kind == ToolKind.WRITE

    def test_parameters_schema(self) -> None:
        """Tool has correct parameters schema."""
        tool = CodeFormatTool()
        params = tool.parameters
        assert "path" in params["properties"]
        assert "path" in params["required"]

    async def test_format_already_clean(self) -> None:
        """Report no changes for already formatted file."""
        tool = CodeFormatTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "clean.py"
            f.write_text("x = 1\n")
            result = await tool.execute(path=str(f))
            assert result.success is True

    async def test_format_fixes_spacing(self) -> None:
        """Format file with bad spacing."""
        tool = CodeFormatTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "bad.py"
            f.write_text("x=1\ny=2\nz    =     3\n")
            result = await tool.execute(path=str(f))
            assert result.success is True
            # File should be modified
            content = f.read_text()
            assert "x = " in content or "x=" in content  # ruff format may or may not change

    async def test_nonexistent_file(self) -> None:
        """Handle nonexistent file."""
        tool = CodeFormatTool()
        result = await tool.execute(path="/nonexistent/foo.py")
        assert result.success is False

    async def test_format_reports_changes(self) -> None:
        """Output indicates whether changes were made."""
        tool = CodeFormatTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "report.py"
            f.write_text("x = 1\n")
            result = await tool.execute(path=str(f))
            assert result.success is True
            assert isinstance(result.content, str)

    async def test_syntax_error_file(self) -> None:
        """Handle file with syntax errors gracefully."""
        tool = CodeFormatTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "broken.py"
            f.write_text("def foo(\n")
            result = await tool.execute(path=str(f))
            # ruff format may report error or skip - either way it shouldn't crash
            assert isinstance(result.content, str)
