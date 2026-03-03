"""Python AST analysis tool implementation."""

from __future__ import annotations

import ast
from pathlib import Path

from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.builtins.python_ast_helpers import generate_symbol_table
from henchman.tools.utils import validate_file_path

_PYTHON_AST_PARAMETERS: dict[str, object] = {
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
        return _PYTHON_AST_PARAMETERS

    @property
    def kind(self: PythonAstTool) -> ToolKind:
        """Tool kind - READ is auto-approved."""
        return ToolKind.READ

    async def execute(  # type: ignore[override]
        self: PythonAstTool,
        path: str = "",
        *,
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
        validation_error = validate_file_path(path)
        if validation_error is not None:
            return validation_error

        file_path = Path(path)
        try:
            source = file_path.read_text()  # noqa: ASYNC240
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

        sections = generate_symbol_table(
            tree,
            file_path.name,
            include_docstrings=include_docstrings,
        )
        return ToolResult(content="\n".join(sections), success=True)
