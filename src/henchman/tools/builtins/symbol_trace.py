"""Symbol trace tool - full symbol provenance across a codebase."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

from henchman.tools.base import Tool, ToolKind, ToolResult

_MAX_FILE_SIZE = 500_000  # bytes - skip very large files
_MAX_RESULTS_PER_CATEGORY = 50
_MAX_SIGNATURE_LENGTH = 120  # chars - truncate long function signatures
_MAX_ANNOTATIONS = 20  # max unique annotation strings to report
_SectionItem = TypeVar("_SectionItem")


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


def _collect_python_files(root: Path, *, include_tests: bool) -> list[Path]:
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
                return line[:_MAX_SIGNATURE_LENGTH]
        # Fallback: return first line (for backward compatibility)
        return lines[0][:_MAX_SIGNATURE_LENGTH] if lines else f"def {node.name}(...)"
    except Exception:
        return f"def {node.name}(...)"


def _definition_from_callable(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    path: Path,
) -> SymbolDefinition:
    """Build a SymbolDefinition from a function or class AST node."""
    kind = "class" if isinstance(node, ast.ClassDef) else "function"
    sig = (
        f"class {node.name}(...)"
        if kind == "class"
        else _extract_signature(node)  # type: ignore[arg-type]
    )
    return SymbolDefinition(file=str(path), line=node.lineno, kind=kind, signature=sig)


def _definitions_from_assignment(
    node: ast.Assign | ast.AnnAssign,
    symbol: str,
    path: Path,
) -> list[SymbolDefinition]:
    """Build SymbolDefinitions from an assignment node if the symbol matches."""
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    return [
        SymbolDefinition(
            file=str(path),
            line=node.lineno,
            kind="variable",
            signature=f"{symbol} = ...",
        )
        for target in targets
        if isinstance(target, ast.Name) and target.id == symbol
    ]


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
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == symbol:
                definitions.append(_definition_from_callable(node, path))
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            definitions.extend(_definitions_from_assignment(node, symbol, path))
    return definitions


def _refs_from_import_from(
    node: ast.ImportFrom,
    symbol: str,
    path: Path,
    source_lines: list[str],
) -> list[SymbolReference]:
    """Build SymbolReferences from a 'from X import Y' statement."""
    ctx = source_lines[node.lineno - 1].strip() if node.lineno - 1 < len(source_lines) else ""
    return [
        SymbolReference(file=str(path), line=node.lineno, context=ctx)
        for alias in node.names
        if alias.name == symbol or alias.asname == symbol
    ]


def _refs_from_import(
    node: ast.Import,
    symbol: str,
    path: Path,
    source_lines: list[str],
) -> list[SymbolReference]:
    """Build SymbolReferences from a plain 'import X' statement."""
    ctx = source_lines[node.lineno - 1].strip() if node.lineno - 1 < len(source_lines) else ""
    return [
        SymbolReference(file=str(path), line=node.lineno, context=ctx)
        for alias in node.names
        if symbol in (alias.asname or alias.name, alias.name)
    ]


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

    source_lines = source.splitlines()
    refs: list[SymbolReference] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            refs.extend(_refs_from_import_from(node, symbol, path, source_lines))
        elif isinstance(node, ast.Import):
            refs.extend(_refs_from_import(node, symbol, path, source_lines))
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
    return [
        SymbolReference(file=str(path), line=i, context=line.strip())
        for i, line in enumerate(lines, 1)
        if pattern.search(line)
    ]


def _process_annotation_node(
    ann_node: ast.expr,
    ann_pattern: re.Pattern[str],
    annotations: set[str],
) -> None:
    """Process an annotation node and add matching annotations."""
    try:
        ann_str = ast.unparse(ann_node)
        if ann_pattern.search(ann_str):
            annotations.add(ann_str)
    except Exception:
        pass


def _iter_function_annotations(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.expr]:
    """Return all annotation nodes from a function definition."""
    annotations: list[ast.expr] = []
    if node.returns:
        annotations.append(node.returns)
    args = node.args
    all_args = args.posonlyargs + args.args + args.kwonlyargs
    if args.vararg:
        all_args = [*all_args, args.vararg]
    if args.kwarg:
        all_args = [*all_args, args.kwarg]
    annotations.extend(arg.annotation for arg in all_args if arg.annotation)
    return annotations


def _collect_annotations_from_node(
    node: ast.AST,
    ann_pattern: re.Pattern[str],
    annotations: set[str],
) -> None:
    """Extract annotations from a node and its components."""
    if isinstance(node, ast.AnnAssign) and node.annotation:
        _process_annotation_node(node.annotation, ann_pattern, annotations)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for ann in _iter_function_annotations(node):
            _process_annotation_node(ann, ann_pattern, annotations)


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

    return sorted(annotations)[:_MAX_ANNOTATIONS]


def _append_section(
    lines: list[str],
    header: str,
    items: Sequence[_SectionItem],
    formatter: Callable[[_SectionItem], str],
    max_items: int = _MAX_RESULTS_PER_CATEGORY,
) -> None:
    """Append a section to the report if items are present."""
    if not items:
        return

    lines.append(f"## {header}")
    lines.extend(formatter(item) for item in items[:max_items])

    if len(items) > max_items:
        lines.append(f"... ({len(items) - max_items} more)")
    lines.append("")


def _format_definition(d: SymbolDefinition) -> str:
    """Format a definition entry for the Markdown report."""
    return f"- **{d.kind}** `{d.file}:{d.line}` — `{d.signature}`"


def _format_reference(ref: SymbolReference) -> str:
    """Format a reference entry for the Markdown report."""
    return f"- `{ref.file}:{ref.line}` — `{ref.context}`"


def _append_all_sections(lines: list[str], trace: SymbolTraceResult) -> None:
    """Append all four provenance sections to the report lines."""
    _append_section(lines, "Definitions", trace.definitions, _format_definition)
    _append_section(lines, "Import sites", trace.imports, _format_reference)
    _append_section(lines, "Reference sites", trace.references, _format_reference)
    _append_section(
        lines,
        "Type annotations",
        trace.annotations,
        lambda ann: f"- `{ann}`",
        max_items=_MAX_ANNOTATIONS,
    )


def _build_trace_report(trace: SymbolTraceResult) -> str:
    """Build a Markdown report from a SymbolTraceResult.

    Args:
        trace: Complete symbol trace result.

    Returns:
        Formatted Markdown report string.
    """
    lines: list[str] = [
        f"# Symbol Trace: `{trace.symbol}`\n",
        (
            f"**Definitions:** {len(trace.definitions)} | "
            f"**Import sites:** {len(trace.imports)} | "
            f"**Reference sites:** {len(trace.references)}"
        ),
        "",
    ]
    _append_all_sections(lines, trace)
    if not any([trace.definitions, trace.imports, trace.references]):
        lines.append(f"Symbol `{trace.symbol}` not found in the searched files.")
    return "\n".join(lines).strip()


def _gather_definitions_and_imports(
    files: list[Path],
    symbol: str,
) -> tuple[list[SymbolDefinition], list[SymbolReference]]:
    """Collect all definitions and import references for the symbol."""
    definitions: list[SymbolDefinition] = []
    imports: list[SymbolReference] = []
    for file_path in files:
        definitions.extend(_find_definitions_in_file(file_path, symbol))
        imports.extend(_find_imports_in_file(file_path, symbol))
    return definitions, imports


def _gather_references(
    files: list[Path],
    trace: SymbolTraceResult,
) -> list[SymbolReference]:
    """Collect reference sites, excluding the definition lines themselves."""
    defined_files = {d.file for d in trace.definitions}
    refs: list[SymbolReference] = []
    for file_path in files:
        raw = _find_references_in_file(file_path, trace.symbol)
        def_lines = {d.line for d in trace.definitions if d.file == str(file_path)}
        refs.extend(
            r for r in raw
            if r.line not in def_lines or str(file_path) not in defined_files
        )
    return refs


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
        root if root.is_dir() else root.parent,
        include_tests=params.include_tests,
    )
    if root.is_file() and root.suffix == ".py":
        files = [root]

    trace = SymbolTraceResult(symbol=params.symbol)
    trace.definitions, trace.imports = _gather_definitions_and_imports(files, params.symbol)
    trace.references = _gather_references(files, trace)
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
        path: str | Path = ".",
        *,
        include_tests: bool = True,
        **kwargs: object,
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
            path=str(path),
            include_tests=include_tests,
        )
        return _execute_symbol_trace(params)
