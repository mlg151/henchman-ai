"""Python AST analysis tool implementation."""

from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path
from threading import Event

from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.builtins.python_ast_helpers import generate_symbol_table
from henchman.tools.utils import validate_file_path

_PYTHON_AST_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Python file to inspect, or directory for action=quality",
        },
        "action": {
            "type": "string",
            "enum": ["symbols", "quality"],
            "default": "symbols",
            "description": "Symbol table or bounded duplicate/long-method/nesting analysis",
        },
        "max_files": {"type": "integer", "minimum": 1, "maximum": 5000, "default": 500},
        "max_findings": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
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
            "Use action=quality on a file or directory for syntax-clone candidates, "
            "long methods and deep nesting, with locations and explicit scan limits."
        )

    parameters = _PYTHON_AST_PARAMETERS

    @property
    def kind(self: PythonAstTool) -> ToolKind:
        """Tool kind - READ is auto-approved."""
        return ToolKind.READ

    async def execute(  # type: ignore[override]
        self: PythonAstTool,
        path: str = "",
        *,
        include_docstrings: bool = True,
        action: str = "symbols",
        max_files: int = 500,
        max_findings: int = 100,
        **kwargs: object,
    ) -> ToolResult:
        """Parse a Python file and return its symbol table.

        Args:
            path: Path to the Python file.
            include_docstrings: Include first-line docstrings in output.
            action: Symbol table (default) or bounded quality scan.
            max_files: Quality scan file budget.
            max_findings: Quality scan finding budget.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with the symbol table.
        """
        if action not in ("symbols", "quality"):
            return ToolResult(content="Unknown python_ast action", success=False, error="Invalid action")
        if action == "quality":
            return await _quality_result(path, max_files, max_findings)

        validation_error = validate_file_path(path)
        if validation_error is not None:
            return validation_error

        file_path = Path(path)
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

        sections = generate_symbol_table(
            tree,
            file_path.name,
            include_docstrings=include_docstrings,
        )
        return ToolResult(content="\n".join(sections), success=True)


async def _quality_result(path: str, max_files: int, max_findings: int) -> ToolResult:
    """Run bounded analysis off the event loop, stopping traversal on cancellation."""
    from henchman.analysis.smells.scanner import ScanOptions, scan_quality

    try:
        if not isinstance(path, str) or not path.strip():
            raise ValueError("path must be a nonempty string")
        options = ScanOptions(max_files=max_files, max_findings=max_findings)
    except ValueError as exc:
        return ToolResult(content=str(exc), success=False, error=str(exc))
    stop = Event()
    try:
        report = await asyncio.to_thread(scan_quality, path, options, stop)
    finally:
        stop.set()
    return ToolResult(
        content=json.dumps(report.to_dict(), ensure_ascii=False),
        success=report.complete,
        error=None if report.complete else "Quality scan incomplete; inspect errors and limits",
    )
