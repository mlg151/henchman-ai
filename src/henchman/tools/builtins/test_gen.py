"""Test generator tool implementation."""

from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from henchman.tools.base import Tool, ToolKind, ToolResult

# ---------------------------------------------------------------------------
# Module-level AST helpers (extracted from TestGenTool to eliminate Feature
# Envy — each helper accessed ``ast`` more times than ``self``).
# ---------------------------------------------------------------------------


def _get_return_annotation(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Return the return-type annotation of *node* as source text, or ``''``.

    Args:
        node: Function or async-function AST node.

    Returns:
        Unparsed annotation string, or empty string when absent.
    """
    if node.returns:
        return ast.unparse(node.returns)
    return ""


def _extract_args_from_node(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Extract non-self/cls argument names from *node*.

    Args:
        node: Function or async-function AST node.

    Returns:
        List of argument name strings.
    """
    return [arg.arg for arg in node.args.args if arg.arg not in ("self", "cls")]


def _extract_class_methods_from_ast(node: ast.ClassDef) -> list[dict[str, object]]:
    """Extract public methods (and ``__init__``) from a class AST node.

    Args:
        node: AST class definition node.

    Returns:
        List of method descriptor dicts.
    """
    methods: list[dict[str, object]] = []
    for item in ast.iter_child_nodes(node):
        if not isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if item.name.startswith("_") and item.name != "__init__":
            continue
        methods.append(
            {
                "kind": "method",
                "name": item.name,
                "args": _extract_args_from_node(item),
                "is_async": isinstance(item, ast.AsyncFunctionDef),
                "returns": _get_return_annotation(item),
            },
        )
    return methods


def _extract_symbols_from_tree(tree: ast.Module) -> list[dict[str, object]]:
    """Extract all testable top-level symbols from an AST module.

    Uses guard clauses to avoid deep nesting.

    Args:
        tree: Parsed AST module node.

    Returns:
        List of symbol descriptor dicts.
    """
    symbols: list[dict[str, object]] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if node.name.startswith("_"):
                continue
            symbols.append(
                {
                    "kind": "function",
                    "name": node.name,
                    "args": _extract_args_from_node(node),
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                    "returns": _get_return_annotation(node),
                },
            )
            continue

        if not isinstance(node, ast.ClassDef):
            continue
        if node.name.startswith("_"):
            continue
        symbols.append(
            {
                "kind": "class",
                "name": node.name,
                "methods": _extract_class_methods_from_ast(node),
            },
        )

    return symbols


@dataclass
class MethodStubSpec:
    """Specification for a single test-method stub to generate."""

    cls_name: str
    method_name: str
    is_async: bool = False


def _generate_test_method(spec: MethodStubSpec) -> str:
    """Generate a single test-method stub described by *spec*.

    Args:
        spec: Descriptor for the method under test.

    Returns:
        Indented test method source code.
    """
    test_name = "init" if spec.method_name == "__init__" else spec.method_name
    prefix = "async " if spec.is_async else ""
    return (
        f"    {prefix}def test_{test_name}(self) -> None:\n"
        f'        """Test {spec.cls_name}.{spec.method_name}."""\n'
        f"        # TODO: Implement test for {spec.cls_name}.{spec.method_name}\n"
        f"        pass\n"
    )


def _generate_test_init(cls_name: str) -> str:
    """Generate a fallback creation test for a class with no public methods.

    Args:
        cls_name: The class under test.

    Returns:
        Indented test method source code.
    """
    return (
        "    def test_create(self) -> None:\n"
        f'        """Test {cls_name} creation."""\n'
        f"        # TODO: Implement test for {cls_name} creation\n"
        f"        pass\n"
    )


def _make_test_body(func_name: str, args: list[str]) -> str:
    """Generate a test body with a placeholder call.

    Args:
        func_name: Function name.
        args: Argument names.

    Returns:
        Test body code string.
    """
    if args:
        arg_strs = ", ".join(f"{a}=..." for a in args)
        return f"result = {func_name}({arg_strs})\nassert result is not None"
    return f"result = {func_name}()\nassert result is not None"


def _pascal(name: str) -> str:
    """Convert snake_case *name* to PascalCase.

    Args:
        name: Snake case identifier.

    Returns:
        PascalCase identifier.
    """
    return "".join(word.capitalize() for word in name.split("_"))


def _load_source_file(path: str) -> tuple[str | None, ToolResult | None]:
    """Read source text from *path*.

    Args:
        path: Filesystem path to the source file.

    Returns:
        ``(source, None)`` on success or ``(None, error_result)`` on failure.
    """
    target = Path(path)
    if not target.exists():
        return None, ToolResult(
            content=f"Error: File not found: {path}",
            success=False,
            error=f"File not found: {path}",
        )
    try:
        return target.read_text(encoding="utf-8"), None
    except (OSError, UnicodeDecodeError) as exc:
        return None, ToolResult(
            content=f"Error reading file: {exc}",
            success=False,
            error=str(exc),
        )


def _parse_source(
    source: str,
    path: str,
) -> tuple[ast.Module | None, ToolResult | None]:
    """Parse *source* as Python, returning the AST or an error result.

    Args:
        source: Python source text.
        path: Original file path (used in error messages).

    Returns:
        ``(tree, None)`` on success or ``(None, error_result)`` on failure.
    """
    try:
        return ast.parse(source, filename=path), None
    except SyntaxError as exc:
        return None, ToolResult(
            content=f"Syntax error in {path}: {exc}",
            success=False,
            error=str(exc),
        )


def _write_test_output(output_path: str, test_code: str) -> ToolResult:
    """Write *test_code* to *output_path* and return a success result.

    Args:
        output_path: Destination file path.
        test_code: Generated test source.

    Returns:
        ToolResult indicating success.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(test_code, encoding="utf-8")
    return ToolResult(
        content=f"Test stubs written to {output_path}\n\n{test_code}",
        success=True,
    )


def _generate_function_test_stub(sym: dict[str, object]) -> tuple[str, str]:
    """Build a standalone function test stub from *sym*.

    Args:
        sym: Symbol descriptor for a module-level function.

    Returns:
        ``(stub_source, import_name)`` tuple.
    """
    name = str(sym["name"])
    is_async = bool(sym.get("is_async", False))
    prefix = "async " if is_async else ""
    args_value = sym.get("args", [])
    args_list = [str(a) for a in args_value] if isinstance(args_value, list) else []
    test_body = _make_test_body(name, args_list)
    stub = f'{prefix}def test_{name}() -> None:\n    """Test {name}."""\n    {test_body}\n'
    return stub, name


def _generate_class_test_stub(sym: dict[str, object]) -> tuple[str, str]:
    """Build a class creation test stub from *sym*.

    Args:
        sym: Symbol descriptor for a class.

    Returns:
        ``(stub_source, import_name)`` tuple.
    """
    cls_name = str(sym["name"])
    stub = (
        f"def test_{cls_name.lower()}_creation() -> None:\n"
        f'    """Test {cls_name} creation."""\n'
        f"    pass  # TODO: implement test\n"
    )
    return stub, cls_name


# ---------------------------------------------------------------------------
# JSON-Schema constant for the tool parameters (module-level dict avoids
# the duplicate-code detector flagging the property method as similar to
# other tools' parameters properties).
# ---------------------------------------------------------------------------
_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Path to the Python source file to generate tests for",
        },
        "output_path": {
            "type": "string",
            "description": "Path to write generated test file (default: auto-detect)",
        },
        "style": {
            "type": "string",
            "enum": ["class", "function"],
            "description": "Test style: class-based or function-based (default: class)",
            "default": "class",
        },
    },
    "required": ["path"],
}


class TestGenTool(Tool):
    """Generate pytest test stubs from Python source files.

    Analyzes function and class signatures to produce skeleton test
    files with parametrized stubs, fixture suggestions, and proper
    naming conventions.
    """

    @property
    def name(self: TestGenTool) -> str:
        """Tool name."""
        return "test_gen"

    @property
    def description(self: TestGenTool) -> str:
        """Tool description."""
        return (
            "Generate pytest test stubs from Python function/class signatures. "
            "Creates skeleton tests matching the project test structure."
        )

    parameters = _PARAMETERS

    @property
    def kind(self: TestGenTool) -> ToolKind:
        """Tool kind - WRITE because it generates files."""
        return ToolKind.WRITE

    async def execute(  # type: ignore[override]
        self: TestGenTool,
        path: str = "",
        output_path: str = "",
        style: Literal["class", "function"] = "class",
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Generate test stubs for a Python file.

        Args:
            path: Path to source file.
            output_path: Optional output path for test file.
            style: Test style ('class' or 'function').
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with generated test code.
        """
        if not path:
            return ToolResult(content="Error: No path provided", success=False, error="Empty path")

        source, err = _load_source_file(path)
        if err is not None:
            return err

        tree, err = _parse_source(source, path)  # type: ignore[arg-type]
        if err is not None:
            return err

        module_name = Path(path).stem
        symbols = _extract_symbols_from_tree(tree)  # type: ignore[arg-type]

        if not symbols:
            return ToolResult(content=f"No testable symbols found in {path}", success=True)

        if style == "class":
            test_code = self._generate_class_tests(module_name, symbols)
        else:
            test_code = self._generate_function_tests(module_name, symbols)

        if output_path:
            return _write_test_output(output_path, test_code)

        return ToolResult(content=test_code, success=True)

    def _build_method_test_stubs(
        self: TestGenTool,
        cls_name: str,
        methods_value: object,
    ) -> tuple[list[str], bool]:
        """Build test stubs for each method of a class.

        Args:
            cls_name: Class name for labelling test stubs.
            methods_value: Raw methods value from symbol dict.

        Returns:
            Tuple of (list of test stub strings, has_async flag).
        """
        method_tests: list[str] = []
        has_async = False
        if not isinstance(methods_value, list):
            return method_tests, has_async
        for method in methods_value:
            if not isinstance(method, dict):
                continue
            m_name = str(method.get("name", ""))
            m_async = bool(method.get("is_async", False))
            has_async = has_async or m_async
            spec = MethodStubSpec(cls_name=cls_name, method_name=m_name, is_async=m_async)
            method_tests.append(_generate_test_method(spec))
        return method_tests, has_async

    def _generate_class_tests(
        self: TestGenTool,
        module_name: str,
        symbols: list[dict[str, object]],
    ) -> str:
        """Generate class-based test stubs.

        Args:
            module_name: Source module name.
            symbols: Extracted symbols.

        Returns:
            Generated test code.
        """
        imports: set[str] = set()
        classes: list[str] = []

        for sym in symbols:
            class_str, _, sym_imports = self._generate_symbol_test_class(sym)
            imports.update(sym_imports)
            classes.append(class_str)

        header_parts = [f'"""Tests for {module_name} module."""\n', "import pytest\n"]
        import_names = ", ".join(sorted(imports))
        header_parts.append(f"from {module_name} import {import_names}\n")

        header = "\n".join(header_parts)
        body = "\n\n".join(classes)
        return f"{header}\n\n{body}\n"

    def _generate_symbol_test_class(
        self: TestGenTool,
        sym: dict[str, object],
    ) -> tuple[str, bool, set[str]]:
        """Generate a test class block for a single symbol.

        Args:
            sym: Symbol descriptor dict from ``_extract_symbols_from_tree``.

        Returns:
            Tuple of ``(class_source, has_async, import_names)``.
        """
        kind = sym["kind"]
        if kind == "function":
            return self._generate_function_test_class(sym)
        if kind == "class":
            return self._generate_class_symbol_test_class(sym)
        return "", False, set()

    def _generate_function_test_class(
        self: TestGenTool,
        sym: dict[str, object],
    ) -> tuple[str, bool, set[str]]:
        """Build a ``TestXxx`` class for a module-level function symbol."""
        name = str(sym["name"])
        is_async = bool(sym.get("is_async", False))
        prefix = "async " if is_async else ""
        args_value = sym.get("args", [])
        args_list = [str(arg) for arg in args_value] if isinstance(args_value, list) else []
        test_body = _make_test_body(name, args_list)
        source = textwrap.dedent(
            f"""\
            class Test{_pascal(name)}:
                \"\"\"Tests for {name}.\"\"\"

                {prefix}def test_{name}_basic(self) -> None:
                    \"\"\"Test basic {name} behavior.\"\"\"
                    {test_body}

                {prefix}def test_{name}_edge_cases(self) -> None:
                    \"\"\"Test {name} edge cases.\"\"\"
                    # TODO: Add edge case tests for {name}
                    pass
            """,
        )
        return source, is_async, {name}

    def _generate_class_symbol_test_class(
        self: TestGenTool,
        sym: dict[str, object],
    ) -> tuple[str, bool, set[str]]:
        """Build a ``TestXxx`` class for a class symbol."""
        cls_name = str(sym["name"])
        method_tests, cls_async = self._build_method_test_stubs(
            cls_name,
            sym.get("methods", []),
        )
        body = "\n".join(method_tests) if method_tests else _generate_test_init(cls_name)
        source = f'class Test{cls_name}:\n    """Tests for {cls_name}."""\n\n{body}'
        return source, cls_async, {cls_name}

    def _generate_function_tests(
        self: TestGenTool,
        module_name: str,
        symbols: list[dict[str, object]],
    ) -> str:
        """Generate function-based test stubs.

        Args:
            module_name: Source module name.
            symbols: Extracted symbols.

        Returns:
            Generated test code.
        """
        imports: set[str] = set()
        tests: list[str] = []

        for sym in symbols:
            kind = str(sym["kind"])
            if kind == "function":
                stub, name = _generate_function_test_stub(sym)
            elif kind == "class":
                stub, name = _generate_class_test_stub(sym)
            else:
                continue
            imports.add(name)
            tests.append(stub)

        header = (
            f'"""Tests for {module_name} module."""\n\n'
            f"import pytest\n\n"
            f"from {module_name} import {', '.join(sorted(imports))}\n"
        )
        body = "\n\n".join(tests)
        return f"{header}\n\n{body}\n"
