"""Tests for test_gen tool."""

import tempfile
from pathlib import Path

from henchman.tools.base import ToolKind
from henchman.tools.builtins.test_gen import TestGenTool


class TestTestGenTool:
    """Tests for TestGenTool."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = TestGenTool()
        assert tool.name == "test_gen"

    def test_description(self) -> None:
        """Tool has a description."""
        tool = TestGenTool()
        assert len(tool.description) > 10

    def test_kind_is_write(self) -> None:
        """Tool is WRITE kind."""
        tool = TestGenTool()
        assert tool.kind == ToolKind.WRITE

    def test_parameters_schema(self) -> None:
        """Tool has correct parameters schema."""
        tool = TestGenTool()
        params = tool.parameters
        assert "path" in params["properties"]
        assert "path" in params["required"]

    async def test_generate_for_functions(self) -> None:
        """Generate tests for functions."""
        tool = TestGenTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "calculator.py"
            f.write_text(
                "def add(a: int, b: int) -> int:\n"
                '    """Add two numbers."""\n'
                "    return a + b\n\n"
                "def subtract(a: int, b: int) -> int:\n"
                "    return a - b\n"
            )
            result = await tool.execute(path=str(f))
            assert result.success is True
            assert "test_add" in result.content
            assert "test_subtract" in result.content
            assert "import pytest" in result.content

    async def test_generate_for_class(self) -> None:
        """Generate tests for a class."""
        tool = TestGenTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "myclass.py"
            f.write_text(
                "class Calculator:\n"
                "    def __init__(self) -> None:\n"
                "        self.result = 0\n\n"
                "    def add(self, value: int) -> int:\n"
                "        self.result += value\n"
                "        return self.result\n"
            )
            result = await tool.execute(path=str(f))
            assert result.success is True
            assert "TestCalculator" in result.content
            assert "test_init" in result.content or "test_add" in result.content

    async def test_function_style(self) -> None:
        """Generate function-based tests."""
        tool = TestGenTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "utils.py"
            f.write_text("def greet(name: str) -> str:\n    return f'Hello {name}'\n")
            result = await tool.execute(path=str(f), style="function")
            assert result.success is True
            assert "def test_greet" in result.content
            assert "class Test" not in result.content

    async def test_async_function(self) -> None:
        """Generate tests for async functions."""
        tool = TestGenTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "async_mod.py"
            f.write_text("async def fetch(url: str) -> str:\n    return ''\n")
            result = await tool.execute(path=str(f))
            assert result.success is True
            assert "async def test_fetch" in result.content

    async def test_write_output_file(self) -> None:
        """Write generated tests to a file."""
        tool = TestGenTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "module.py"
            f.write_text("def process(data: list) -> list:\n    return data\n")
            out = Path(tmpdir) / "tests" / "test_module.py"
            result = await tool.execute(path=str(f), output_path=str(out))
            assert result.success is True
            assert out.exists()
            content = out.read_text()
            assert "test_process" in content

    async def test_no_testable_symbols(self) -> None:
        """Handle file with no testable symbols."""
        tool = TestGenTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "empty.py"
            f.write_text("x = 1\n_private = 2\n")
            result = await tool.execute(path=str(f))
            assert result.success is True
            assert "No testable symbols" in result.content

    async def test_nonexistent_file(self) -> None:
        """Handle nonexistent file."""
        tool = TestGenTool()
        result = await tool.execute(path="/nonexistent/module.py")
        assert result.success is False

    async def test_empty_path(self) -> None:
        """Handle empty path."""
        tool = TestGenTool()
        result = await tool.execute(path="")
        assert result.success is False

    async def test_syntax_error(self) -> None:
        """Handle file with syntax errors."""
        tool = TestGenTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "broken.py"
            f.write_text("def foo(\n")
            result = await tool.execute(path=str(f))
            assert result.success is False

    def test_pascal_case(self) -> None:
        """Test _pascal helper."""
        tool = TestGenTool()
        assert tool._pascal("hello_world") == "HelloWorld"
        assert tool._pascal("simple") == "Simple"
        assert tool._pascal("a_b_c") == "ABC"

    async def test_private_excluded(self) -> None:
        """Private functions are excluded from test generation."""
        tool = TestGenTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "mod.py"
            f.write_text("def public():\n    pass\n\n" "def _private():\n    pass\n")
            result = await tool.execute(path=str(f))
            assert result.success is True
            assert "test_public" in result.content
            assert "_private" not in result.content
