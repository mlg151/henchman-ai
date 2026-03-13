"""File overview tool - hierarchical structural summary without reading full content."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import ClassVar

from henchman.tools.base import Tool, ToolKind, ToolResult

_SIZE_FULL_READ = 100
_SIZE_WITH_DOCS = 500
_MAX_IMPORTS_SHOWN = 20
_MAX_HEADINGS_SHOWN = 30
_MAX_DOCSTRING_CHARS = 100
_DEPTH_WITH_METHODS = 2
_MAX_GENERIC_PREVIEW_LINES = 30


def _format_annotation(annotation: ast.expr | None) -> str:
    """Format an AST annotation node as a string.

    Args:
        annotation: AST expression node for a type annotation, or None.

    Returns:
        Formatted annotation string with leading colon, or empty string.
    """
    if annotation is None:
        return ""
    return f": {ast.unparse(annotation)}"


def _format_function_sig(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    include_docs: bool,
    indent: str,
) -> str:
    """Format a function/method definition as a signature line.

    Args:
        node: AST function definition node.
        include_docs: Whether to include the first docstring line.
        indent: Indentation prefix string.

    Returns:
        Formatted signature string, optionally with docstring.
    """
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    args = node.args
    params: list[str] = []

    defaults_offset = len(args.args) - len(args.defaults)
    for i, arg in enumerate(args.args):
        ann = _format_annotation(arg.annotation)
        di = i - defaults_offset
        default = f" = {ast.unparse(args.defaults[di])}" if di >= 0 else ""
        params.append(f"{arg.arg}{ann}{default}")

    if args.vararg:
        params.append(f"*{args.vararg.arg}{_format_annotation(args.vararg.annotation)}")

    for i, kwarg in enumerate(args.kwonlyargs):
        ann = _format_annotation(kwarg.annotation)
        kd = args.kw_defaults[i]
        default = f" = {ast.unparse(kd)}" if kd is not None else ""
        params.append(f"{kwarg.arg}{ann}{default}")

    if args.kwarg:
        params.append(f"**{args.kwarg.arg}{_format_annotation(args.kwarg.annotation)}")

    ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    sig = f"{indent}{prefix} {node.name}({', '.join(params)}){ret}  [L{node.lineno}]"

    if include_docs:
        doc = ast.get_docstring(node)
        if doc:
            first_line = doc.split("\n")[0][:_MAX_DOCSTRING_CHARS]
            sig += f'\n{indent}    """{first_line}"""'

    return sig


def _format_class(node: ast.ClassDef, include_docs: bool, depth: int) -> str:
    """Format a class definition with optional methods.

    Args:
        node: AST class definition node.
        include_docs: Whether to include docstrings.
        depth: If >= 2, include method signatures inside the class.

    Returns:
        Formatted class block as a string.
    """
    bases = ", ".join(ast.unparse(b) for b in node.bases)
    header = f"class {node.name}({bases}):" if bases else f"class {node.name}:"
    header += f"  [L{node.lineno}]"
    lines = [header]

    if include_docs:
        doc = ast.get_docstring(node)
        if doc:
            first_line = doc.split("\n")[0][:_MAX_DOCSTRING_CHARS]
            lines.append(f'    """{first_line}"""')

    if depth >= _DEPTH_WITH_METHODS:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                lines.append(_format_function_sig(child, include_docs, indent="    "))

    return "\n".join(lines)


def _collect_imports(tree: ast.Module) -> list[str]:
    """Collect all import statements from an AST module.

    Args:
        tree: Parsed AST module.

    Returns:
        List of import statement strings.
    """
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = ", ".join(a.name for a in node.names)
            imports.append(f"from {module} import {names}")
    return imports


def _summarize_python(source: str, depth: int, include_docs: bool) -> str:
    """Build a hierarchical structural summary of Python source code.

    Args:
        source: Python source code string.
        depth: Nesting depth for class members.
        include_docs: Whether to include docstrings.

    Returns:
        Structural summary as a formatted string.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return f"[SyntaxError: {e}]"

    parts: list[str] = []

    imports = _collect_imports(tree)
    if imports:
        shown = imports[:_MAX_IMPORTS_SHOWN]
        section = "## Imports\n" + "\n".join(shown)
        if len(imports) > _MAX_IMPORTS_SHOWN:
            section += f"\n... ({len(imports) - _MAX_IMPORTS_SHOWN} more)"
        parts.append(section)

    if include_docs:
        mod_doc = ast.get_docstring(tree)
        if mod_doc:
            parts.append(f"## Module docstring\n{mod_doc[:200]}")

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parts.append(_format_function_sig(node, include_docs, indent=""))
        elif isinstance(node, ast.ClassDef) and depth >= 1:
            parts.append(_format_class(node, include_docs, depth))

    return "\n\n".join(parts) if parts else "[Empty file]"


