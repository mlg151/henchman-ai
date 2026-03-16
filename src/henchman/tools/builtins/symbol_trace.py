"""Symbol trace tool - full symbol provenance across a codebase."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from henchman.tools.base import Tool, ToolKind, ToolResult

_MAX_FILE_SIZE = 500_000  # bytes - skip very large files
_MAX_RESULTS_PER_CATEGORY = 50


@dataclass
class SymbolDefinition:
    """Location where a symbol is defined.

    Attributes:
        file: Path to the file containing the definition.
        line: Line number of the definition.
        kind: Kind of definition ('function', 'class', 'variable', 'import').
        signature: Optional signature or assignment snippet.
    """

    file: str
    line: int
    kind: str
    signature: str = ""


@dataclass
class SymbolReference:
    """A reference to a symbol in source code.

    Attributes:
        file: Path to the file containing the reference.
        line: Line number of the reference.
        context: The line content for context.
    """

    file: str
    line: int
    context: str


@dataclass
class SymbolTraceParams:
    """Parameters for the symbol trace operation."""

    symbol: str
    path: str = "."
    include_tests: bool = True


@dataclass
class SymbolTraceResult:
    """Complete symbol provenance report.

    Attributes:
        symbol: The symbol name that was traced.
        definitions: Where the symbol is defined.
        imports: Where the symbol is imported.
        references: Where the symbol is called or referenced.
        annotations: Type annotations found for the symbol.
    """

    symbol: str
    definitions: list[SymbolDefinition] = field(default_factory=list)
    imports: list[SymbolReference] = field(default_factory=list)
    references: list[SymbolReference] = field(default_factory=list)
    annotations: list[str] = field(default_factory=list)


def _collect_python_files(root: Path, include_tests: bool) -> list[Path]:
    """Collect Python files to trace, optionally excluding test files.

    Args:
        root: Root directory to search from.
        include_tests: Whether to include test files.

    Returns:
        Sorted list of Python file paths.
    """
    files: list[Path] = []
    for path in sorted(root.rglob("*.py")):
        if not include_tests and ("test_" in path.name or path.name.startswith("test")):
            continue
        if path.stat().st_size > _MAX_FILE_SIZE:
            continue
        files.append(path)
    return files


def _extract_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Extract a single-line signature from a function node."""
    try:
        sig = ast.unparse(node)
        # Handle decorated functions: find the "def" line
        lines = sig.split("\n")
        for line in lines:
            if line.strip().startswith(("def ", "async def ")):
                # Return the function signature line (truncated if needed)
                return line[:120]
        # Fallback: return first line (for backward compatibility)
        return lines[0][:120] if lines else f"def {node.name}(...)"
    except Exception:  # noqa: BLE001
        return f"def {node.name}(...)"


def _find_definitions_in_file(
    path: Path,
    symbol: str,
) -> list[SymbolDefinition]:
    """Find all definitions of a symbol in a Python file via AST.

    Args:
        path: Path to the Python file.
        symbol: Symbol name to find definitions for.

    Returns:
        List of SymbolDefinition objects found in the file.
    """
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
    except (SyntaxError, OSError):
        return []

    definitions: list[SymbolDefinition] = []

    for node in ast.walk(tree):
        # Process function/class definitions
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name != symbol:
                continue

            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            sig = (
                f"class {node.name}(...)"
                if kind == "class"
                else _extract_signature(node)  # type: ignore[arg-type]
            )

            definitions.append(
                SymbolDefinition(
                    file=str(path),
                    line=node.lineno,
                    kind=kind,
                    signature=sig,
                )
            )

        # Process assignments
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id == symbol:
                    definitions.append(
                        SymbolDefinition(
                            file=str(path),
                            line=node.lineno,
                            kind="variable",
                            signature=f"{symbol} = ...",
                        )
                    )

    return definitions


