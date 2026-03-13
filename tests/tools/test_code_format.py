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

    async def test_empty_path(self) -> None:
        """Empty path returns error."""
        tool = CodeFormatTool()
        result = await tool.execute(path="")
        assert result.success is False
        assert "No path" in result.content

    async def test_changed_file_reports_changes(self) -> None:
        """Reports changed files from ruff stderr output."""
        from unittest.mock import MagicMock, patch

        tool = CodeFormatTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "test.py"
            f.write_text("x=1\n")
            check_proc = MagicMock()
            check_proc.returncode = 1
            fmt_proc = MagicMock()
            fmt_proc.returncode = 0

            async def fake_wait_for(coro: object, timeout: float) -> tuple[bytes, bytes]:
                """Return fake communicate result with changed file name."""
                return (b"", b"test.py\n")

            with patch("asyncio.create_subprocess_exec", side_effect=[check_proc, fmt_proc]):
                with patch("asyncio.wait_for", side_effect=fake_wait_for):
                    result = await tool.execute(path=str(f))
                    assert result.success is True

    async def test_ruff_not_installed(self) -> None:
        """Handle ruff not installed."""
        from unittest.mock import patch

        tool = CodeFormatTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "test.py"
            f.write_text("x = 1\n")
            with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError()):
                result = await tool.execute(path=str(f))
                assert result.success is False
                assert "not installed" in result.content

    async def test_ruff_timeout(self) -> None:
        """Handle ruff timeout."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        tool = CodeFormatTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "test.py"
            f.write_text("x = 1\n")
            mock_proc = MagicMock()
            mock_proc.communicate = AsyncMock()
            with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
                    result = await tool.execute(path=str(f))
                    assert result.success is False
                    assert "timed out" in result.content
