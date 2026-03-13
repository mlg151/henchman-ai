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
        """Test module-level _pascal helper."""
        from henchman.tools.builtins.test_gen import _pascal

        assert _pascal("hello_world") == "HelloWorld"
        assert _pascal("simple") == "Simple"
        assert _pascal("a_b_c") == "ABC"

    async def test_private_excluded(self) -> None:
        """Private functions are excluded from test generation."""
        tool = TestGenTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "mod.py"
            f.write_text("def public():\n    pass\n\ndef _private():\n    pass\n")
            result = await tool.execute(path=str(f))
            assert result.success is True
            assert "test_public" in result.content
            assert "_private" not in result.content

    async def test_generate_function_style(self) -> None:
        """Generate function-based test stubs."""
        tool = TestGenTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "calc.py"
            f.write_text("def add(a, b):\n    return a + b\n")
            result = await tool.execute(path=str(f), style="function")
            assert result.success is True
            assert "def test_add" in result.content

    async def test_generate_function_style_with_class(self) -> None:
        """Function-style generates creation test for classes."""
        tool = TestGenTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "mymod.py"
            f.write_text("class MyClass:\n    def method(self): pass\n")
            result = await tool.execute(path=str(f), style="function")
            assert result.success is True
            assert "myclass" in result.content.lower() or "MyClass" in result.content

    async def test_file_read_error(self) -> None:
        """Handle file read error gracefully."""
        import unittest.mock as mock

        tool = TestGenTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "bad.py"
            f.write_text("def foo(): pass\n")
            with mock.patch("pathlib.Path.read_text", side_effect=OSError("Permission denied")):
                result = await tool.execute(path=str(f))
                assert result.success is False
                assert "Error reading" in result.content

    async def test_class_with_no_public_methods_gets_create_test(self) -> None:
        """Class with only private methods gets a creation test."""
        tool = TestGenTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "priv.py"
            f.write_text("class Priv:\n    def _private(self): pass\n")
            result = await tool.execute(path=str(f))
            assert result.success is True
            assert "test_create" in result.content

    async def test_private_functions_excluded(self) -> None:
        """Private functions are not included in test stubs."""
        tool = TestGenTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "mod.py"
            f.write_text("def _private(): pass\ndef public(): pass\n")
            result = await tool.execute(path=str(f))
            assert result.success is True
            assert "_private" not in result.content
            assert "public" in result.content

    async def test_output_path_writes_file(self) -> None:
        """Test stubs written to output_path."""
        tool = TestGenTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "src.py"
            src.write_text("def greet(name): return f'hi {name}'\n")
            out = Path(tmpdir) / "tests" / "test_src.py"
            result = await tool.execute(path=str(src), output_path=str(out))
            assert result.success is True
            assert out.exists()