def _find_imports_in_file(path: Path, symbol: str) -> list[SymbolReference]:
    """Find all import statements for a symbol in a Python file.

    Args:
        path: Path to the Python file.
        symbol: Symbol name to find imports for.

    Returns:
        List of SymbolReference objects for import statements.
    """
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
    except (SyntaxError, OSError):
        return []

    refs: list[SymbolReference] = []
    lines = source.splitlines()

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == symbol or (alias.asname and alias.asname == symbol):
                    line_idx = node.lineno - 1
                    ctx = lines[line_idx].strip() if line_idx < len(lines) else ""
                    refs.append(SymbolReference(file=str(path), line=node.lineno, context=ctx))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name
                if symbol in (name, alias.name):
                    line_idx = node.lineno - 1
                    ctx = lines[line_idx].strip() if line_idx < len(lines) else ""

                    refs.append(SymbolReference(file=str(path), line=node.lineno, context=ctx))

    return refs


def _find_references_in_file(path: Path, symbol: str) -> list[SymbolReference]:
    """Find all call/reference sites for a symbol via regex search.

    Args:
        path: Path to the file to search.
        symbol: Symbol name to find references for.

    Returns:
        List of SymbolReference objects for each reference line.
    """
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    pattern = re.compile(rf"\b{re.escape(symbol)}\b")
    refs: list[SymbolReference] = []

    for i, line in enumerate(lines, 1):
        if pattern.search(line):
            refs.append(SymbolReference(file=str(path), line=i, context=line.strip()))

    return refs


def _process_annotation_node(
    ann_node: ast.expr, ann_pattern: re.Pattern[str], annotations: set[str]
) -> None:
    """Helper to process an annotation node and add matching annotations."""
    try:
        ann_str = ast.unparse(ann_node)
        if ann_pattern.search(ann_str):
            annotations.add(ann_str)
    except Exception:  # noqa: BLE001
        pass


def _collect_annotations_from_node(
    node: ast.AST, ann_pattern: re.Pattern[str], annotations: set[str]
) -> None:
    """Extract annotations from a node and its components."""
    if isinstance(node, ast.AnnAssign) and node.annotation:
        _process_annotation_node(node.annotation, ann_pattern, annotations)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if node.returns:
            _process_annotation_node(node.returns, ann_pattern, annotations)

        # Check all argument types for annotations
        # Positional-only arguments (Python 3.8+)
        for arg in node.args.posonlyargs:
            if arg.annotation:
                _process_annotation_node(arg.annotation, ann_pattern, annotations)

        # Normal arguments
        for arg in node.args.args:
            if arg.annotation:
                _process_annotation_node(arg.annotation, ann_pattern, annotations)

        # *args parameter
        if node.args.vararg and node.args.vararg.annotation:
            _process_annotation_node(node.args.vararg.annotation, ann_pattern, annotations)

        # Keyword-only arguments
        for arg in node.args.kwonlyargs:
            if arg.annotation:
                _process_annotation_node(arg.annotation, ann_pattern, annotations)

        # **kwargs parameter
        if node.args.kwarg and node.args.kwarg.annotation:
            _process_annotation_node(node.args.kwarg.annotation, ann_pattern, annotations)


def _collect_annotations(files: list[Path], symbol: str) -> list[str]:
    """Collect type annotation strings containing the symbol.

    Args:
        files: Python files to inspect.
        symbol: Symbol name to look for in annotations.

    Returns:
        List of unique annotation strings mentioning the symbol.
    """
    ann_pattern = re.compile(rf"\b{re.escape(symbol)}\b")
    annotations: set[str] = set()

    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, OSError):
            continue

        for node in ast.walk(tree):
            _collect_annotations_from_node(node, ann_pattern, annotations)

    return sorted(annotations)[:20]


def _append_section(
    lines: list[str],
    header: str,
    items: list[object],
    formatter: callable,
    max_items: int = _MAX_RESULTS_PER_CATEGORY,
) -> None:
    """Append a section to the report if items are present."""
    if not items:
        return

    lines.append(f"## {header}")
    for item in items[:max_items]:
        lines.append(formatter(item))

    if len(items) > max_items:
        lines.append(f"... ({len(items) - max_items} more)")
    lines.append("")


