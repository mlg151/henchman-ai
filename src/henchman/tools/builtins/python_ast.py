"""Python AST analysis tool implementation."""

from __future__ import annotations
import ast
from pathlib import Path

from henchman.tools.base import Tool, ToolKind, ToolResult


class PythonAstTool(Tool):
    """Parse a Python file and return its symbol table.

    Extracts classes, functions, methods, imports, decorators,
    line ranges, docstrings, and method classifications — giving agents
    a structural map of a file without reading its full contents.
    """

    @property
    def name(self: PythonAstTool) -> str:
        """Tool name."""
        return "python_ast"

    @property
    def description(self: PythonAstTool) -> str:
        """Tool description."""
        return (
            "Parse a Python file and return its symbol table: classes, "
            "functions, methods, imports, decorators, line ranges, "
            "docstrings, and method types (static/classmethod/property/abstract). "
            "Use this to understand file structure without reading the full contents."
        )

    @property
    def parameters(self: PythonAstTool) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the Python file to analyze",
                },
                "include_docstrings": {
                    "type": "boolean",
                    "description": "Include first-line docstrings in output",
                    "default": True,
                },
            },
            "required": ["path"],
        }

    @property
    def kind(self: PythonAstTool) -> ToolKind:
        """Tool kind - READ is auto-approved."""
        return ToolKind.READ

    def _get_docstring(self: PythonAstTool, node: ast.AST) -> str | None:
        """Extract the first line of a docstring from a node.

        Args:
            node: AST node (function, class, or module).

        Returns:
            First line of docstring, or None.
        """
        # ast.get_docstring only works with specific node types
        get_docstring = ast.get_docstring
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            docstring = get_docstring(node)
            if docstring:
                return docstring.split("\n")[0].strip()
        return None

    def _get_decorator_name(self: PythonAstTool, d: ast.expr) -> str:
        """Extract the base name from a decorator node.

        Args:
            d: Decorator AST node.

        Returns:
            The decorator's base name, or empty string if not determinable.
        """
        if isinstance(d, ast.Name):
            return d.id
        if isinstance(d, ast.Attribute):
            return d.attr
        if isinstance(d, ast.Call):
            return self._get_decorator_name(d.func)
        return ""

    def _classify_method(self: PythonAstTool, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Classify a method by its decorators.

        Args:
            node: AST function node.

        Returns:
            Classification string (e.g., "staticmethod", "classmethod", "property").
        """
        _known = ("staticmethod", "classmethod", "property", "abstractmethod")
        tags = [
            name
            for d in node.decorator_list
            if (name := self._get_decorator_name(d)) in _known
        ]
        return ", ".join(tags)

    def _format_decorator(self: PythonAstTool, node: ast.expr) -> str:
        """Format a decorator node to string.

        Args:
            node: AST decorator node.

        Returns:
            String representation of the decorator.
        """
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{self._format_decorator(node.value)}.{node.attr}"
        if isinstance(node, ast.Call):
            return f"{self._format_decorator(node.func)}(...)"
        return "?"

    def _format_function(
        self: PythonAstTool,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        indent: int = 0,
        include_docstrings: bool = True,
        is_method: bool = False,
    ) -> list[str]:
        """Format a function/method definition.

        Args:
            node: AST function node.
            indent: Indentation level.
            include_docstrings: Include docstring in output.
            is_method: Whether this is a method inside a class.

        Returns:
            List of formatted lines.
        """
        prefix = "  " * indent
        ast_unparse = ast.unparse
        node_name = node.name
        node_lineno = node.lineno
        kind = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"

        # Build signature
        args = []
        for arg in node.args.args:
            annotation = ""
            if arg.annotation:
                annotation = f": {ast_unparse(arg.annotation)}"
            args.append(f"{arg.arg}{annotation}")

        returns = ""
        if node.returns:
            returns = f" -> {ast_unparse(node.returns)}"

        decos = [f"{prefix}@{self._format_decorator(d)}" for d in node.decorator_list]

        end_line = node.end_lineno or node_lineno
        sig = f"{prefix}{kind} {node_name}({', '.join(args)}){returns}"

        # Add method classification tag
        tag = ""
        if is_method:
            classification = self._classify_method(node)
            if classification:
                tag = f"  [{classification}]"

        lines = [*decos, f"{sig}  [L{node_lineno}-{end_line}]{tag}"]

        if include_docstrings:
            docstring = self._get_docstring(node)
            if docstring:
                lines.append(f'{prefix}  """{docstring}"""')

        return lines

    def _format_class(
        self: PythonAstTool, node: ast.ClassDef, indent: int = 0, include_docstrings: bool = True,
    ) -> list[str]:
        """Format a class definition with its methods.

        Args:
            node: AST class node.
            indent: Indentation level.
            include_docstrings: Include docstrings in output.

        Returns:
            List of formatted lines.
        """
        prefix = "  " * indent
        ast_unparse = ast.unparse
        node_name = node.name
        node_lineno = node.lineno
        bases = [ast_unparse(b) for b in node.bases]
        bases_str = f"({', '.join(bases)})" if bases else ""

        decos = [f"{prefix}@{self._format_decorator(d)}" for d in node.decorator_list]

        end_line = node.end_lineno or node_lineno
        lines = [*decos, f"{prefix}class {node_name}{bases_str}  [L{node_lineno}-{end_line}]"]

        if include_docstrings:
            docstring = self._get_docstring(node)
            if docstring:
                lines.append(f'{prefix}  """{docstring}"""')

        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                lines.extend(
                    self._format_function(
                        child,
                        indent + 1,
                        include_docstrings=include_docstrings,
                        is_method=True,
                    ),
                )
            elif isinstance(child, ast.ClassDef):
                lines.extend(
                    self._format_class(child, indent + 1, include_docstrings=include_docstrings),
                )

        return lines

    def _format_import(self: PythonAstTool, node: ast.Import | ast.ImportFrom) -> str:
        """Format an import statement.

        Args:
            node: AST import node.

        Returns:
            Formatted import string.
        """
        node_lineno = node.lineno
        node_names = node.names
        names = ", ".join(a.name + (f" as {a.asname}" if a.asname else "") for a in node_names)
        if isinstance(node, ast.Import):
            return f"import {names}  [L{node_lineno}]"
        # ImportFrom
        module = node.module or ""
        level = "." * (node.level or 0)
        return f"from {level}{module} import {names}  [L{node_lineno}]"

    async def execute(  # type: ignore[override]
        self: PythonAstTool,
        path: str = "",
        include_docstrings: bool = True,
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Parse a Python file and return its symbol table.

        Args:
            path: Path to the Python file.
            include_docstrings: Include first-line docstrings in output.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with the symbol table.
        """
        return await self._parse_python_file(path, include_docstrings)

    async def _parse_python_file(self: PythonAstTool, path: str, include_docstrings: bool) -> ToolResult:  # noqa: E501
        """Orchestrate the parsing of a Python file.

        Args:
            path: Path to the Python file.
            include_docstrings: Include first-line docstrings in output.

        Returns:
            ToolResult with the symbol table.
        """
        # Validate input
        validation_error = self._validate_path(path)
        if validation_error is not None:
            return validation_error

        # Read file
        file_path = Path(path)
        try:
            source = file_path.read_text()
        except PermissionError:
            return ToolResult(
                content=f"Error: Permission denied: {path}",
                success=False,
                error=f"Permission denied: {path}",
            )

        # Parse AST
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as e:
            return ToolResult(
                content=f"Syntax error in {path}: {e}",
                success=False,
                error=str(e),
            )

        # Generate symbol table
        sections = self._generate_symbol_table(tree, file_path.name, include_docstrings)

        return ToolResult(
            content="\n".join(sections),
            success=True,
        )

    def _validate_path(self: PythonAstTool, path: str) -> ToolResult | None:
        """Validate the provided file path.

        Args:
            path: Path to validate.

        Returns:
            ToolResult with error if validation fails, None if valid.
        """
        if not path:
            return ToolResult(
                content="Error: No path provided",
                success=False,
                error="Empty path",
            )

        file_path = Path(path)
        if not file_path.exists():
            return ToolResult(
                content=f"Error: File not found: {path}",
                success=False,
                error=f"File not found: {path}",
            )

        return None

    def _generate_symbol_table(
        self: PythonAstTool, tree: ast.Module, file_name: str, include_docstrings: bool,
    ) -> list[str]:
        """Generate symbol table sections from AST.

        Args:
            tree: AST module node.
            file_name: Name of the file being analyzed.
            include_docstrings: Include first-line docstrings in output.

        Returns:
            List of formatted sections.
        """
        sections: list[str] = [f"# Symbol table for {file_name}"]

        # Module docstring
        self._add_module_docstring(sections, tree, include_docstrings)

        # Imports
        self._add_imports_section(sections, tree)

        # Top-level assignments
        self._add_assignments_section(sections, tree)

        # Functions and classes
        self._add_functions_and_classes_sections(sections, tree, include_docstrings)

        return sections

    def _add_module_docstring(
        self: PythonAstTool, sections: list[str], tree: ast.Module, include_docstrings: bool,
    ) -> None:
        """Add module docstring to sections if present and requested.

        Args:
            sections: List to append to.
            tree: AST module node.
            include_docstrings: Whether to include docstrings.
        """
        if include_docstrings:
            module_doc = self._get_docstring(tree)
            if module_doc:
                sections.append(f'"""{module_doc}"""')

    def _add_imports_section(self: PythonAstTool, sections: list[str], tree: ast.Module) -> None:
        """Add imports section to sections if imports exist.

        Args:
            sections: List to append to.
            tree: AST module node.
        """
        imports = [
            n for n in ast.iter_child_nodes(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
        ]
        if imports:
            sections.append("\n## Imports")
            sections.extend(self._format_import(imp) for imp in imports)

    def _add_assignments_section(self: PythonAstTool, sections: list[str], tree: ast.Module) -> None:  # noqa: E501
        """Add assignments section to sections if assignments exist.

        Args:
            sections: List to append to.
            tree: AST module node.
        """
        ast_unparse = ast.unparse
        AnnAssign = ast.AnnAssign
        Assign = ast.Assign
        assigns = [
            n for n in ast.iter_child_nodes(tree) if isinstance(n, (Assign, AnnAssign))
        ]
        if assigns:
            sections.append("\n## Constants / Variables")
            for a in assigns:
                a_lineno = a.lineno
                if isinstance(a, AnnAssign) and a.target:
                    name = ast_unparse(a.target)
                    ann = ast_unparse(a.annotation) if a.annotation else "?"
                    sections.append(f"{name}: {ann}  [L{a_lineno}]")
                elif isinstance(a, Assign):
                    names = ", ".join(ast_unparse(t) for t in a.targets)
                    sections.append(f"{names}  [L{a_lineno}]")

    def _add_functions_and_classes_sections(
        self: PythonAstTool, sections: list[str], tree: ast.Module, include_docstrings: bool,
    ) -> None:
        """Add functions and classes sections to sections.

        Args:
            sections: List to append to.
            tree: AST module node.
            include_docstrings: Include first-line docstrings in output.
        """
        FunctionDef = ast.FunctionDef
        AsyncFunctionDef = ast.AsyncFunctionDef
        ClassDef = ast.ClassDef
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (FunctionDef, AsyncFunctionDef)):
                sections.append("")
                sections.extend(
                    self._format_function(node, include_docstrings=include_docstrings),
                )
            elif isinstance(node, ClassDef):
                sections.append("")
                sections.extend(
                    self._format_class(node, include_docstrings=include_docstrings),
                )
