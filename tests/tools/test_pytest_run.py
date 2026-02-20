"""Tests for pytest_run tool."""

import tempfile
from pathlib import Path

from henchman.tools.base import ToolKind
from henchman.tools.builtins.pytest_run import PytestRunTool


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
