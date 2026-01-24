"""Tests for grep tool."""

import tempfile
from pathlib import Path

from henchman.tools.base import ToolKind
from henchman.tools.builtins.grep import GrepTool


class TestGrepTool:
    """Tests for GrepTool."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = GrepTool()
        assert tool.name == "grep"

    def test_description(self) -> None:
        """Tool has description."""
        tool = GrepTool()
        assert "search" in tool.description.lower() or "pattern" in tool.description.lower()

    def test_kind_is_read(self) -> None:
        """Tool is a READ kind (auto-approved)."""
        tool = GrepTool()
        assert tool.kind == ToolKind.READ

    def test_parameters_schema(self) -> None:
        """Tool has correct parameters schema."""
        tool = GrepTool()
        params = tool.parameters
        assert "pattern" in params["properties"]
        assert "path" in params["properties"]
        assert "pattern" in params["required"]

    async def test_grep_simple_pattern(self) -> None:
        """Find lines matching simple pattern."""
        tool = GrepTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world\nfoo bar\nhello there\n")
            f.flush()
            result = await tool.execute(pattern="hello", path=f.name)
        assert result.success is True
        assert "hello world" in result.content
        assert "hello there" in result.content
        assert "foo bar" not in result.content
        Path(f.name).unlink()

    async def test_grep_regex_pattern(self) -> None:
        """Find lines matching regex pattern."""
        tool = GrepTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test123\ntest456\nhello\n")
            f.flush()
            result = await tool.execute(pattern=r"test\d+", path=f.name)
        assert result.success is True
        assert "test123" in result.content
        assert "test456" in result.content
        assert "hello" not in result.content
        Path(f.name).unlink()

    async def test_grep_case_insensitive(self) -> None:
        """Case insensitive search."""
        tool = GrepTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Hello\nHELLO\nhello\nworld\n")
            f.flush()
            result = await tool.execute(pattern="hello", path=f.name, ignore_case=True)
        assert result.success is True
        assert "Hello" in result.content
        assert "HELLO" in result.content
        assert "hello" in result.content
        Path(f.name).unlink()

    async def test_grep_directory(self) -> None:
        """Search in all files in a directory."""
        tool = GrepTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "file1.txt").write_text("hello world\n")
            (Path(tmpdir) / "file2.txt").write_text("goodbye world\n")

            result = await tool.execute(pattern="hello", path=tmpdir)
            assert result.success is True
            assert "hello" in result.content
            assert "file1.txt" in result.content

    async def test_grep_with_line_numbers(self) -> None:
        """Include line numbers in output."""
        tool = GrepTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("line1\nhello\nline3\n")
            f.flush()
            result = await tool.execute(pattern="hello", path=f.name, line_numbers=True)
        assert result.success is True
        assert "2" in result.content  # Line number
        Path(f.name).unlink()

    async def test_grep_no_matches(self) -> None:
        """Handle no matches gracefully."""
        tool = GrepTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world\n")
            f.flush()
            result = await tool.execute(pattern="nonexistent", path=f.name)
        assert result.success is True
        assert "no matches" in result.content.lower() or result.content.strip() == ""
        Path(f.name).unlink()

    async def test_grep_file_not_found(self) -> None:
        """Handle file not found error."""
        tool = GrepTool()
        result = await tool.execute(pattern="test", path="/nonexistent/file.txt")
        assert result.success is False
        assert result.error is not None

    async def test_grep_with_glob_pattern(self) -> None:
        """Search with file glob pattern."""
        tool = GrepTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "file.txt").write_text("hello txt\n")
            (Path(tmpdir) / "file.py").write_text("hello py\n")

            result = await tool.execute(pattern="hello", path=tmpdir, glob="*.txt")
            assert result.success is True
            assert "hello txt" in result.content
            assert "hello py" not in result.content
