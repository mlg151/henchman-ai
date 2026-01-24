"""Tests for built-in file tools (read_file, write_file, edit_file)."""

import tempfile
from pathlib import Path

from henchman.tools.base import ToolKind
from henchman.tools.builtins.file_edit import EditFileTool
from henchman.tools.builtins.file_read import ReadFileTool
from henchman.tools.builtins.file_write import WriteFileTool


class TestReadFileTool:
    """Tests for ReadFileTool."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = ReadFileTool()
        assert tool.name == "read_file"

    def test_description(self) -> None:
        """Tool has description."""
        tool = ReadFileTool()
        assert "read" in tool.description.lower()

    def test_kind_is_read(self) -> None:
        """Tool is a READ kind (auto-approved)."""
        tool = ReadFileTool()
        assert tool.kind == ToolKind.READ

    def test_parameters_schema(self) -> None:
        """Tool has correct parameters schema."""
        tool = ReadFileTool()
        params = tool.parameters
        assert params["type"] == "object"
        assert "path" in params["properties"]
        assert "path" in params["required"]

    async def test_read_file_success(self) -> None:
        """Successfully read a file."""
        tool = ReadFileTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("line 1\nline 2\nline 3\n")
            f.flush()
            result = await tool.execute(path=f.name)
        assert result.success is True
        assert "line 1" in result.content
        assert "line 2" in result.content
        Path(f.name).unlink()

    async def test_read_file_with_line_range(self) -> None:
        """Read specific line range from file."""
        tool = ReadFileTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("line 1\nline 2\nline 3\nline 4\nline 5\n")
            f.flush()
            result = await tool.execute(path=f.name, start_line=2, end_line=4)
        assert result.success is True
        assert "line 1" not in result.content
        assert "line 2" in result.content
        assert "line 4" in result.content
        assert "line 5" not in result.content
        Path(f.name).unlink()

    async def test_read_file_not_found(self) -> None:
        """Handle file not found error."""
        tool = ReadFileTool()
        result = await tool.execute(path="/nonexistent/file.txt")
        assert result.success is False
        assert result.error is not None
        assert "not found" in result.error.lower() or "no such file" in result.error.lower()

    async def test_read_file_with_negative_end_line(self) -> None:
        """End line -1 means read to end."""
        tool = ReadFileTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("line 1\nline 2\nline 3\n")
            f.flush()
            result = await tool.execute(path=f.name, start_line=2, end_line=-1)
        assert result.success is True
        assert "line 1" not in result.content
        assert "line 2" in result.content
        assert "line 3" in result.content
        Path(f.name).unlink()


class TestWriteFileTool:
    """Tests for WriteFileTool."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = WriteFileTool()
        assert tool.name == "write_file"

    def test_description(self) -> None:
        """Tool has description."""
        tool = WriteFileTool()
        assert "write" in tool.description.lower()

    def test_kind_is_write(self) -> None:
        """Tool is a WRITE kind (requires confirmation)."""
        tool = WriteFileTool()
        assert tool.kind == ToolKind.WRITE

    def test_parameters_schema(self) -> None:
        """Tool has correct parameters schema."""
        tool = WriteFileTool()
        params = tool.parameters
        assert "path" in params["properties"]
        assert "content" in params["properties"]
        assert "path" in params["required"]
        assert "content" in params["required"]

    async def test_write_file_success(self) -> None:
        """Successfully write to a file."""
        tool = WriteFileTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"
            result = await tool.execute(path=str(path), content="hello world")
            assert result.success is True
            assert path.read_text() == "hello world"

    async def test_write_file_creates_parent_dirs(self) -> None:
        """Create parent directories if they don't exist."""
        tool = WriteFileTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "subdir" / "nested" / "test.txt"
            result = await tool.execute(path=str(path), content="nested content")
            assert result.success is True
            assert path.read_text() == "nested content"

    async def test_write_file_overwrites_existing(self) -> None:
        """Overwrite existing file."""
        tool = WriteFileTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("original")
            f.flush()
            result = await tool.execute(path=f.name, content="new content")
            assert result.success is True
            assert Path(f.name).read_text() == "new content"
        Path(f.name).unlink()


class TestEditFileTool:
    """Tests for EditFileTool."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = EditFileTool()
        assert tool.name == "edit_file"

    def test_description(self) -> None:
        """Tool has description."""
        tool = EditFileTool()
        assert "edit" in tool.description.lower()

    def test_kind_is_write(self) -> None:
        """Tool is a WRITE kind (requires confirmation)."""
        tool = EditFileTool()
        assert tool.kind == ToolKind.WRITE

    def test_parameters_schema(self) -> None:
        """Tool has correct parameters schema."""
        tool = EditFileTool()
        params = tool.parameters
        assert "path" in params["properties"]
        assert "old_str" in params["properties"]
        assert "new_str" in params["properties"]

    async def test_edit_file_success(self) -> None:
        """Successfully edit a file with string replacement."""
        tool = EditFileTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world")
            f.flush()
            result = await tool.execute(
                path=f.name,
                old_str="world",
                new_str="universe",
            )
            assert result.success is True
            assert Path(f.name).read_text() == "hello universe"
        Path(f.name).unlink()

    async def test_edit_file_string_not_found(self) -> None:
        """Error when old_str not found in file."""
        tool = EditFileTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world")
            f.flush()
            result = await tool.execute(
                path=f.name,
                old_str="nonexistent",
                new_str="replacement",
            )
            assert result.success is False
            assert "not found" in result.error.lower()
        Path(f.name).unlink()

    async def test_edit_file_multiple_matches_error(self) -> None:
        """Error when old_str matches multiple times."""
        tool = EditFileTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello hello hello")
            f.flush()
            result = await tool.execute(
                path=f.name,
                old_str="hello",
                new_str="hi",
            )
            assert result.success is False
            assert "multiple" in result.error.lower() or "unique" in result.error.lower()
        Path(f.name).unlink()

    async def test_edit_file_not_found(self) -> None:
        """Error when file doesn't exist."""
        tool = EditFileTool()
        result = await tool.execute(
            path="/nonexistent/file.txt",
            old_str="x",
            new_str="y",
        )
        assert result.success is False
        assert result.error is not None


