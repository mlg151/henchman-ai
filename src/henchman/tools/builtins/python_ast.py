"""Python AST analysis tool implementation."""

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
    def name(self) -> str:
        """Tool name."""
        return "python_ast"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Parse a Python file and return its symbol table: classes, "
            "functions, methods, imports, decorators, line ranges, "
            "docstrings, and method types (static/classmethod/property/abstract). "
            "Use this to understand file structure without reading the full contents."
        )

    @property
    def parameters(self) -> dict[str, object]:
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
    def kind(self) -> ToolKind:
        """Tool kind - READ is auto-approved."""
        return ToolKind.READ

    def _get_docstring(self, node: ast.AST) -> str | None:
        """Extract the first line of a docstring from a node.

        Args:
            node: AST node (function, class, or module).

        Returns:
            First line of docstring, or None.
        """
        docstring = ast.get_docstring(node)
        if docstring:
            return docstring.split("\n")[0].strip()
        return None

    def _classify_method(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Classify a method by its decorators.

        Args:
            node: AST function node.

        Returns:
            Classification string (e.g., "staticmethod", "classmethod", "property").
        """
        tags = []
        for d in node.decorator_list:
            name = ""
            if isinstance(d, ast.Name):
                name = d.id
            elif isinstance(d, ast.Attribute):
                name = d.attr
            elif isinstance(d, ast.Call):
                if isinstance(d.func, ast.Name):
                    name = d.func.id
                elif isinstance(d.func, ast.Attribute):
                    name = d.func.attr
            if name in ("staticmethod", "classmethod", "property", "abstractmethod"):
                tags.append(name)
        return ", ".join(tags)

    def _format_decorator(self, node: ast.expr) -> str:
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
        self,
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
        kind = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"

        # Build signature
        args = []
        for arg in node.args.args:
            annotation = ""
            if arg.annotation:
                annotation = f": {ast.unparse(arg.annotation)}"
            args.append(f"{arg.arg}{annotation}")

        returns = ""
        if node.returns:
            returns = f" -> {ast.unparse(node.returns)}"

        decos = [f"{prefix}@{self._format_decorator(d)}" for d in node.decorator_list]

        end_line = node.end_lineno or node.lineno
        sig = f"{prefix}{kind} {node.name}({', '.join(args)}){returns}"

        # Add method classification tag
        tag = ""
        if is_method:
            classification = self._classify_method(node)
            if classification:
                tag = f"  [{classification}]"

        lines = [*decos, f"{sig}  [L{node.lineno}-{end_line}]{tag}"]

        if include_docstrings:
            docstring = self._get_docstring(node)
            if docstring:
                lines.append(f"{prefix}  \"\"\"{docstring}\"\"\"")

        return lines

    def _format_class(
        self, node: ast.ClassDef, indent: int = 0, include_docstrings: bool = True
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
        bases = [ast.unparse(b) for b in node.bases]
        bases_str = f"({', '.join(bases)})" if bases else ""

        decos = [f"{prefix}@{self._format_decorator(d)}" for d in node.decorator_list]

        end_line = node.end_lineno or node.lineno
        lines = [*decos, f"{prefix}class {node.name}{bases_str}  [L{node.lineno}-{end_line}]"]

        if include_docstrings:
            docstring = self._get_docstring(node)
            if docstring:
                lines.append(f"{prefix}  \"\"\"{docstring}\"\"\"")

        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                lines.extend(
                    self._format_function(
                        child,
                        indent + 1,
                        include_docstrings=include_docstrings,
                        is_method=True,
                    )
                )
            elif isinstance(child, ast.ClassDef):
                lines.extend(
                    self._format_class(child, indent + 1, include_docstrings=include_docstrings)
                )

        return lines

    def _format_import(self, node: ast.Import | ast.ImportFrom) -> str:
        """Format an import statement.

        Args:
            node: AST import node.

        Returns:
            Formatted import string.
        """
        if isinstance(node, ast.Import):
            names = ", ".join(a.name + (f" as {a.asname}" if a.asname else "") for a in node.names)
            return f"import {names}  [L{node.lineno}]"
        # ImportFrom
        module = node.module or ""
        level = "." * (node.level or 0)
        names = ", ".join(a.name + (f" as {a.asname}" if a.asname else "") for a in node.names)
        return f"from {level}{module} import {names}  [L{node.lineno}]"

    async def execute(  # type: ignore[override]
        self,
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

        try:
            source = file_path.read_text()
        except PermissionError:
            return ToolResult(
                content=f"Error: Permission denied: {path}",
                success=False,
                error=f"Permission denied: {path}",
            )

        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as e:
            return ToolResult(
                content=f"Syntax error in {path}: {e}",
                success=False,
                error=str(e),
            )

        sections: list[str] = [f"# Symbol table for {file_path.name}"]

        # Module docstring
        if include_docstrings:
            module_doc = self._get_docstring(tree)
            if module_doc:
                sections.append(f'"""{module_doc}"""')

        # Imports
        imports = [
            n for n in ast.iter_child_nodes(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
        ]
        if imports:
            sections.append("\n## Imports")
            for imp in imports:
                sections.append(self._format_import(imp))

        # Top-level assignments
        assigns = [
            n for n in ast.iter_child_nodes(tree) if isinstance(n, (ast.Assign, ast.AnnAssign))
        ]
        if assigns:
            sections.append("\n## Constants / Variables")
            for a in assigns:
                if isinstance(a, ast.AnnAssign) and a.target:
                    name = ast.unparse(a.target)
                    ann = ast.unparse(a.annotation) if a.annotation else "?"
                    sections.append(f"{name}: {ann}  [L{a.lineno}]")
                elif isinstance(a, ast.Assign):
                    names = ", ".join(ast.unparse(t) for t in a.targets)
                    sections.append(f"{names}  [L{a.lineno}]")

        # Functions and classes
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sections.append("")
                sections.extend(
                    self._format_function(node, include_docstrings=include_docstrings)
                )
            elif isinstance(node, ast.ClassDef):
                sections.append("")
                sections.extend(
                    self._format_class(node, include_docstrings=include_docstrings)
                )

        return ToolResult(
            content="\n".join(sections),
            success=True,
        )