def _build_trace_report(trace: SymbolTraceResult) -> str:
    """Build a Markdown report from a SymbolTraceResult.

    Args:
        trace: Complete symbol trace result.

    Returns:
        Formatted Markdown report string.
    """
    lines: list[str] = [f"# Symbol Trace: `{trace.symbol}`\n"]

    summary = (
        f"**Definitions:** {len(trace.definitions)} | "
        f"**Import sites:** {len(trace.imports)} | "
        f"**Reference sites:** {len(trace.references)}"
    )
    lines.append(summary)
    lines.append("")

    _append_section(
        lines,
        "Definitions",
        trace.definitions,
        lambda d: f"- **{d.kind}** `{d.file}:{d.line}` — `{d.signature}`",
    )

    _append_section(
        lines,
        "Import sites",
        trace.imports,
        lambda ref: f"- `{ref.file}:{ref.line}` — `{ref.context}`",
    )

    _append_section(
        lines,
        "Reference sites",
        trace.references,
        lambda ref: f"- `{ref.file}:{ref.line}` — `{ref.context}`",
    )

    _append_section(
        lines,
        "Type annotations",
        trace.annotations,
        lambda ann: f"- `{ann}`",
        max_items=20,
    )

    if not any([trace.definitions, trace.imports, trace.references]):
        lines.append(f"Symbol `{trace.symbol}` not found in the searched files.")

    return "\n".join(lines).strip()


def _execute_symbol_trace(params: SymbolTraceParams) -> ToolResult:
    """Execute the symbol trace operation.

    Args:
        params: Symbol trace parameters.

    Returns:
        ToolResult with a Markdown provenance report.
    """
    root = Path(params.path)
    if not root.exists():
        return ToolResult(
            content=f"Error: Path not found: {params.path}",
            success=False,
            error=f"Path not found: {params.path}",
        )

    files = _collect_python_files(
        root if root.is_dir() else root.parent, params.include_tests
    )
    if root.is_file() and root.suffix == ".py":
        files = [root]

    trace = SymbolTraceResult(symbol=params.symbol)

    for file_path in files:
        defs = _find_definitions_in_file(file_path, params.symbol)
        trace.definitions.extend(defs)

        imps = _find_imports_in_file(file_path, params.symbol)
        trace.imports.extend(imps)

    # References: only search in files that aren't just definition files
    defined_files = {d.file for d in trace.definitions}
    for file_path in files:
        refs = _find_references_in_file(file_path, params.symbol)
        # Exclude lines that are the definition itself
        def_lines = {d.line for d in trace.definitions if d.file == str(file_path)}
        filtered = [
            r
            for r in refs
            if r.line not in def_lines or str(file_path) not in defined_files
        ]
        trace.references.extend(filtered)

    trace.annotations = _collect_annotations(files, params.symbol)

    return ToolResult(content=_build_trace_report(trace), success=True)


class SymbolTraceTool(Tool):
    """Trace a symbol's full provenance across a codebase.

    Given a symbol name (function, class, variable, or import alias),
    finds all definition sites, import sites, call/reference sites, and
    type annotations. Replaces the manual combination of python_ast +
    grep + import_graph + kg_query into a single comprehensive call.
    """

    _parameters: ClassVar[dict[str, object]] = {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Symbol name to trace (function, class, variable, or alias)",
            },
            "path": {
                "type": "string",
                "description": "Root directory or file to search (defaults to current directory)",
                "default": ".",
            },
            "include_tests": {
                "type": "boolean",
                "description": "Whether to include test files in the trace",
                "default": True,
            },
        },
        "required": ["symbol"],
    }

    @property
    def name(self: SymbolTraceTool) -> str:
        """Tool name."""
        return "symbol_trace"

    @property
    def description(self: SymbolTraceTool) -> str:
        """Tool description."""
        return (
            "Trace a symbol's full provenance across a codebase: definition site(s), "
            "all import statements, all call/reference sites, and type annotations. "
            "Replaces the manual combination of python_ast + grep + import_graph."
        )
    @property
    def kind(self: SymbolTraceTool) -> ToolKind:
        """Tool kind - READ is auto-approved."""
        return ToolKind.READ

    async def execute(  # type: ignore[override]
        self: SymbolTraceTool,
        symbol: str = "",
        path: str = ".",
        include_tests: bool = True,
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Trace symbol provenance across the codebase.

        Args:
            symbol: Symbol name to trace.
            path: Root directory or file to search.
            include_tests: Whether to include test files.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with a Markdown provenance report.
        """
        if not symbol:
            return ToolResult(
                content="Error: symbol is required",
                success=False,
                error="symbol is required",
            )

        params = SymbolTraceParams(
            symbol=symbol,
            path=path,
            include_tests=include_tests,
        )
        return _execute_symbol_trace(params)
