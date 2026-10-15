"""Tests for python_ast_helpers module."""
from __future__ import annotations

import ast

import pytest

from henchman.tools.builtins.python_ast_helpers import (
    add_assignments_section,
    add_functions_and_classes_sections,
    add_imports_section,
    format_class_node,
    format_decorator,
    format_function_node,
    format_import_node,
    generate_symbol_table,
    get_decorator_name,
    get_node_docstring,
)


class TestGetNodeDocstring:
    """Tests for get_node_docstring."""

    def test_function_with_docstring(self) -> None:
        """Extracts docstring from function."""
        tree = ast.parse('def foo():\n    """My docstring."""\n    pass\n')
        func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        result = get_node_docstring(func)
        assert result == "My docstring."

    def test_function_without_docstring(self) -> None:
        """Returns None for function without docstring."""
        tree = ast.parse("def foo():\n    pass\n")
        func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        result = get_node_docstring(func)
        assert result is None

    def test_non_matching_node_returns_none(self) -> None:
        """Returns None for non-function/class/module nodes."""
        node = ast.Constant(value=42)
        result = get_node_docstring(node)
        assert result is None

    def test_class_with_multiline_docstring(self) -> None:
        """Returns only first line of multiline docstring."""
        tree = ast.parse('class A:\n    """First line.\n    Second line.\n    """\n    pass\n')
        cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        result = get_node_docstring(cls)
        assert result == "First line."


class TestGetDecoratorName:
    """Tests for get_decorator_name."""

    def test_name_decorator(self) -> None:
        """Extracts name from ast.Name decorator."""
        tree = ast.parse("@staticmethod\ndef foo(): pass\n")
        func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        result = get_decorator_name(func.decorator_list[0])
        assert result == "staticmethod"

    def test_attribute_decorator(self) -> None:
        """Extracts attr from ast.Attribute decorator."""
        tree = ast.parse("@pytest.mark.asyncio\ndef foo(): pass\n")
        func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        result = get_decorator_name(func.decorator_list[0])
        assert result == "asyncio"

    def test_call_decorator(self) -> None:
        """Extracts name from ast.Call decorator."""
        tree = ast.parse("@app.route('/path')\ndef foo(): pass\n")
        func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        result = get_decorator_name(func.decorator_list[0])
        assert result == "route"

    def test_unknown_decorator(self) -> None:
        """Returns empty string for unknown decorator types."""
        node = ast.Constant(value="not a decorator")
        result = get_decorator_name(node)
        assert result == ""


class TestFormatDecorator:
    """Tests for format_decorator."""

    def test_name_decorator(self) -> None:
        """Formats ast.Name as its id."""
        tree = ast.parse("@staticmethod\ndef foo(): pass\n")
        func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        result = format_decorator(func.decorator_list[0])
        assert result == "staticmethod"

    def test_attribute_decorator(self) -> None:
        """Formats ast.Attribute as value.attr."""
        tree = ast.parse("@pytest.mark\ndef foo(): pass\n")
        func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        result = format_decorator(func.decorator_list[0])
        assert "mark" in result

    def test_call_decorator(self) -> None:
        """Formats ast.Call as func(...)."""
        tree = ast.parse("@route('/path')\ndef foo(): pass\n")
        func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        result = format_decorator(func.decorator_list[0])
        assert "(...)" in result

    def test_unknown_node(self) -> None:
        """Returns ? for unknown node types."""
        node = ast.Constant(value="x")
        result = format_decorator(node)
        assert result == "?"


class TestFormatClassNode:
    """Tests for format_class_node."""

    def test_class_without_docstring(self) -> None:
        """Formats class node without docstring."""
        tree = ast.parse("class Foo:\n    def method(self): pass\n")
        cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        result = format_class_node(cls, include_docstrings=False)
        assert any("Foo" in line for line in result)

    def test_class_with_nested_class(self) -> None:
        """Formats class with nested class."""
        source = (
            "class Outer:\n"
            "    class Inner:\n"
            "        def method(self): pass\n"
        )
        tree = ast.parse(source)
        outer = next(
            n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "Outer"
        )
        result = format_class_node(outer)
        assert any("Inner" in line for line in result)

    def test_class_without_docstring_flag(self) -> None:
        """include_docstrings=False skips docstrings."""
        source = 'class A:\n    """Docstring."""\n    pass\n'
        tree = ast.parse(source)
        cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        result = format_class_node(cls, include_docstrings=False)
        assert not any('"""' in line for line in result)


class TestAddAssignmentsSection:
    """Tests for add_assignments_section."""

    def test_annotated_assignment(self) -> None:
        """Adds annotated assignments."""
        tree = ast.parse("x: int = 5\n")
        sections: list[str] = []
        add_assignments_section(sections, tree)
        assert any("x" in s for s in sections)
        assert any("int" in s for s in sections)

    def test_regular_assignment(self) -> None:
        """Adds regular assignments."""
        tree = ast.parse("MY_CONST = 42\n")
        sections: list[str] = []
        add_assignments_section(sections, tree)
        assert any("MY_CONST" in s for s in sections)

    def test_no_assignments(self) -> None:
        """Does nothing when no assignments."""
        tree = ast.parse("def foo(): pass\n")
        sections: list[str] = []
        add_assignments_section(sections, tree)
        assert sections == []

    def test_annnassign_with_none_target_skipped(self) -> None:
        """AnnAssign with None target is skipped (228->223 branch)."""
        # Manually create AnnAssign with target=None to exercise the
        # 'elif isinstance(a, ast.Assign)' False branch
        tree = ast.Module(body=[], type_ignores=[])
        ann_node = ast.AnnAssign(
            target=None,  # type: ignore[arg-type]
            annotation=ast.Name(id="int", ctx=ast.Load()),
            value=None,
            simple=1,
        )
        ast.fix_missing_locations(ann_node)
        tree.body.append(ann_node)
        sections: list[str] = []
        add_assignments_section(sections, tree)
        # No assignment added since target is None


