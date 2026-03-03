"""Test generator tool implementation."""

import ast
import textwrap
from pathlib import Path

from henchman.tools.base import Tool, ToolKind, ToolResult


class TestGenTool(Tool):
    """Generate pytest test stubs from Python source files.

    Analyzes function and class signatures to produce skeleton test
    files with parametrized stubs, fixture suggestions, and proper
    naming conventions.
    """

    @property
    def name(self) -> str:
        """Tool name."""
        return "test_gen"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Generate pytest test stubs from Python function/class signatures. "
            "Creates skeleton tests matching the project test structure."
        )

    @property
    def parameters(self) -> dict[str, object]:
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
    def kind(self) -> ToolKind:
        """Tool kind - WRITE because it generates files."""
        return ToolKind.WRITE

    async def execute(  # type: ignore[override]
        self,
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
        if not target.exists():
            return ToolResult(
                content=f"Error: File not found: {path}",
                success=False,
                error=f"File not found: {path}",
            )

        try:
            source = target.read_text(encoding="utf-8")
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
        symbols = self._extract_symbols(tree)

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
            out.write_text(test_code, encoding="utf-8")
            return ToolResult(
                content=f"Test stubs written to {output_path}\n\n{test_code}",
                success=True,
            )

        return ToolResult(content=test_code, success=True)

    def _extract_symbols(self, tree: ast.Module) -> list[dict[str, object]]:
        """Extract testable symbols from AST.

        Args:
            tree: Parsed AST module.

        Returns:
            List of symbol dicts with name, kind, args, is_async, decorators.
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
                        "args": self._extract_args(node),
                        "is_async": isinstance(node, ast.AsyncFunctionDef),
                        "returns": self._get_return_annotation(node),
                    },
                )
            elif isinstance(node, ast.ClassDef):
                if node.name.startswith("_"):
                    continue
                methods: list[dict[str, object]] = []
                for item in ast.iter_child_nodes(node):
                    if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                        if item.name.startswith("_") and item.name != "__init__":
                            continue
                        methods.append(
                            {
                                "kind": "method",
                                "name": item.name,
                                "args": self._extract_args(item),
                                "is_async": isinstance(item, ast.AsyncFunctionDef),
                                "returns": self._get_return_annotation(item),
                            },
                        )
                symbols.append(
                    {
                        "kind": "class",
                        "name": node.name,
                        "methods": methods,
                    },
                )

        return symbols

    def _extract_args(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
        """Extract argument names from function definition.

        Args:
            node: Function AST node.

        Returns:
            List of argument names (excluding self/cls).
        """
        args: list[str] = []
        for arg in node.args.args:
            if arg.arg in ("self", "cls"):
                continue
            args.append(arg.arg)
        return args

    def _get_return_annotation(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Get return type annotation as string.

        Args:
            node: Function AST node.

        Returns:
            Return annotation string or empty.
        """
        if node.returns:
            return ast.unparse(node.returns)
        return ""

    def _generate_class_tests(
        self,
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
            kind = sym["kind"]
            if kind == "function":
                name = str(sym["name"])
                is_async = bool(sym.get("is_async", False))
                imports.add(name)
                if is_async:
                    has_async = True
                prefix = "async " if is_async else ""
                args_value = sym.get("args", [])
                args_list = [str(arg) for arg in args_value] if isinstance(args_value, list) else []
                test_body = self._make_test_body(name, args_list)
                classes.append(
                    textwrap.dedent(
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
                    ),
                )
            elif kind == "class":
                cls_name = str(sym["name"])
                imports.add(cls_name)
                methods_value = sym.get("methods", [])
                method_tests: list[str] = []

                if isinstance(methods_value, list):
                    for method in methods_value:
                        if isinstance(method, dict):
                            m_name = str(method.get("name", ""))
                            m_async = bool(method.get("is_async", False))
                            if m_async:
                                has_async = True

                            test_name = "init" if m_name == "__init__" else m_name
                            prefix = "async " if m_async else ""
                            method_tests.append(
                                f"    {prefix}def test_{test_name}(self) -> None:\n"
                                f'        """Test {cls_name}.{m_name}."""\n'
                                f'        # TODO: Implement test for {cls_name}.{m_name}\n'
                                f'        pass\n',
                            )

                body = (
                    "\n".join(method_tests)
                    if method_tests
                    else (
                        "    def test_create(self) -> None:\n"
                        f'        """Test {cls_name} creation."""\n'
                        f'        # TODO: Implement test for {cls_name} creation\n'
                        f'        pass\n'
                    )
                )
                classes.append(f'class Test{cls_name}:\n    """Tests for {cls_name}."""\n\n{body}')

        # Build header
        header_parts = [f'"""Tests for {module_name} module."""\n']
        if has_async:
            header_parts.append("import pytest\n")
        else:
            header_parts.append("import pytest\n")

        import_names = ", ".join(sorted(imports))
        header_parts.append(f"from {module_name} import {import_names}\n")

        header = "\n".join(header_parts)
        body = "\n\n".join(classes)
        return f"{header}\n\n{body}\n"

    def _generate_function_tests(
        self,
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
                    f'{prefix}def test_{name}() -> None:\n    """Test {name}."""\n    {test_body}\n',
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

    def _make_test_body(self, func_name: str, args: list[str]) -> str:
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

    def _pascal(self, name: str) -> str:
        """Convert snake_case to PascalCase.

        Args:
            name: Snake case name.

        Returns:
            PascalCase name.
        """
        return "".join(word.capitalize() for word in name.split("_"))
