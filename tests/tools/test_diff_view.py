"""Tests for diff_view tool."""

import tempfile
from pathlib import Path

from henchman.tools.base import ToolKind
from henchman.tools.builtins.diff_view import DiffViewTool


class TestDiffViewTool:
    """Tests for DiffViewTool."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = DiffViewTool()
        assert tool.name == "diff_view"

    def test_description(self) -> None:
        """Tool has a description."""
        tool = DiffViewTool()
        assert len(tool.description) > 10

    def test_kind_is_read(self) -> None:
        """Tool is READ kind."""
        tool = DiffViewTool()
        assert tool.kind == ToolKind.READ

    def test_parameters_schema(self) -> None:
        """Tool has correct parameters schema."""
        tool = DiffViewTool()
        params = tool.parameters
        assert "properties" in params

    async def test_diff_in_git_repo(self) -> None:
        """Show diff in a git repo with changes."""
        tool = DiffViewTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            import subprocess

            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=tmpdir,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=tmpdir,
                capture_output=True,
            )
            f = Path(tmpdir) / "hello.py"
            f.write_text("x = 1\n")
            subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "init"],
                cwd=tmpdir,
                capture_output=True,
            )
            f.write_text("x = 2\n")
            result = await tool.execute(cwd=tmpdir)
            assert result.success is True
            assert "x = 2" in result.content or "diff" in result.content.lower()

    async def test_diff_no_changes(self) -> None:
        """Report no changes when working tree is clean."""
        tool = DiffViewTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            import subprocess

            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=tmpdir,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=tmpdir,
                capture_output=True,
            )
            f = Path(tmpdir) / "hello.py"
            f.write_text("x = 1\n")
            subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "init"],
                cwd=tmpdir,
                capture_output=True,
            )
            result = await tool.execute(cwd=tmpdir)
            assert result.success is True
            assert "no" in result.content.lower() or result.content.strip() == ""

    async def test_diff_specific_file(self) -> None:
        """Show diff for a specific file."""
        tool = DiffViewTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            import subprocess

            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=tmpdir,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=tmpdir,
                capture_output=True,
            )
            a = Path(tmpdir) / "a.py"
            b = Path(tmpdir) / "b.py"
            a.write_text("x = 1\n")
            b.write_text("y = 1\n")
            subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "init"],
                cwd=tmpdir,
                capture_output=True,
            )
            a.write_text("x = 2\n")
            b.write_text("y = 2\n")
            result = await tool.execute(path="a.py", cwd=tmpdir)
            assert result.success is True
            assert "x = 2" in result.content
            # Should not contain b.py changes
            assert "y = 2" not in result.content

    async def test_not_a_git_repo(self) -> None:
        """Handle non-git directory."""
        tool = DiffViewTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = await tool.execute(cwd=tmpdir)
            assert result.success is False

    async def test_staged_diff(self) -> None:
        """Show staged changes."""
        tool = DiffViewTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            import subprocess

            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=tmpdir,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=tmpdir,
                capture_output=True,
            )
            f = Path(tmpdir) / "hello.py"
            f.write_text("x = 1\n")
            subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "init"],
                cwd=tmpdir,
                capture_output=True,
            )
            f.write_text("x = 3\n")
            subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True)
            result = await tool.execute(cwd=tmpdir, staged=True)
            assert result.success is True
            assert "x = 3" in result.content
