"""Tests for directory tools (ls, glob)."""

import tempfile
from pathlib import Path

from henchman.tools.base import ToolKind
from henchman.tools.builtins.glob_tool import GlobTool
from henchman.tools.builtins.ls import LsTool


class TestLsTool:
    """Tests for LsTool."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = LsTool()
        assert tool.name == "ls"

    def test_description(self) -> None:
        """Tool has description."""
        tool = LsTool()
        assert "list" in tool.description.lower()

    def test_kind_is_read(self) -> None:
        """Tool is a READ kind (auto-approved)."""
        tool = LsTool()
        assert tool.kind == ToolKind.READ

    def test_parameters_schema(self) -> None:
        """Tool has correct parameters schema."""
        tool = LsTool()
        params = tool.parameters
        assert "path" in params["properties"]

    async def test_ls_directory(self) -> None:
        """List directory contents."""
        tool = LsTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some files
            (Path(tmpdir) / "file1.txt").touch()
            (Path(tmpdir) / "file2.txt").touch()
            (Path(tmpdir) / "subdir").mkdir()

            result = await tool.execute(path=tmpdir)
            assert result.success is True
            assert "file1.txt" in result.content
            assert "file2.txt" in result.content
            assert "subdir" in result.content

    async def test_ls_nonexistent_directory(self) -> None:
        """Handle nonexistent directory."""
        tool = LsTool()
        result = await tool.execute(path="/nonexistent/directory")
        assert result.success is False
        assert result.error is not None

    async def test_ls_file_instead_of_directory(self) -> None:
        """Handle when path is a file, not directory."""
        tool = LsTool()
        with tempfile.NamedTemporaryFile(delete=False) as f:
            result = await tool.execute(path=f.name)
            # Should still work - just shows the file
            assert result.success is True
        Path(f.name).unlink()

    async def test_ls_hidden_files(self) -> None:
        """Option to show hidden files."""
        tool = LsTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / ".hidden").touch()
            (Path(tmpdir) / "visible.txt").touch()

            # Without show_hidden
            result = await tool.execute(path=tmpdir, show_hidden=False)
            assert "visible.txt" in result.content
            assert ".hidden" not in result.content

            # With show_hidden
            result = await tool.execute(path=tmpdir, show_hidden=True)
            assert ".hidden" in result.content


class TestGlobTool:
    """Tests for GlobTool."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = GlobTool()
        assert tool.name == "glob"

    def test_description(self) -> None:
        """Tool has description."""
        tool = GlobTool()
        assert "glob" in tool.description.lower() or "pattern" in tool.description.lower()

    def test_kind_is_read(self) -> None:
        """Tool is a READ kind (auto-approved)."""
        tool = GlobTool()
        assert tool.kind == ToolKind.READ

    def test_parameters_schema(self) -> None:
        """Tool has correct parameters schema."""
        tool = GlobTool()
        params = tool.parameters
        assert "pattern" in params["properties"]
        assert "pattern" in params["required"]

    async def test_glob_simple_pattern(self) -> None:
        """Match files with simple glob pattern."""
        tool = GlobTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "file1.txt").touch()
            (Path(tmpdir) / "file2.txt").touch()
            (Path(tmpdir) / "file.py").touch()

            result = await tool.execute(pattern="*.txt", path=tmpdir)
            assert result.success is True
            assert "file1.txt" in result.content
            assert "file2.txt" in result.content
            assert "file.py" not in result.content

    async def test_glob_recursive_pattern(self) -> None:
        """Match files recursively with **."""
        tool = GlobTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "top.txt").touch()
            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()
            (subdir / "nested.txt").touch()

            result = await tool.execute(pattern="**/*.txt", path=tmpdir)
            assert result.success is True
            assert "nested.txt" in result.content

    async def test_glob_no_matches(self) -> None:
        """Handle no matches gracefully."""
        tool = GlobTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = await tool.execute(pattern="*.xyz", path=tmpdir)
            assert result.success is True
            assert "no matches" in result.content.lower() or result.content.strip() == ""
