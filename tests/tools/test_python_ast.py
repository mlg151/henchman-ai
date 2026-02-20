"""Tests for python_ast tool."""

import tempfile
from pathlib import Path

from henchman.tools.base import ToolKind
from henchman.tools.builtins.python_ast import PythonAstTool


class TestPythonAstTool:
    """Tests for PythonAstTool."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = PythonAstTool()
        assert tool.name == "python_ast"

    def test_description(self) -> None:
        """Tool has a description."""
        tool = PythonAstTool()
        assert len(tool.description) > 10

    def test_kind_is_read(self) -> None:
        """Tool is READ kind."""
        tool = PythonAstTool()
        assert tool.kind == ToolKind.READ

    def test_parameters_schema(self) -> None:
        """Tool has correct parameters schema."""
        tool = PythonAstTool()
        params = tool.parameters
        assert "path" in params["properties"]
        assert "path" in params["required"]

    async def test_parse_simple_file(self) -> None:
        """Parse a simple Python file with functions and classes."""
        tool = PythonAstTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "example.py"
            f.write_text(
                '"""Module docstring."""\n\n'
                "import os\n\n"
                "X = 42\n\n\n"
                "def greet(name: str) -> str:\n"
                '    """Greet someone."""\n'
                '    return f"Hello, {name}!"\n\n\n'
                "class Foo:\n"
                '    """A foo class."""\n\n'
                "    def __init__(self, x: int) -> None:\n"
                "        self.x = x\n\n"
                "    def bar(self) -> int:\n"
                "        return self.x\n"
            )
            result = await tool.execute(path=str(f))
            assert result.success is True
            assert "greet" in result.content
            assert "Foo" in result.content
            assert "bar" in result.content
            assert "__init__" in result.content

    async def test_parse_shows_line_numbers(self) -> None:
        """Output includes line numbers for symbols."""
        tool = PythonAstTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "lines.py"
            f.write_text("def alpha():\n    pass\n\n\ndef beta():\n    pass\n")
            result = await tool.execute(path=str(f))
            assert result.success is True
            # Should contain line references
            assert "1" in result.content  # alpha starts at line 1
            assert "5" in result.content  # beta starts at line 5

    async def test_parse_shows_imports(self) -> None:
        """Output includes import statements."""
        tool = PythonAstTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "imports.py"
            f.write_text("import os\nfrom pathlib import Path\n\nx = 1\n")
            result = await tool.execute(path=str(f))
            assert result.success is True
            assert "os" in result.content
            assert "Path" in result.content

    async def test_parse_decorators(self) -> None:
        """Output includes decorators."""
        tool = PythonAstTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "deco.py"
            f.write_text(
                "from functools import lru_cache\n\n@lru_cache\ndef cached():\n    return 42\n"
            )
            result = await tool.execute(path=str(f))
            assert result.success is True
            assert "cached" in result.content
            assert "lru_cache" in result.content

    async def test_nonexistent_file(self) -> None:
        """Handle nonexistent file."""
        tool = PythonAstTool()
        result = await tool.execute(path="/nonexistent/foo.py")
        assert result.success is False

    async def test_syntax_error_file(self) -> None:
        """Handle file with syntax errors."""
        tool = PythonAstTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "broken.py"
            f.write_text("def foo(\n")
            result = await tool.execute(path=str(f))
            assert result.success is False
            assert "syntax" in result.content.lower() or "error" in result.content.lower()

    async def test_empty_file(self) -> None:
        """Handle empty file."""
        tool = PythonAstTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "empty.py"
            f.write_text("")
            result = await tool.execute(path=str(f))
            assert result.success is True