class TestFileToolPermissionErrors:
    """Tests for permission error handling in file tools."""

    async def test_read_file_permission_error(self) -> None:
        """Handle permission denied on read."""
        import os
        import stat

        tool = ReadFileTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("content")
            f.flush()
            # Remove read permissions
            os.chmod(f.name, 0o000)
            try:
                result = await tool.execute(path=f.name)
                assert result.success is False
                assert "permission" in result.error.lower()
            finally:
                # Restore permissions for cleanup
                os.chmod(f.name, stat.S_IRUSR | stat.S_IWUSR)
                Path(f.name).unlink()

    async def test_write_file_permission_error(self) -> None:
        """Handle permission denied on write."""
        import os
        import stat

        tool = WriteFileTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Make directory read-only
            os.chmod(tmpdir, stat.S_IRUSR | stat.S_IXUSR)
            try:
                result = await tool.execute(
                    path=str(Path(tmpdir) / "test.txt"),
                    content="test",
                )
                assert result.success is False
                assert "permission" in result.error.lower()
            finally:
                # Restore permissions for cleanup
                os.chmod(tmpdir, stat.S_IRWXU)

    async def test_edit_file_permission_error(self) -> None:
        """Handle permission denied on edit."""
        import os
        import stat

        tool = EditFileTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world")
            f.flush()
            # Remove write permissions
            os.chmod(f.name, stat.S_IRUSR)
            try:
                result = await tool.execute(
                    path=f.name,
                    old_str="hello",
                    new_str="hi",
                )
                assert result.success is False
                assert "permission" in result.error.lower()
            finally:
                # Restore permissions for cleanup
                os.chmod(f.name, stat.S_IRUSR | stat.S_IWUSR)
                Path(f.name).unlink()


class TestLsToolEdgeCases:
    """Additional tests for ls tool."""

    async def test_ls_permission_error(self) -> None:
        """Handle permission denied on directory."""
        import os
        import stat

        from henchman.tools.builtins.ls import LsTool

        tool = LsTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a subdirectory and remove permissions
            subdir = Path(tmpdir) / "restricted"
            subdir.mkdir()
            os.chmod(str(subdir), 0o000)
            try:
                result = await tool.execute(path=str(subdir))
                assert result.success is False
                assert "permission" in result.error.lower()
            finally:
                os.chmod(str(subdir), stat.S_IRWXU)


class TestGlobToolEdgeCases:
    """Additional tests for glob tool."""

    async def test_glob_path_not_found(self) -> None:
        """Handle path not found."""
        from henchman.tools.builtins.glob_tool import GlobTool

        tool = GlobTool()
        result = await tool.execute(pattern="*.txt", path="/nonexistent/path")
        assert result.success is False
        assert "not found" in result.error.lower()


class TestGrepToolEdgeCases:
    """Additional tests for grep tool."""

    async def test_grep_invalid_regex(self) -> None:
        """Handle invalid regex pattern."""
        from henchman.tools.builtins.grep import GrepTool

        tool = GrepTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world")
            f.flush()
            result = await tool.execute(pattern="[invalid", path=f.name)
        assert result.success is False
        assert "regex" in result.error.lower() or "invalid" in result.error.lower()
        Path(f.name).unlink()


class TestShellToolEdgeCases:
    """Additional tests for shell tool."""

    async def test_shell_exception_handling(self) -> None:
        """Handle unexpected exceptions."""
        from henchman.tools.builtins.shell import ShellTool

        tool = ShellTool()
        # Non-existent working directory should cause error
        result = await tool.execute(command="echo hello", cwd="/nonexistent/dir")
        assert result.success is False
        assert result.error is not None


class TestWebFetchEdgeCases:
    """Additional tests for web_fetch tool."""

    async def test_aiohttp_not_installed(self) -> None:
        """Handle aiohttp not installed."""
        from unittest.mock import patch

        from henchman.tools.builtins.web_fetch import WebFetchTool

        tool = WebFetchTool()

        # Mock import to raise ImportError
        with patch.dict("sys.modules", {"aiohttp": None}):
            import builtins

            original_import = builtins.__import__

            def mock_import(name, *args, **kwargs):  # noqa: ARG001
                if name == "aiohttp":
                    raise ImportError("No module named 'aiohttp'")
                return original_import(name, *args, **kwargs)

            with patch.object(builtins, "__import__", mock_import):
                result = await tool.execute(url="https://example.com")

        assert result.success is False
        assert "aiohttp" in result.error.lower()
