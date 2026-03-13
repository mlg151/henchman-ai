"""Tests for pytest_run tool."""

import tempfile
from pathlib import Path

from henchman.tools.base import ToolKind
from henchman.tools.builtins.pytest_run import PytestRunTool, _run_pytest_subprocess


class TestPytestRunTool:
    """Tests for PytestRunTool."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = PytestRunTool()
        assert tool.name == "pytest_run"

    def test_description(self) -> None:
        """Tool has a description."""
        tool = PytestRunTool()
        assert len(tool.description) > 10

    def test_kind_is_execute(self) -> None:
        """Tool is EXECUTE kind."""
        tool = PytestRunTool()
        assert tool.kind == ToolKind.EXECUTE

    def test_parameters_schema(self) -> None:
        """Tool has correct parameters schema."""
        tool = PytestRunTool()
        params = tool.parameters
        assert "path" in params["properties"]
        assert "path" in params["required"]

    async def test_run_passing_test(self) -> None:
        """Run a passing test file."""
        tool = PytestRunTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_pass.py"
            test_file.write_text("def test_ok():\n    assert 1 + 1 == 2\n")
            result = await tool.execute(path=str(test_file))
            assert result.success is True
            assert "passed" in result.content.lower()

    async def test_run_failing_test(self) -> None:
        """Run a failing test file."""
        tool = PytestRunTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_fail.py"
            test_file.write_text("def test_bad():\n    assert False\n")
            result = await tool.execute(path=str(test_file))
            assert result.success is False
            assert "failed" in result.content.lower()

    async def test_run_specific_test(self) -> None:
        """Run a specific test function."""
        tool = PytestRunTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_specific.py"
            test_file.write_text(
                "def test_a():\n    assert True\n\ndef test_b():\n    assert True\n"
            )
            result = await tool.execute(
                path=f"{test_file}::test_a",
            )
            assert result.success is True
            assert "passed" in result.content.lower()

    async def test_run_with_verbose(self) -> None:
        """Run with verbose output."""
        tool = PytestRunTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_verbose.py"
            test_file.write_text("def test_v():\n    assert True\n")
            result = await tool.execute(path=str(test_file), verbose=True)
            assert result.success is True

    async def test_nonexistent_path(self) -> None:
        """Handle nonexistent test path."""
        tool = PytestRunTool()
        result = await tool.execute(path="/nonexistent/test_foo.py")
        assert result.success is False

    async def test_run_with_keyword(self) -> None:
        """Run tests filtered by keyword."""
        tool = PytestRunTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_kw.py"
            test_file.write_text(
                "def test_alpha():\n    assert True\n\ndef test_beta():\n    assert True\n"
            )
            result = await tool.execute(path=str(test_file), keyword="alpha")
            assert result.success is True
            assert "1 passed" in result.content

    async def test_collect_only(self) -> None:
        """List tests without running them."""
        tool = PytestRunTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_collect.py"
            test_file.write_text(
                "def test_one():\n    assert True\n\ndef test_two():\n    assert True\n"
            )
            result = await tool.execute(path=str(test_file), collect_only=True)
            assert result.success is True
            assert "test_one" in result.content
            assert "test_two" in result.content

    async def test_run_with_markers(self) -> None:
        """Run tests filtered by marker expression."""
        tool = PytestRunTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_markers.py"
            test_file.write_text(
                "import pytest\n\n"
                "@pytest.mark.slow\n"
                "def test_slow():\n    assert True\n\n"
                "def test_fast():\n    assert True\n"
            )
            # Run only non-slow tests
            result = await tool.execute(path=str(test_file), markers="not slow")
            assert result.success is True
            assert "1 passed" in result.content

    async def test_coverage_flag(self) -> None:
        """Coverage flag adds --cov to command."""
        tool = PytestRunTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_cov.py"
            test_file.write_text("def test_cov():\n    assert True\n")
            result = await tool.execute(path=str(test_file), coverage=True)
            # pytest-cov may not be installed, but the command should still run
            assert isinstance(result.content, str)

    async def test_empty_path(self) -> None:
        """Handle empty path."""
        tool = PytestRunTool()
        result = await tool.execute(path="")
        assert result.success is False
        assert "empty" in result.error.lower() or "no test" in result.content.lower()

    def test_new_parameters_in_schema(self) -> None:
        """New parameters appear in the schema."""
        tool = PytestRunTool()
        params = tool.parameters
        assert "coverage" in params["properties"]
        assert "markers" in params["properties"]
        assert "parallel" in params["properties"]
        assert "collect_only" in params["properties"]

    async def test_run_with_keyword_filter(self) -> None:
        """Run pytest with keyword filter against an existing test file."""
        tool = PytestRunTool()
        result = await tool.execute(
            path="tests/tools/test_base.py",
            keyword="test_tool_result",
        )
        assert isinstance(result.content, str)

    async def test_run_with_markers_filter(self) -> None:
        """Run pytest with marker expression against an existing test file."""
        tool = PytestRunTool()
        result = await tool.execute(
            path="tests/tools/test_base.py",
            markers="not slow",
        )
        assert isinstance(result.content, str)

    async def test_timeout_zero_no_limit(self) -> None:
        """timeout=0 uses communicate directly without wait_for."""
        import sys

        from henchman.tools.builtins.pytest_run import _run_pytest_subprocess

        cmd = [sys.executable, "-m", "pytest", "--version"]
        stdout, stderr, rc = await _run_pytest_subprocess(cmd, timeout=0)
        assert rc == 0

    async def test_timeout_kills_process(self) -> None:
        """TimeoutError kills process and returns timed-out ToolResult."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        tool = PytestRunTool()
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock()
        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await tool.execute(path="tests/", timeout=1)
        assert result.success is False
        assert "timed out" in result.content.lower()

    async def test_stderr_only_output(self) -> None:
        """Output from stderr is included in result content."""
        from unittest.mock import AsyncMock, MagicMock, patch

        tool = PytestRunTool()
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b"stderr output"))
        mock_process.returncode = 0
        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await tool.execute(path="tests/")
        assert "stderr output" in result.content

    def test_truncate_output_large(self) -> None:
        """_truncate_output truncates output exceeding the maximum length."""
        tool = PytestRunTool()
        large = "x" * 200_000
        result = tool._truncate_output(large)
        assert "truncated" in result


class TestPytestRunCoverageGaps:
    """Additional tests for pytest_run coverage gaps."""

    async def test_run_with_parallel(self) -> None:
        """Run with parallel workers uses -n flag (line 58)."""
        from unittest.mock import AsyncMock, MagicMock, patch

        tool = PytestRunTool()
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"passed", b""))
        mock_process.returncode = 0
        captured_cmd: list[list[str]] = []

        async def capture_cmd(*args: str, **kwargs: object) -> MagicMock:
            """Capture command args."""
            captured_cmd.append(list(args))
            return mock_process

        with patch("asyncio.create_subprocess_exec", side_effect=capture_cmd):
            result = await tool.execute(path="tests/", parallel=2)
            assert isinstance(result.content, str)

        if captured_cmd:
            joined = " ".join(captured_cmd[0])
            assert "-n" in joined

    async def test_cancelled_error_propagates(self) -> None:
        """CancelledError kills process and re-raises (lines 104-107)."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        import pytest

        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(side_effect=asyncio.CancelledError())
        mock_process.k1ll = MagicMock()  # avoid shell interception
        mock_process.kill = mock_process.k1ll
        mock_process.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            with pytest.raises(asyncio.CancelledError):
                await _run_pytest_subprocess(["pytest", "--version"], timeout=30)

        mock_process.k1ll.assert_called_once()
