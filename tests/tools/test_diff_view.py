"""Tests for diff_view tool."""

import tempfile
from pathlib import Path

from henchman.tools.base import ToolKind
from henchman.tools.builtins.diff_view import DiffParams, DiffViewTool


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

    async def test_compare_branches(self) -> None:
        """Compare two branches."""
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
            subprocess.run(
                ["git", "checkout", "-b", "feature"],
                cwd=tmpdir,
                capture_output=True,
            )
            f.write_text("x = 99\n")
            subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "feature"],
                cwd=tmpdir,
                capture_output=True,
            )
            # Compare master..feature
            result = await tool.execute(compare="master..feature", cwd=tmpdir)
            assert result.success is True
            assert "x = 99" in result.content

    async def test_stat_mode(self) -> None:
        """Show --stat summary."""
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
            result = await tool.execute(cwd=tmpdir, stat=True)
            assert result.success is True
            assert "hello.py" in result.content

    async def test_name_only_mode(self) -> None:
        """Show --name-only output."""
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
            result = await tool.execute(cwd=tmpdir, name_only=True)
            assert result.success is True
            assert "hello.py" in result.content

    async def test_context_lines(self) -> None:
        """Context lines parameter is passed to git."""
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
            f.write_text("line1\nline2\nline3\nline4\nline5\n")
            subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "init"],
                cwd=tmpdir,
                capture_output=True,
            )
            f.write_text("line1\nline2\nCHANGED\nline4\nline5\n")
            result = await tool.execute(cwd=tmpdir, context_lines=0)
            assert result.success is True
            assert "CHANGED" in result.content

    def test_build_command_defaults(self) -> None:
        """Build command with defaults produces basic diff."""
        tool = DiffViewTool()
        cmd = tool._build_command(DiffParams())
        assert cmd == ["git", "--no-pager", "diff"]

    def test_build_command_all_options(self) -> None:
        """Build command with all options."""
        tool = DiffViewTool()
        cmd = tool._build_command(
            DiffParams(
                path="file.py",
                staged=False,
                compare="a..b",
                stat=True,
                name_only=True,
                context_lines=5,
            )
        )
        assert "--stat" in cmd
        assert "--name-only" in cmd
        assert "-U5" in cmd
        assert "a..b" in cmd
        assert "file.py" in cmd

    def test_build_command_staged_ignored_with_compare(self) -> None:
        """Staged flag is ignored when compare is set."""
        tool = DiffViewTool()
        cmd = tool._build_command(DiffParams(staged=True, compare="main..dev"))
        assert "--cached" not in cmd
        assert "main..dev" in cmd

    async def test_output_truncation(self) -> None:
        """Large diff output is truncated."""
        from unittest.mock import AsyncMock, MagicMock, patch
        large_output = "+" + "x" * 200_000
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(large_output.encode(), b""))
        mock_process.returncode = 0
        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            from henchman.tools.builtins.diff_view import DiffViewTool
            tool = DiffViewTool()
            result = await tool.execute()
            assert result.success is True
            assert "truncated" in result.content

    async def test_git_not_installed(self) -> None:
        """Handle git not installed."""
        from unittest.mock import patch

        from henchman.tools.builtins.diff_view import DiffViewTool
        tool = DiffViewTool()
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError()):
            result = await tool.execute()
            assert result.success is False
            assert "not installed" in result.content

    async def test_git_timeout(self) -> None:
        """Handle git command timeout."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from henchman.tools.builtins.diff_view import DiffViewTool
        tool = DiffViewTool()
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(side_effect=TimeoutError())
        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await tool.execute()
            assert result.success is False
            assert "timed out" in result.content

    async def test_run_git_method(self) -> None:
        """DiffViewTool._run_git delegates to _run_git_command."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from henchman.tools.builtins.diff_view import DiffViewTool
        tool = DiffViewTool()
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"diff output", b""))
        mock_process.returncode = 0
        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await tool._run_git(["git", "diff"])
            assert result.success is True
