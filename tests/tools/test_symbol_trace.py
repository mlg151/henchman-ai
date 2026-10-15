"""Tests for the symbol_trace tool."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from henchman.tools.base import ToolKind
from henchman.tools.builtins.symbol_trace import (
    SymbolTraceParams,
    SymbolTraceResult,
    SymbolTraceTool,
    _build_trace_report,
    _collect_annotations,
    _collect_python_files,
    _execute_symbol_trace,
    _find_definitions_in_file,
    _find_imports_in_file,
    _find_references_in_file,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def py_file(tmp_path: Path) -> Path:
    """Create a small Python file with various definitions."""
    src = textwrap.dedent("""\
        from os import path
        from typing import Optional
        import sys

        MY_CONST = 42

        class Foo:
            def bar(self) -> None:
                pass

        def baz(x: Foo) -> Optional[str]:
            return None

        result = baz(Foo())
    """)
    p = tmp_path / "sample.py"
    p.write_text(src)
    return p


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestCollectPythonFiles:
    """Tests for _collect_python_files."""

    def test_finds_py_files(self, tmp_path: Path) -> None:
        """Finds .py files under the root."""
        (tmp_path / "a.py").write_text("x=1")
        (tmp_path / "b.txt").write_text("text")
        files = _collect_python_files(tmp_path, include_tests=True)
        names = [f.name for f in files]
        assert "a.py" in names
        assert "b.txt" not in names

    def test_excludes_test_files(self, tmp_path: Path) -> None:
        """Excludes test files when include_tests=False."""
        (tmp_path / "mod.py").write_text("x=1")
        (tmp_path / "test_mod.py").write_text("pass")
        files = _collect_python_files(tmp_path, include_tests=False)
        names = [f.name for f in files]
        assert "mod.py" in names
        assert "test_mod.py" not in names

    def test_includes_test_files(self, tmp_path: Path) -> None:
        """Includes test files when include_tests=True."""
        (tmp_path / "test_mod.py").write_text("pass")
        files = _collect_python_files(tmp_path, include_tests=True)
        names = [f.name for f in files]
        assert "test_mod.py" in names


class TestFindDefinitionsInFile:
    """Tests for _find_definitions_in_file."""

    def test_finds_function_definition(self, py_file: Path) -> None:
        """Finds function definition."""
        defs = _find_definitions_in_file(py_file, "baz")
        assert len(defs) >= 1
        assert defs[0].kind == "function"
        assert "baz" in defs[0].signature

    def test_finds_class_definition(self, py_file: Path) -> None:
        """Finds class definition."""
        defs = _find_definitions_in_file(py_file, "Foo")
        assert len(defs) >= 1
        assert defs[0].kind == "class"

    def test_finds_variable_definition(self, py_file: Path) -> None:
        """Finds variable assignment."""
        defs = _find_definitions_in_file(py_file, "MY_CONST")
        assert len(defs) >= 1
        assert defs[0].kind == "variable"

    def test_missing_symbol_returns_empty(self, py_file: Path) -> None:
        """Returns empty list when symbol not found."""
        defs = _find_definitions_in_file(py_file, "NoSuchSymbol")
        assert defs == []

    def test_syntax_error_file(self, tmp_path: Path) -> None:
        """Returns empty list for files with syntax errors."""
        bad = tmp_path / "bad.py"
        bad.write_text("def bad(")
        defs = _find_definitions_in_file(bad, "bad")
        assert defs == []

    def test_finds_decorated_function_definition(self, tmp_path: Path) -> None:
        """Finds decorated function and extracts correct signature."""
        src = textwrap.dedent("""\
            from typing import Optional

            @decorator
            def decorated_func(x: int) -> Optional[str]:
                return str(x) if x > 0 else None
        """)
        p = tmp_path / "decorated.py"
        p.write_text(src)

        defs = _find_definitions_in_file(p, "decorated_func")
        assert len(defs) == 1
        assert defs[0].kind == "function"
        # BUG: Currently returns "@decorator" instead of "def decorated_func(x: int) -> Optional[str]:"
        # The signature should contain "decorated_func" and show the function signature
        assert "decorated_func" in defs[0].signature
        assert "def decorated_func" in defs[0].signature
        # Should NOT be just the decorator
        assert defs[0].signature != "@decorator"


class TestFindImportsInFile:
    """Tests for _find_imports_in_file."""

    def test_finds_from_import(self, py_file: Path) -> None:
        """Finds 'from X import Y' for symbol Y."""
        refs = _find_imports_in_file(py_file, "path")
        assert len(refs) >= 1
        assert any("from os import path" in r.context for r in refs)

    def test_finds_regular_import(self, py_file: Path) -> None:
        """Finds 'import X' for symbol X."""
        refs = _find_imports_in_file(py_file, "sys")
        assert len(refs) >= 1

    def test_missing_import_returns_empty(self, py_file: Path) -> None:
        """Returns empty list when symbol not imported."""
        refs = _find_imports_in_file(py_file, "NotImported")
        assert refs == []

    def test_syntax_error_file(self, tmp_path: Path) -> None:
        """Returns empty list for files with syntax errors."""
        bad = tmp_path / "bad.py"
        bad.write_text("def bad(")
        refs = _find_imports_in_file(bad, "anything")
        assert refs == []


class TestFindReferencesInFile:
    """Tests for _find_references_in_file."""

    def test_finds_references(self, py_file: Path) -> None:
        """Finds lines containing the symbol name."""
        refs = _find_references_in_file(py_file, "Foo")
        assert len(refs) >= 1

    def test_missing_symbol_returns_empty(self, py_file: Path) -> None:
        """Returns empty list when symbol not referenced."""
        refs = _find_references_in_file(py_file, "CompletelyAbsent")
        assert refs == []

    def test_references_have_context(self, py_file: Path) -> None:
        """Each reference includes the line content."""
        refs = _find_references_in_file(py_file, "baz")
        for ref in refs:
            assert "baz" in ref.context


class TestCollectAnnotations:
    """Tests for _collect_annotations."""

    def test_finds_return_annotations(self, py_file: Path) -> None:
        """Finds return type annotations containing symbol."""
        # Optional is used as return annotation
        annotations = _collect_annotations([py_file], "Optional")
        assert any("Optional" in a for a in annotations)

    def test_finds_param_annotations(self, py_file: Path) -> None:
        """Finds parameter annotations containing symbol."""
        annotations = _collect_annotations([py_file], "Foo")
        assert any("Foo" in a for a in annotations)

    def test_missing_symbol_returns_empty(self, py_file: Path) -> None:
        """Returns empty list when symbol not in annotations."""
        annotations = _collect_annotations([py_file], "NeverAnnotated")
        assert annotations == []

    def test_finds_all_argument_type_annotations(self, tmp_path: Path) -> None:
        """Finds annotations in posonlyargs, vararg, and kwarg parameters."""
        src = """
