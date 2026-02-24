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

    async def test_docstrings_extracted(self) -> None:
        """Docstrings appear in output by default."""
        tool = PythonAstTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "docs.py"
            f.write_text(
                '"""Module level docstring."""\n\n'
                "def greet(name: str) -> str:\n"
                '    """Greet someone nicely."""\n'
                '    return f"Hello, {name}!"\n\n\n'
                "class Animal:\n"
                '    """Represents an animal."""\n\n'
                "    def speak(self) -> str:\n"
                '        """Make a sound."""\n'
                '        return "..."\n'
            )
            result = await tool.execute(path=str(f))
            assert result.success is True
            assert "Module level docstring" in result.content
            assert "Greet someone nicely" in result.content
            assert "Represents an animal" in result.content
            assert "Make a sound" in result.content

    async def test_docstrings_disabled(self) -> None:
        """Docstrings omitted when include_docstrings=False."""
        tool = PythonAstTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "nodocs.py"
            f.write_text(
                '"""Module docstring."""\n\n'
                "def greet():\n"
                '    """Hello."""\n'
                "    pass\n"
            )
            result = await tool.execute(path=str(f), include_docstrings=False)
            assert result.success is True
            assert "greet" in result.content
            # Docstrings should NOT appear
            assert '"""Module docstring' not in result.content
            assert '"""Hello' not in result.content

    async def test_method_classification(self) -> None:
        """Methods are classified by decorator type."""
        tool = PythonAstTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "methods.py"
            f.write_text(
                "from abc import abstractmethod\n\n"
                "class Foo:\n"
                "    @staticmethod\n"
                "    def static_method() -> None:\n"
                "        pass\n\n"
                "    @classmethod\n"
                "    def class_method(cls) -> None:\n"
                "        pass\n\n"
                "    @property\n"
                "    def prop(self) -> int:\n"
                "        return 0\n\n"
                "    @abstractmethod\n"
                "    def abstract(self) -> None:\n"
                "        pass\n\n"
                "    def regular(self) -> None:\n"
                "        pass\n"
            )
            result = await tool.execute(path=str(f))
            assert result.success is True
            assert "staticmethod" in result.content
            assert "classmethod" in result.content
            assert "property" in result.content
            assert "abstractmethod" in result.content

    async def test_empty_path(self) -> None:
        """Handle empty path."""
        tool = PythonAstTool()
        result = await tool.execute(path="")
        assert result.success is False

    def test_include_docstrings_in_schema(self) -> None:
        """New parameter appears in schema."""
        tool = PythonAstTool()
        params = tool.parameters
        assert "include_docstrings" in params["properties"]
