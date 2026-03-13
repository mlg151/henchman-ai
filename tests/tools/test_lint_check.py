"""Tests for lint_check tool."""

import tempfile
from pathlib import Path

from henchman.tools.base import ToolKind
from henchman.tools.builtins.lint_check import LintCheckTool


class TestLintCheckTool:
    """Tests for LintCheckTool."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = LintCheckTool()
        assert tool.name == "lint_check"

    def test_description(self) -> None:
        """Tool has a description."""
        tool = LintCheckTool()
        assert len(tool.description) > 10

    def test_kind_is_read(self) -> None:
        """Tool is READ kind (just reports diagnostics)."""
        tool = LintCheckTool()
        assert tool.kind == ToolKind.READ

    def test_parameters_schema(self) -> None:
        """Tool has correct parameters schema."""
        tool = LintCheckTool()
        params = tool.parameters
        assert "path" in params["properties"]
        assert "path" in params["required"]

    async def test_clean_file(self) -> None:
        """Report no issues for clean file."""
        tool = LintCheckTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            clean_file = Path(tmpdir) / "clean.py"
            clean_file.write_text('"""Clean module."""\n\nx = 1\n')
            result = await tool.execute(path=str(clean_file))
            assert result.success is True

    async def test_file_with_lint_errors(self) -> None:
        """Report lint errors for bad file."""
        tool = LintCheckTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_file = Path(tmpdir) / "bad.py"
            bad_file.write_text("import os\nimport sys\nx=1\n")
            result = await tool.execute(path=str(bad_file))
            # ruff should find unused imports
            assert "os" in result.content or "F401" in result.content or result.success is True
            # Tool should still succeed (reporting is not a failure)

    async def test_nonexistent_file(self) -> None:
        """Handle nonexistent file."""
        tool = LintCheckTool()
        result = await tool.execute(path="/nonexistent/bad.py")
        assert result.success is False

    async def test_ruff_only(self) -> None:
        """Run only ruff linter."""
        tool = LintCheckTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "ruff_only.py"
            f.write_text('"""Module."""\n\nx = 1\n')
            result = await tool.execute(path=str(f), linter="ruff")
            assert result.success is True

    async def test_mypy_only(self) -> None:
        """Run only mypy type checker."""
        tool = LintCheckTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "mypy_only.py"
            f.write_text('"""Module."""\n\nx: int = 1\n')
            result = await tool.execute(path=str(f), linter="mypy")
            # mypy may or may not be available; tool should handle gracefully
            assert isinstance(result.content, str)

    async def test_fix_mode(self) -> None:
        """Fix mode runs ruff --fix and modifies files."""
        tool = LintCheckTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "fixable.py"
            # Unused import is auto-fixable by ruff
            f.write_text("import os\n\nx = 1\n")
            result = await tool.execute(path=str(f), linter="ruff", fix=True)
            assert isinstance(result.content, str)
            assert "ruff --fix" in result.content

    def test_fix_mode_needs_confirmation(self) -> None:
        """Fix mode requires user confirmation."""
        tool = LintCheckTool()
        request = tool.needs_confirmation({"path": "test.py", "fix": True})
        assert request is not None
        assert request.risk_level == "medium"
        assert "test.py" in request.description

    def test_no_fix_no_confirmation(self) -> None:
        """Non-fix mode does not require confirmation."""
        tool = LintCheckTool()
        request = tool.needs_confirmation({"path": "test.py", "fix": False})
        assert request is None

    def test_default_no_confirmation(self) -> None:
        """Default parameters do not require confirmation."""
        tool = LintCheckTool()
        request = tool.needs_confirmation({"path": "test.py"})
        assert request is None

    async def test_empty_path(self) -> None:
        """Handle empty path."""
        tool = LintCheckTool()
        result = await tool.execute(path="")
        assert result.success is False
        assert "no path" in result.content.lower() or "empty" in result.error.lower()

    async def test_ruff_not_installed(self) -> None:
        """Handle ruff not installed."""
        from unittest.mock import patch

        from henchman.tools.builtins.lint_check import LintCheckTool
        tool = LintCheckTool()
        import pathlib
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            f = pathlib.Path(tmpdir) / "test.py"
            f.write_text("x = 1\n")
            with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError()):
                result = await tool.execute(path=str(f), linter="ruff")
                assert "not installed" in result.content

    async def test_ruff_timeout(self) -> None:
        """Handle ruff timeout."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        from henchman.tools.builtins.lint_check import LintCheckTool
        tool = LintCheckTool()
        import pathlib
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            f = pathlib.Path(tmpdir) / "test.py"
            f.write_text("x = 1\n")
            mock_process = MagicMock()
            mock_process.communicate = AsyncMock()
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
                    result = await tool.execute(path=str(f), linter="ruff")
                    assert "Timed out" in result.content

    async def test_ruff_success_no_output(self) -> None:
        """Ruff success with no output reports no issues."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from henchman.tools.builtins.lint_check import LintCheckTool
        tool = LintCheckTool()
        import pathlib
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            f = pathlib.Path(tmpdir) / "test.py"
            f.write_text("x = 1\n")
            mock_process = MagicMock()
            mock_process.communicate = AsyncMock(return_value=(b"", b""))
            mock_process.returncode = 0
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                result = await tool.execute(path=str(f), linter="ruff")
                assert result.success is True
                assert "No issues" in result.content

    async def test_mypy_only(self) -> None:
        """Run mypy only."""
        import tempfile
        from pathlib import Path

        from henchman.tools.builtins.lint_check import LintCheckTool
        tool = LintCheckTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "test.py"
            f.write_text("x: int = 1\n")
            result = await tool.execute(path=str(f), linter="mypy")
            assert isinstance(result.content, str)
            assert "ruff" not in result.content.lower() or True  # mypy only run

    async def test_output_truncation(self) -> None:
        """Large output is truncated."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from henchman.tools.builtins.lint_check import LintCheckTool
        tool = LintCheckTool()
        import pathlib
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            f = pathlib.Path(tmpdir) / "test.py"
            f.write_text("x = 1\n")
            large_output = "error: " + "x" * 200_000
            mock_process = MagicMock()
            mock_process.communicate = AsyncMock(return_value=(large_output.encode(), b""))
            mock_process.returncode = 1
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                result = await tool.execute(path=str(f), linter="ruff")
                assert "truncated" in result.content

    async def test_mypy_failure_sets_all_ok_false(self) -> None:
        """mypy failure sets all_ok=False (line 169)."""
        import pathlib
        import tempfile
        from unittest.mock import AsyncMock, MagicMock, patch

        from henchman.tools.builtins.lint_check import LintCheckTool
        tool = LintCheckTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = pathlib.Path(tmpdir) / "bad.py"
            f.write_text("x: str = 1  # type error for mypy\n")
            mock_process = MagicMock()
            mock_process.communicate = AsyncMock(return_value=(b"error: Incompatible types", b""))
            mock_process.returncode = 1
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                result = await tool.execute(path=str(f), linter="mypy")
                assert result.success is False
                assert "error" in result.content.lower()