def _summarize_markdown(lines: list[str]) -> str:
    """Summarize a Markdown file by extracting headings.

    Args:
        lines: Lines of the Markdown file.

    Returns:
        Summary string with heading structure.
    """
    headings = [ln for ln in lines if ln.startswith("#")]
    summary = f"Markdown file: {len(lines)} lines, {len(headings)} headings\n\n"
    summary += "\n".join(headings[:_MAX_HEADINGS_SHOWN])
    if len(headings) > _MAX_HEADINGS_SHOWN:
        summary += f"\n... ({len(headings) - _MAX_HEADINGS_SHOWN} more)"
    return summary


def _summarize_json(content: str) -> str:
    """Summarize a JSON file by showing top-level structure.

    Args:
        content: Raw JSON file content.

    Returns:
        Summary string describing top-level structure.
    """
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            keys = list(data.keys())[:20]
            return f"JSON object with {len(data)} top-level keys: {keys}"
        if isinstance(data, list):
            return f"JSON array with {len(data)} items"
    except json.JSONDecodeError:
        pass
    return "JSON file (could not parse)"


def _summarize_yaml(lines: list[str]) -> str:
    """Summarize a YAML file by showing top-level keys.

    Args:
        lines: Lines of the YAML file.

    Returns:
        Summary string with top-level keys.
    """
    top_keys = [
        ln.split(":")[0].strip()
        for ln in lines
        if ln and not ln.startswith(" ") and not ln.startswith("#") and ":" in ln
    ]
    return f"YAML file: {len(lines)} lines\nTop-level keys: {top_keys[:20]}"


def _summarize_generic(path: Path, content: str) -> str:
    """Summarize a file based on its extension.

    Args:
        path: Path to the file (used for extension detection).
        content: Raw file content.

    Returns:
        Summary string appropriate to the file type.
    """
    suffix = path.suffix.lower()
    lines = content.splitlines()

    if suffix == ".md":
        return _summarize_markdown(lines)
    if suffix == ".json":
        return _summarize_json(content)
    if suffix in {".yaml", ".yml"}:
        return _summarize_yaml(lines)

    if len(lines) <= _MAX_GENERIC_PREVIEW_LINES:
        return content
    preview = "\n".join(lines[:15])
    preview += f"\n... ({len(lines) - _MAX_GENERIC_PREVIEW_LINES} lines omitted) ...\n"
    preview += "\n".join(lines[-15:])
    return preview


def _execute_file_overview(path: str, depth: int) -> ToolResult:
    """Execute the file overview operation.

    Args:
        path: Path to the file to summarize.
        depth: Nesting depth for Python structure (1 = top-level, 2 = with methods).

    Returns:
        ToolResult with the structural summary.
    """
    file_path = Path(path)

    if not file_path.exists():
        return ToolResult(
            content=f"Error: File not found: {path}",
            success=False,
            error=f"File not found: {path}",
        )

    if not file_path.is_file():
        return ToolResult(
            content=f"Error: Not a file: {path}",
            success=False,
            error=f"Not a file: {path}",
        )

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except PermissionError:
        return ToolResult(
            content=f"Error: Permission denied: {path}",
            success=False,
            error=f"Permission denied: {path}",
        )

    line_count = len(content.splitlines())
    header = f"# {file_path.name} ({line_count} lines)\n"

    if file_path.suffix == ".py":
        include_docs = line_count <= _SIZE_WITH_DOCS
        summary = _summarize_python(content, depth, include_docs)
    else:
        summary = _summarize_generic(file_path, content)

    return ToolResult(content=header + summary, success=True)


class FileOverviewTool(Tool):
    """Get a hierarchical structural summary of a file without reading full content.

    For Python files: extracts imports, class hierarchy, function signatures,
    and docstrings (first line). Adapts detail level based on file size.
    For other file types: extracts relevant structural information (headings,
    keys, etc.). Useful for understanding a file's structure before targeted reads.
    """

    _parameters: ClassVar[dict[str, object]] = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to summarize",
            },
            "depth": {
                "type": "integer",
                "description": "Nesting depth: 1 = top-level only, 2 = include class methods",
                "default": 2,
            },
        },
        "required": ["path"],
    }

    @property
    def name(self: FileOverviewTool) -> str:
        """Tool name."""
        return "file_overview"

    @property
    def description(self: FileOverviewTool) -> str:
        """Tool description."""
        return (
            "Get a hierarchical structural summary of a file without reading full content. "
            "For Python files: shows imports, class tree, function signatures, and docstrings. "
            "Adapts detail level to file size. Much faster than read_file for understanding structure."
        )
    @property
    def kind(self: FileOverviewTool) -> ToolKind:
        """Tool kind - READ is auto-approved."""
        return ToolKind.READ

    async def execute(  # type: ignore[override]
        self: FileOverviewTool,
        path: str = "",
        depth: int = 2,
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Get structural overview of a file.

        Args:
            path: Path to the file to summarize.
            depth: Nesting depth (1 = top-level only, 2 = include class methods).
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with the hierarchical structural summary.
        """
        if not path:
            return ToolResult(
                content="Error: path is required",
                success=False,
                error="path is required",
            )
        return _execute_file_overview(path, depth)
