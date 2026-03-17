"""Dead code detection tool implementation."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from henchman.tools.base import Tool, ToolKind, ToolResult

# Well-known names that are intentionally "unused"
DEFAULT_WHITELIST: frozenset[str] = frozenset(
    {
        "__all__",
        "__init__",
        "__main__",
        "__version__",
        "__author__",
        "__doc__",
        "__file__",
        "__name__",
        "__package__",
        "setup",
        "conftest",
    },
)

# Constants for AST node types
_ALL_NAME = "__all__"
_PRIVATE_PREFIX = "_"


@dataclass(frozen=True)
class AnalysisParameters:
    """Parameters for dead code analysis."""

    check_imports: bool = True
    check_functions: bool = True
    whitelist: frozenset[str] = frozenset()


@dataclass(frozen=True)
class AnalysisContext:
    """Context for analyzing a single file."""

    tree: ast.Module
    filename: str
    params: AnalysisParameters


def is_import_context(name_node: ast.Name, tree: ast.Module) -> bool:
    """Check if a Name node is part of an import statement.

    Args:
        name_node: The Name AST node.
        tree: The module AST.

    Returns:
        True if the node is within an import statement.
    """
    for import_node in ast.walk(tree):
        if (
            isinstance(import_node, (ast.Import, ast.ImportFrom))
            and hasattr(import_node, "lineno")
            and import_node.lineno == name_node.lineno
        ):
            return True
    return False


def collect_top_level_definitions(tree: ast.Module) -> dict[str, tuple[str, int]]:
    """Collect top-level function and class definitions.

    Args:
        tree: Parsed AST module.

    Returns:
        Dictionary mapping name to (kind, line_number).
    """
    definitions: dict[str, tuple[str, int]] = {}
    for node in ast.iter_child_nodes(tree):
        node_name = node.name if hasattr(node, "name") else ""  # type: ignore[union-attr]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node_name.startswith(_PRIVATE_PREFIX):
                definitions[node_name] = ("function", node.lineno)
        elif isinstance(node, ast.ClassDef) and not node_name.startswith(_PRIVATE_PREFIX):
            definitions[node_name] = ("class", node.lineno)
    return definitions


def find_all_assignment(node: ast.AST) -> ast.expr | None:
    """Find __all__ assignment value if node is an assignment to __all__.

    Args:
        node: AST node to check.

    Returns:
        The value expression if node assigns to __all__ with list/tuple,
        None otherwise.
    """
    if not isinstance(node, ast.Assign):
        return None

    for target in node.targets:
        if (
            isinstance(target, ast.Name)
            and target.id == _ALL_NAME
            and isinstance(node.value, (ast.List, ast.Tuple))
        ):
            return node.value
    return None


def collect_imported_names(tree: ast.Module) -> dict[str, int]:
    """Collect all imported names from AST.

    Args:
        tree: Parsed AST module.

    Returns:
        Dictionary mapping imported name to line number.
    """
    imported: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            _collect_import_names(node, imported)
        elif isinstance(node, ast.ImportFrom):
            _collect_import_from_names(node, imported)
    return imported


def _collect_import_names(node: ast.Import, imported: dict[str, int]) -> None:
    """Collect names from ast.Import node.

    Args:
        node: Import AST node.
        imported: Dictionary to update with imported names.
    """
    for alias in node.names:
        name = alias.asname or alias.name.split(".")[0]
        imported[name] = node.lineno


def _collect_import_from_names(node: ast.ImportFrom, imported: dict[str, int]) -> None:
    """Collect names from ast.ImportFrom node.

    Args:
        node: ImportFrom AST node.
        imported: Dictionary to update with imported names.
    """
    for alias in node.names:
        if alias.name == "*":
            continue
        name = alias.asname or alias.name
        imported[name] = node.lineno


def _process_name_node(node: ast.Name, tree: ast.Module) -> str | None:
    """Process a Name AST node to extract used name if not in import context.

    Args:
        node: Name AST node.
        tree: Module AST for context checking.

    Returns:
        Name if it should be added to used names, None otherwise.
    """
    if not is_import_context(node, tree):
        return node.id
    return None


def _process_attribute_node(node: ast.Attribute) -> str | None:
    """Process an Attribute AST node to extract root name.

    Args:
        node: Attribute AST node.

    Returns:
        Root name if extractable, None otherwise.
    """
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        current = current.value
    return current.id if isinstance(current, ast.Name) else None


def _extract_used_name(node: ast.AST, tree: ast.Module) -> str | None:
    """Extract a referenced name from a Name or Attribute node.

    Args:
        node: AST node to inspect.
        tree: Module AST used for import-context checking.

    Returns:
        The referenced name string, or None if not applicable.
    """
    if isinstance(node, ast.Name):
        return _process_name_node(node, tree)
    if isinstance(node, ast.Attribute):
        return _process_attribute_node(node)
    return None


def collect_used_names(tree: ast.Module) -> set[str]:
    """Collect all used names from AST (excluding import context).

    Args:
        tree: Parsed AST module.

    Returns:
        Set of used names.
    """
    used_names: set[str] = set()
    for node in ast.walk(tree):
        name = _extract_used_name(node, tree)
        if name:
            used_names.add(name)
    return used_names


def collect_all_references(tree: ast.Module) -> set[str]:
    """Collect all name references from AST.

    Args:
        tree: Parsed AST module.

    Returns:
        Set of referenced names.
    """
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            used.add(node.attr)
    return used


def get_all_names(tree: ast.Module) -> set[str] | None:
    """Extract names from __all__ if defined.

    Args:
        tree: Parsed AST module.

    Returns:
        Set of names in __all__, or None if not defined.
    """
    for node in ast.iter_child_nodes(tree):
        all_assignment = find_all_assignment(node)
        if all_assignment is not None:
            return _extract_names_from_all(all_assignment)
    return None


def _extract_names_from_all(value: ast.expr) -> set[str] | None:
    """Extract string names from __all__ list/tuple.

    Args:
        value: AST expression (list or tuple).

    Returns:
        Set of string names, or None if extraction fails.
    """
    if not isinstance(value, (ast.List, ast.Tuple)):
        return None

    names: set[str] = set()
    for element in value.elts:
        if isinstance(element, ast.Constant) and isinstance(element.value, str):
            names.add(element.value)
    return names or None


def _is_unused_name(
    name: str,
    used_names: set[str],
    whitelist: frozenset[str],
) -> bool:
    """Return True if name is a dead code candidate.

    Args:
        name: Symbol name to check.
        used_names: Names referenced in the file.
        whitelist: Names to always consider as used.

    Returns:
        True when the name is not in used_names or whitelist.
    """
    return name not in used_names and name not in whitelist


def _identify_unused_items(
    items: dict[str, int],
    used_names: set[str],
    whitelist: frozenset[str],
) -> list[tuple[str, int]]:
    """Identify unused items from imported names dict.

    Args:
        items: Dictionary mapping item name to line number.
        used_names: Set of used names.
        whitelist: Names to ignore.

    Returns:
        List of (item_name, line_number) tuples sorted by line.
    """
    unused: list[tuple[str, int]] = []
    for name, line in items.items():
        if _is_unused_name(name, used_names, whitelist):
            unused.append((name, line))
    return sorted(unused, key=lambda pair: pair[1])


def _identify_unused_definitions(
    definitions: dict[str, tuple[str, int]],
    used_names: set[str],
    whitelist: frozenset[str],
) -> list[tuple[str, str, int]]:
    """Identify unused top-level definitions.

    Args:
        definitions: Dictionary mapping name to (kind, line_number).
        used_names: Set of used names.
        whitelist: Names to ignore.

    Returns:
        List of (kind, name, line_number) tuples sorted by line.
    """
    return sorted(
        [
            (kind, name, line)
            for name, (kind, line) in definitions.items()
            if _is_unused_name(name, used_names, whitelist)
        ],
        key=lambda x: x[2],
    )


def _find_unused_imports(context: AnalysisContext) -> list[tuple[str, int]]:
    """Find imports that are never used in the file.

    Args:
        context: Analysis context.

    Returns:
        List of (import_name, line_number) tuples.
    """
    imported = collect_imported_names(context.tree)
    used_names = collect_used_names(context.tree)
    return _identify_unused_items(imported, used_names, context.params.whitelist)


def _find_unused_definitions(context: AnalysisContext) -> list[tuple[str, str, int]]:
    """Find functions/classes defined but never referenced in the same file.

    Args:
        context: Analysis context.

    Returns:
        List of (kind, name, line_number) tuples.
    """
    definitions = collect_top_level_definitions(context.tree)
    used_names = collect_all_references(context.tree)
    all_names = get_all_names(context.tree)
    if all_names is not None:
        used_names.update(all_names)
    return _identify_unused_definitions(definitions, used_names, context.params.whitelist)


def _get_file_finding(file_result: ToolResult) -> str | None:
    """Return the finding content if the result contains dead code findings.

    Args:
        file_result: ToolResult from analyzing a single file.

    Returns:
        Content string if there are findings, None otherwise.
    """
    if file_result.success and "No dead code" not in file_result.content:
        return file_result.content
    return None


def _extract_dead_code_params(
    params: dict[str, object],
) -> tuple[str, bool, bool, list[str]]:
    """Extract and validate execution parameters for dead code analysis.

    Args:
        params: Raw keyword parameters dict.

    Returns:
        Tuple of (path, check_imports, check_functions, whitelist).
    """
    path = str(params.get("path", ""))
    check_imports = bool(params.get("check_imports", True))
    check_functions = bool(params.get("check_functions", True))
    whitelist_raw = params.get("whitelist")
    whitelist: list[str] = list(whitelist_raw) if isinstance(whitelist_raw, list) else []
    return path, check_imports, check_functions, whitelist


def _resolve_analysis_target(path: str) -> Path | ToolResult:
    """Resolve and validate the path for dead code analysis."""
    target = Path(path)
    if not target.exists():
        return ToolResult(
            content=f"Error: Path not found: {path}",
            success=False,
            error=f"Path not found: {path}",
        )
    return target


class DeadCodeTool(Tool):
    """Detect unused imports, functions, and classes in Python code.

    Uses AST analysis to find imports that are never referenced,
    functions that are never called, and classes that are never
    instantiated within the analyzed scope.
    """

    @property
    def name(self: DeadCodeTool) -> str:
        """Tool name."""
        return "dead_code"

    @property
    def description(self: DeadCodeTool) -> str:
        """Tool description."""
        return (
            "Detect unused imports, functions, and classes in Python files. "
            "Scans a file or directory and reports dead code candidates."
        )

    @property
    def parameters(self: DeadCodeTool) -> dict[str, object]:
        """JSON Schema for parameters."""
        whitelist_schema: dict[str, object] = {
            "type": "array",
            "items": {"type": "string"},
            "description": "Names to exclude from dead code detection",
        }
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file or directory",
                },
                "check_imports": {
                    "type": "boolean",
                    "description": "Check for unused imports (default true)",
                    "default": True,
                },
                "check_functions": {
                    "type": "boolean",
                    "description": "Check for unused functions/classes (default true)",
                    "default": True,
                },
                "whitelist": whitelist_schema,
            },
            "required": ["path"],
        }

    @property
    def kind(self: DeadCodeTool) -> ToolKind:
        """Tool kind - read-only analysis."""
        return ToolKind.READ

    async def execute(  # type: ignore[override]
        self: DeadCodeTool,
        **params: object,
    ) -> ToolResult:
        """Detect dead code in Python files.

        Args:
            params: Tool parameters passed as keyword arguments.
                Expected keys:
                    path (str): Path to file or directory.
                    check_imports (bool): Whether to check unused imports.
                    check_functions (bool): Whether to check unused functions/classes.
                    whitelist (list[str]): Additional names to ignore.

        Returns:
            ToolResult with dead code report.
        """
        path, check_imports, check_functions, whitelist = _extract_dead_code_params(params)
        if not path:
            return ToolResult(
                content="Error: No path provided",
                success=False,
                error="Empty path",
            )

        target = _resolve_analysis_target(path)
        if isinstance(target, ToolResult):
            return target

        analysis_params = AnalysisParameters(
            check_imports=check_imports,
            check_functions=check_functions,
            whitelist=DEFAULT_WHITELIST | frozenset(whitelist),
        )

        if target.is_file():
            return self._analyze_file(target, analysis_params)
        return self._analyze_directory(target, analysis_params)

    def _analyze_file(
        self: DeadCodeTool,
        path: Path,
        params: AnalysisParameters,
    ) -> ToolResult:
        """Analyze a single Python file.

        Args:
            path: Path to the file.
            params: Analysis parameters.

        Returns:
            ToolResult with findings.
        """
        tree = self._parse_file(path)
        if isinstance(tree, ToolResult):
            return tree

        analysis_result = self._perform_analysis(
            context=AnalysisContext(tree=tree, filename=path.name, params=params),
        )
        return ToolResult(content=analysis_result, success=True)

    def _parse_file(self: DeadCodeTool, path: Path) -> ast.Module | ToolResult:
        """Parse a Python file into AST.

        Args:
            path: Path to the file.

        Returns:
            AST module or ToolResult with error.
        """
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return ToolResult(
                content=f"Error reading file: {exc}",
                success=False,
                error=str(exc),
            )

        try:
            return ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            return ToolResult(
                content=f"Syntax error in {path}: {exc}",
                success=False,
                error=str(exc),
            )

    def _perform_analysis(self: DeadCodeTool, context: AnalysisContext) -> str:
        """Perform dead code analysis on parsed AST.

        Args:
            context: Analysis context containing tree, filename, and parameters.

        Returns:
            Formatted analysis results.
        """
        filename = context.filename
        analysis_params = context.params
        parts: list[str] = [f"Dead code analysis: {filename}"]
        findings: list[str] = []

        if analysis_params.check_imports:
            unused_imports = _find_unused_imports(context)
            if unused_imports:
                findings += self._format_findings(
                    "\nUnused imports:",
                    [f"  line {line}: {name}" for name, line in unused_imports],
                )

        if analysis_params.check_functions:
            unused_defs = _find_unused_definitions(context)
            if unused_defs:
                findings += self._format_findings(
                    "\nPossibly unused definitions:",
                    [f"  line {line}: {kind} {name}" for kind, name, line in unused_defs],
                )

        parts.extend(findings or ["\n  No dead code detected."])
        return "\n".join(parts)

    def _format_findings(
        self: DeadCodeTool,
        header: str,
        items: list[str],
    ) -> list[str]:
        """Format a list of finding lines under a section header.

        Args:
            header: Section heading line (e.g. ``"\\nUnused imports:"``).
            items: Pre-formatted item strings to list beneath the header.

        Returns:
            List beginning with *header* followed by each item.
        """
        return [header, *items]



    def _analyze_directory(
        self: DeadCodeTool,
        directory: Path,
        params: AnalysisParameters,
    ) -> ToolResult:
        """Analyze all Python files in a directory.

        Args:
            directory: Directory to scan.
            params: Analysis parameters.

        Returns:
            ToolResult with findings.
        """
        all_findings: list[str] = []
        files_scanned = 0

        for py_file in sorted(directory.rglob("*.py")):
            finding = _get_file_finding(self._analyze_file(py_file, params))
            if finding:
                all_findings.append(finding)
            files_scanned += 1

        if not all_findings:
            return ToolResult(
                content=f"No dead code detected in {files_scanned} files.",
                success=True,
            )

        header = f"Dead code scan: {files_scanned} files, {len(all_findings)} with findings\n"
        return ToolResult(
            content=header + "\n\n".join(all_findings),
            success=True,
        )