class TestGenerateSymbolTable:
    """Tests for generate_symbol_table."""

    def test_generates_full_table(self) -> None:
        """Generates a complete symbol table."""
        source = (
            '"""Module docstring."""\n'
            "import os\n"
            "X: int = 1\n"
            "def foo(): pass\n"
            "class Bar:\n"
            '    """Bar docstring."""\n'
            "    def method(self): pass\n"
        )
        tree = ast.parse(source)
        sections = generate_symbol_table(tree, "mymodule.py", include_docstrings=True)
        content = "\n".join(sections)
        assert "foo" in content
        assert "Bar" in content
        assert "import os" in content


class TestFormatFunctionNode:
    """Tests for format_function_node."""

    @pytest.mark.parametrize(
        ("definition", "expected_signature"),
        [
            (
                "def convert(value: int, /, offset: int = 2) -> int:",
                "def convert(value: int, /, offset: int=2) -> int",
            ),
            (
                "def select(*, required: str, limit: int = 10) -> str:",
                "def select(*, required: str, limit: int=10) -> str",
            ),
            (
                "async def fetch(url: str, /, timeout: float = 3.5, "
                "*paths: str, verify: bool = True, **headers: str) -> bytes:",
                "async def fetch(url: str, /, timeout: float=3.5, "
                "*paths: str, verify: bool=True, **headers: str) -> bytes",
            ),
            (
                "def collect(*items: int, **options: bool):",
                "def collect(*items: int, **options: bool)",
            ),
            (
                "def make(factory: type = dict, options: tuple = (1, 2)):",
                "def make(factory: type=dict, options: tuple=(1, 2))",
            ),
        ],
    )
    def test_complete_signature_preserves_call_contract(
        self, definition: str, expected_signature: str
    ) -> None:
        tree = ast.parse(definition + "\n    pass\n")
        function = tree.body[0]
        assert isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef))

        assert format_function_node(function) == [
            f"{expected_signature}  [L1-2]"
        ]

    def test_ordinary_signature_keeps_existing_format(self) -> None:
        tree = ast.parse(
            '@staticmethod\ndef convert(value: int) -> str:\n'
            '    """Convert the input."""\n'
            '    return str(value)\n'
        )
        function = tree.body[0]
        assert isinstance(function, ast.FunctionDef)
        assert format_function_node(function, indent=1, is_method=True) == [
            "  @staticmethod",
            "  def convert(value: int) -> str  [L2-4]  [staticmethod]",
            '    """Convert the input."""',
        ]

    def test_basic_function(self) -> None:
        """Formats a basic function definition."""
        tree = ast.parse("def foo(x: int) -> str:\n    pass\n")
        func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        result = format_function_node(func)
        assert any("foo" in line for line in result)

    def test_async_function(self) -> None:
        """Formats async function with async def."""
        tree = ast.parse("async def bar(): pass\n")
        func = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef))
        result = format_function_node(func)
        assert any("async def" in line for line in result)


class TestFormatImportNode:
    """Tests for format_import_node."""

    def test_simple_import(self) -> None:
        """Formats a simple import statement."""
        tree = ast.parse("import os\n")
        imp = next(n for n in ast.walk(tree) if isinstance(n, ast.Import))
        result = format_import_node(imp)
        assert "import os" in result

    def test_from_import(self) -> None:
        """Formats a from...import statement."""
        tree = ast.parse("from os.path import join\n")
        imp = next(n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom))
        result = format_import_node(imp)
        assert "from os.path import join" in result


class TestAddImportsSection:
    """Tests for add_imports_section."""

    def test_adds_imports(self) -> None:
        """Adds imports when present."""
        tree = ast.parse("import os\nimport sys\n")
        sections: list[str] = []
        add_imports_section(sections, tree)
        assert any("os" in s for s in sections)

    def test_no_imports(self) -> None:
        """Does nothing when no imports."""
        tree = ast.parse("x = 1\n")
        sections: list[str] = []
        add_imports_section(sections, tree)
        assert sections == []


class TestAddFunctionsAndClassesSections:
    """Tests for add_functions_and_classes_sections."""

    def test_adds_functions(self) -> None:
        """Adds function entries."""
        tree = ast.parse("def foo(): pass\n")
        sections: list[str] = []
        add_functions_and_classes_sections(sections, tree, include_docstrings=False)
        assert any("foo" in s for s in sections)

    def test_adds_classes(self) -> None:
        """Adds class entries."""
        tree = ast.parse("class MyClass: pass\n")
        sections: list[str] = []
        add_functions_and_classes_sections(sections, tree, include_docstrings=False)
        assert any("MyClass" in s for s in sections)
