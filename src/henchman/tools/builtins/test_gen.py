"""Test generator tool implementation."""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

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


def _generate_test_method(cls_name: str, method_name: str, is_async: bool) -> str:
    """Generate a single test-method stub for *method_name* on *cls_name*.

    Args:
        cls_name: The class under test (used in the docstring).
        method_name: The method being tested.
        is_async: Whether the test should be an ``async def``.

    Returns:
        Indented test method source code.
    """
    test_name = "init" if method_name == "__init__" else method_name
    prefix = "async " if is_async else ""
    return (
        f"    {prefix}def test_{test_name}(self) -> None:\n"
        f'        """Test {cls_name}.{method_name}."""\n'
        f"        # TODO: Implement test for {cls_name}.{method_name}\n"
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

    @property
    def parameters(self: TestGenTool) -> dict[str, object]:  # noqa
        """JSON Schema for parameters."""
        return {
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

    @property
    def kind(self: TestGenTool) -> ToolKind:
        """Tool kind - WRITE because it generates files."""
        return ToolKind.WRITE

    async def execute(  # type: ignore[override]  # noqa: PLR0911
        self: TestGenTool,
        path: str = "",
        output_path: str = "",
        style: str = "class",
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
            return ToolResult(
                content="Error: No path provided",
                success=False,
                error="Empty path",
            )

        target = Path(path)
        if not target.exists():  # noqa: ASYNC240
            return ToolResult(
                content=f"Error: File not found: {path}",
                success=False,
                error=f"File not found: {path}",
            )

        try:
            source = target.read_text(encoding="utf-8")  # noqa: ASYNC240
        except (OSError, UnicodeDecodeError) as exc:
            return ToolResult(
                content=f"Error reading file: {exc}",
                success=False,
                error=str(exc),
            )

        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as exc:
            return ToolResult(
                content=f"Syntax error in {path}: {exc}",
                success=False,
                error=str(exc),
            )

        module_name = target.stem
        symbols = _extract_symbols_from_tree(tree)

        if not symbols:
            return ToolResult(
                content=f"No testable symbols found in {path}",
                success=True,
            )

        if style == "class":
            test_code = self._generate_class_tests(module_name, symbols)
        else:
            test_code = self._generate_function_tests(module_name, symbols)

        # Write or return
        if output_path:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(test_code, encoding="utf-8")  # noqa: ASYNC240
            return ToolResult(
                content=f"Test stubs written to {output_path}\n\n{test_code}",
                success=True,
            )

        return ToolResult(content=test_code, success=True)

    def _extract_class_methods(
        self: TestGenTool,
        node: ast.ClassDef,
    ) -> list[dict[str, object]]:
        """Delegate to module-level ``_extract_class_methods_from_ast``."""
        return _extract_class_methods_from_ast(node)

    def _extract_symbols(self: TestGenTool, tree: ast.Module) -> list[dict[str, object]]:
        """Delegate to module-level ``_extract_symbols_from_tree``."""
        return _extract_symbols_from_tree(tree)

    def _extract_args(self: TestGenTool, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
        """Delegate to module-level ``_extract_args_from_node``."""
        return _extract_args_from_node(node)

    def _get_return_annotation(self: TestGenTool, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:  # noqa: E501
        """Delegate to module-level ``_get_return_annotation``."""
        return _get_return_annotation(node)

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
            method_tests.append(_generate_test_method(cls_name, m_name, m_async))
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
        has_async = False
        classes: list[str] = []

        for sym in symbols:
            class_str, sym_async, sym_imports = self._generate_symbol_test_class(sym)
            has_async = has_async or sym_async
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
        test_body = self._make_test_body(name, args_list)
        source = textwrap.dedent(
            f"""\
            class Test{self._pascal(name)}:
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
            cls_name, sym.get("methods", []),
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
            name = str(sym["name"])

            if kind == "function":
                is_async = bool(sym.get("is_async", False))
                imports.add(name)
                prefix = "async " if is_async else ""
                args_value = sym.get("args", [])
                args_list = [str(arg) for arg in args_value] if isinstance(args_value, list) else []
                test_body = self._make_test_body(name, args_list)
                tests.append(
                    f'{prefix}def test_{name}() -> None:\n    """Test {name}."""\n    {test_body}\n',  # noqa: E501
                )
            elif kind == "class":
                cls_name = str(sym["name"])
                imports.add(cls_name)
                tests.append(
                    f"def test_{cls_name.lower()}_creation() -> None:\n"
                    f'    """Test {cls_name} creation."""\n'
                    f'    pass  # TODO: implement test\n',
                )

        header = (
            f'"""Tests for {module_name} module."""\n\n'
            f"import pytest\n\n"
            f"from {module_name} import {', '.join(sorted(imports))}\n"
        )
        body = "\n\n".join(tests)
        return f"{header}\n\n{body}\n"

    def _make_test_body(self: TestGenTool, func_name: str, args: list[str]) -> str:
        """Generate a test body with placeholder call.

        Args:
            func_name: Function name.
            args: Argument names.

        Returns:
            Test body code.
        """
        if args:
            arg_strs = ", ".join(f"{a}=..." for a in args)
            return f"result = {func_name}({arg_strs})\nassert result is not None"
        return f"result = {func_name}()\nassert result is not None"

    def _pascal(self: TestGenTool, name: str) -> str:
        """Convert snake_case to PascalCase.

        Args:
            name: Snake case name.

        Returns:
            PascalCase name.
        """
        return "".join(word.capitalize() for word in name.split("_"))