class TestTestGenInternals:
    """Tests for test_gen module-level helpers."""

    def test_extract_class_methods_skips_private(self) -> None:
        """_extract_class_methods_from_ast skips private methods."""
        import ast

        from henchman.tools.builtins.test_gen import _extract_class_methods_from_ast

        tree = ast.parse("class A:\n    def _private(self): pass\n    def public(self): pass\n")
        cls_node = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        methods = _extract_class_methods_from_ast(cls_node)
        names = [m["name"] for m in methods]
        assert "public" in names
        assert "_private" not in names

    def test_extract_class_methods_includes_init(self) -> None:
        """_extract_class_methods_from_ast includes __init__."""
        import ast

        from henchman.tools.builtins.test_gen import _extract_class_methods_from_ast

        tree = ast.parse("class A:\n    def __init__(self): pass\n")
        cls_node = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        methods = _extract_class_methods_from_ast(cls_node)
        names = [m["name"] for m in methods]
        assert "__init__" in names

    def test_extract_symbols_skips_private_functions(self) -> None:
        """_extract_symbols_from_tree skips private functions."""
        import ast

        from henchman.tools.builtins.test_gen import _extract_symbols_from_tree

        tree = ast.parse("def _hidden(): pass\ndef visible(): pass\n")
        symbols = _extract_symbols_from_tree(tree)
        names = [s["name"] for s in symbols]
        assert "visible" in names
        assert "_hidden" not in names

    def test_generate_test_init(self) -> None:
        """_generate_test_init produces a creation test."""
        from henchman.tools.builtins.test_gen import _generate_test_init

        result = _generate_test_init("MyClass")
        assert "test_create" in result
        assert "MyClass" in result

    def test_extract_class_methods_delegate(self) -> None:
        """_extract_class_methods_from_ast works via module-level function."""
        import ast

        from henchman.tools.builtins.test_gen import _extract_class_methods_from_ast

        tree = ast.parse("class A:\n    def method(self): pass\n")
        cls_node = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        methods = _extract_class_methods_from_ast(cls_node)
        assert len(methods) > 0

    def test_extract_symbols_delegate(self) -> None:
        """_extract_symbols_from_tree works via module-level function."""
        import ast

        from henchman.tools.builtins.test_gen import _extract_symbols_from_tree

        tree = ast.parse("def foo(): pass\n")
        symbols = _extract_symbols_from_tree(tree)
        assert len(symbols) > 0

    def test_extract_args_delegate(self) -> None:
        """_extract_args_from_node works via module-level function."""
        import ast

        from henchman.tools.builtins.test_gen import _extract_args_from_node

        tree = ast.parse("def foo(a, b, c): pass\n")
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        args = _extract_args_from_node(func_node)
        assert args == ["a", "b", "c"]

    def test_get_return_annotation_delegate(self) -> None:
        """_get_return_annotation works via module-level function."""
        import ast

        from henchman.tools.builtins.test_gen import _get_return_annotation

        tree = ast.parse("def foo() -> int: pass\n")
        func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        ann = _get_return_annotation(func_node)
        assert ann == "int"

    def test_build_method_test_stubs_non_list(self) -> None:
        """_build_method_test_stubs handles non-list methods gracefully."""
        tool = TestGenTool()
        stubs, has_async = tool._build_method_test_stubs("MyClass", "not-a-list")
        assert stubs == []
        assert has_async is False

    def test_build_method_test_stubs_non_dict_skipped(self) -> None:
        """_build_method_test_stubs skips non-dict items in list."""
        tool = TestGenTool()
        stubs, has_async = tool._build_method_test_stubs("MyClass", ["not_a_dict", 42])
        assert stubs == []

    def test_generate_symbol_test_class_unknown_kind(self) -> None:
        """_generate_symbol_test_class returns empty for unknown kind."""
        tool = TestGenTool()
        result = tool._generate_symbol_test_class({"kind": "unknown", "name": "foo"})
        assert result == ("", False, set())


class TestTestGenCoverageGaps:
    """Additional tests for test_gen coverage gaps."""

    def test_extract_class_methods_non_func_child(self) -> None:
        """_extract_class_methods_from_ast skips non-function children (line 55)."""
        import ast

        from henchman.tools.builtins.test_gen import _extract_class_methods_from_ast

        # Class with a class variable (non-function child)
        tree = ast.parse("class A:\n    x = 1\n    def method(self): pass\n")
        cls_node = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        methods = _extract_class_methods_from_ast(cls_node)
        names = [m["name"] for m in methods]
        assert "method" in names
        assert len(methods) == 1  # x = 1 should be skipped

    def test_extract_symbols_private_class_skipped(self) -> None:
        """_extract_symbols_from_tree skips private classes (line 100)."""
        import ast

        from henchman.tools.builtins.test_gen import _extract_symbols_from_tree

        tree = ast.parse("class _Private:\n    pass\nclass Public:\n    pass\n")
        symbols = _extract_symbols_from_tree(tree)
        names = [s["name"] for s in symbols]
        assert "Public" in names
        assert "_Private" not in names

    async def test_generate_function_style_class_symbols(self) -> None:
        """Function-style: unknown kind skips elif class block (449->435)."""
        tool = TestGenTool()
        # Directly call _generate_function_tests with kind="other" to hit 449->435
        symbols = [
            {"kind": "other", "name": "foo"},
        ]
        result = tool._generate_function_tests("mymod", symbols)
        # Unknown kind - no tests generated for it
        assert isinstance(result, str)

    async def test_generate_function_style_class_execute(self) -> None:
        """Function-style generates creation test for class symbols."""
        import tempfile
        from pathlib import Path

        tool = TestGenTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "mymod.py"
            f.write_text("class MyClass:\n    def method(self): pass\n\ndef helper(): pass\n")
            result = await tool.execute(path=str(f), style="function")
            assert result.success is True
            assert "myclass" in result.content.lower()