from typing import Tuple, Dict

def example_func(
    pos_only: int, /,
    normal: str,
    *args: Tuple[int, ...],
    kw_only: float = 0.0,
    **kwargs: Dict[str, bool],
) -> None:
    pass
"""
        p = tmp_path / "modern.py"
        p.write_text(src)

        # Test collecting annotations for "int"
        int_annotations = _collect_annotations([p], "int")
        assert any("int" in a for a in int_annotations), \
            f"Should find 'int' in annotations: {int_annotations}"

        # Test collecting annotations for "Tuple"
        tuple_annotations = _collect_annotations([p], "Tuple")
        assert any("Tuple" in a for a in tuple_annotations), \
            f"Should find 'Tuple' in annotations: {tuple_annotations}"

        # Test collecting annotations for "Dict"
        dict_annotations = _collect_annotations([p], "Dict")
        assert any("Dict" in a for a in dict_annotations), \
            f"Should find 'Dict' in annotations: {dict_annotations}"


class TestBuildTraceReport:
    """Tests for _build_trace_report."""

    def test_report_has_symbol_name(self) -> None:
        """Report title contains the symbol name."""
        trace = SymbolTraceResult(symbol="my_func")
        report = _build_trace_report(trace)
        assert "my_func" in report

    def test_report_shows_counts(self) -> None:
        """Report shows definition, import, and reference counts."""
        trace = SymbolTraceResult(symbol="x")
        report = _build_trace_report(trace)
        assert "Definitions:" in report
        assert "Import sites:" in report
        assert "Reference sites:" in report

    def test_not_found_message(self) -> None:
        """Shows 'not found' when no results."""
        trace = SymbolTraceResult(symbol="ghost")
        report = _build_trace_report(trace)
        assert "not found" in report.lower()


class TestExecuteSymbolTrace:
    """Tests for _execute_symbol_trace."""

    def test_missing_path(self) -> None:
        """Returns error for non-existent path."""
        params = SymbolTraceParams(symbol="foo", path="/no/such/path")
        result = _execute_symbol_trace(params)
        assert result.success is False

    def test_traces_symbol(self, tmp_path: Path, py_file: Path) -> None:
        """Returns a report for a found symbol."""
        params = SymbolTraceParams(symbol="Foo", path=str(tmp_path))
        result = _execute_symbol_trace(params)
        assert result.success is True
        assert "Foo" in result.content

    def test_single_file_path(self, py_file: Path) -> None:
        """Accepts a single file path."""
        params = SymbolTraceParams(symbol="baz", path=str(py_file))
        result = _execute_symbol_trace(params)
        assert result.success is True


# ---------------------------------------------------------------------------
# Tool class tests
# ---------------------------------------------------------------------------


class TestSymbolTraceTool:
    """Tests for the SymbolTraceTool class."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = SymbolTraceTool()
        assert tool.name == "symbol_trace"

    def test_description(self) -> None:
        """Tool has a description."""
        tool = SymbolTraceTool()
        assert "symbol" in tool.description.lower() or "trace" in tool.description.lower()

    def test_kind_is_read(self) -> None:
        """Tool is READ kind (auto-approved)."""
        tool = SymbolTraceTool()
        assert tool.kind == ToolKind.READ

    def test_parameters_schema(self) -> None:
        """Parameters schema has required 'symbol' field."""
        tool = SymbolTraceTool()
        params = tool.parameters
        assert "symbol" in params["properties"]
        assert "symbol" in params["required"]

    async def test_execute_empty_symbol(self) -> None:
        """Returns error when symbol is empty."""
        tool = SymbolTraceTool()
        result = await tool.execute(symbol="")
        assert result.success is False

    async def test_execute_found(self, tmp_path: Path, py_file: Path) -> None:
        """Returns successful trace for found symbol."""
        tool = SymbolTraceTool()
        result = await tool.execute(symbol="Foo", path=str(tmp_path))
        assert result.success is True

    async def test_execute_ignores_extra_kwargs(self, tmp_path: Path, py_file: Path) -> None:
        """Extra kwargs are silently ignored."""
        tool = SymbolTraceTool()
        result = await tool.execute(symbol="Foo", path=str(tmp_path), unknown="ignored")
        assert result.success is True
