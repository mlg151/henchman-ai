"""Dead code detection tool implementation."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.utils import create_path_parameter_schema

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
    ast_walk = ast.walk
    Import = ast.Import  # noqa: N806
    ImportFrom = ast.ImportFrom  # noqa: N806
    for import_node in ast_walk(tree):
        if (
            isinstance(import_node, (Import, ImportFrom))
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
    iter_child_nodes = ast.iter_child_nodes
    FunctionDef = ast.FunctionDef  # noqa: N806
    AsyncFunctionDef = ast.AsyncFunctionDef  # noqa: N806
    ClassDef = ast.ClassDef  # noqa: N806
    for node in iter_child_nodes(tree):
        node_name = node.name if hasattr(node, "name") else ""
        if isinstance(node, (FunctionDef, AsyncFunctionDef)):
            if not node_name.startswith(_PRIVATE_PREFIX):
                definitions[node_name] = ("function", node.lineno)
        elif isinstance(node, ClassDef) and not node_name.startswith(_PRIVATE_PREFIX):
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
    Assign = ast.Assign  # noqa: N806
    Name = ast.Name  # noqa: N806
    List = ast.List  # noqa: N806
    Tuple = ast.Tuple  # noqa: N806
    if not isinstance(node, Assign):
        return None

    for target in node.targets:
        if (
            isinstance(target, Name)
            and target.id == _ALL_NAME
            and isinstance(node.value, (List, Tuple))
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


def collect_used_names(tree: ast.Module) -> set[str]:
    """Collect all used names from AST (excluding import context).

    Args:
        tree: Parsed AST module.

    Returns:
        Set of used names.
    """
    used_names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            name = _process_name_node(node, tree)
            if name:
                used_names.add(name)
        elif isinstance(node, ast.Attribute):
            root_name = _process_attribute_node(node)
            if root_name:
                used_names.add(root_name)

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


def _identify_unused_items(
    items: dict[str, int],
    used_names: set[str],
    whitelist: frozenset[str],
) -> list[tuple[str, int]]:
    """Identify unused items from collected data.

    Args:
        items: Dictionary mapping item name to line number.
        used_names: Set of used names.
        whitelist: Names to ignore.

    Returns:
        List of (item_name, line_number) tuples.
    """
    unused: list[tuple[str, int]] = []
    for name, line in sorted(items.items(), key=lambda x: x[1]):
        if name not in used_names and name not in whitelist:
            unused.append((name, line))
    return unused


def _identify_unused_definitions(
    definitions: dict[str, tuple[str, int]],
    used_names: set[str],
    whitelist: frozenset[str],
) -> list[tuple[str, str, int]]:
    """Identify unused definitions from collected data.

    Args:
        definitions: Dictionary mapping name to (kind, line_number).
        used_names: Set of used names.
        whitelist: Names to ignore.

    Returns:
        List of (kind, name, line_number) tuples.
    """
    unused: list[tuple[str, str, int]] = []
    for name, (kind, line) in sorted(definitions.items(), key=lambda x: x[1][1]):
        if name not in whitelist and name not in used_names:
            unused.append((kind, name, line))
    return unused


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
        return create_path_parameter_schema(
            additional_params={
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
                "whitelist": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Names to exclude from dead code detection",
                },
            },
        )

    @property
    def kind(self: DeadCodeTool) -> ToolKind:
        """Tool kind - read-only analysis."""
        return ToolKind.READ

    async def execute(  # type: ignore[override]
        self: DeadCodeTool,
        path: str = "",
        *,
        check_imports: bool = True,
        check_functions: bool = True,
        whitelist: list[str] | None = None,
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Detect dead code in Python files.

        Args:
            path: Path to file or directory.
            check_imports: Whether to check unused imports.
            check_functions: Whether to check unused functions/classes.
            whitelist: Additional names to ignore.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with dead code report.
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
                content=f"Error: Path not found: {path}",
                success=False,
                error=f"Path not found: {path}",
            )

        params = AnalysisParameters(
            check_imports=check_imports,
            check_functions=check_functions,
            whitelist=DEFAULT_WHITELIST | frozenset(whitelist or []),
        )

        if target.is_file():  # noqa: ASYNC240
            return self._analyze_file(target, params)
        return self._analyze_directory(target, params)

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
        parts: list[str] = [f"Dead code analysis: {context.filename}"]
        findings: list[str] = []

        if context.params.check_imports:
            unused_imports = self._find_unused_imports(context)
            if unused_imports:
                findings.extend(self._format_import_findings(unused_imports))

        if context.params.check_functions:
            unused_defs = self._find_unused_definitions(context)
            if unused_defs:
                findings.extend(self._format_definition_findings(unused_defs))

        if findings:
            parts.extend(findings)
        else:
            parts.append("\n  No dead code detected.")

        return "\n".join(parts)

    def _format_findings(
        self: DeadCodeTool, header: str, items: list[str],
    ) -> list[str]:
        """Format a list of finding lines under a section header.

        Args:
            header: Section heading line (e.g. ``"\\nUnused imports:"``).
            items: Pre-formatted item strings to list beneath the header.

        Returns:
            List beginning with *header* followed by each item.
        """
        return [header, *items]

    def _format_import_findings(self: DeadCodeTool, unused_imports: list[tuple[str, int]]) -> list[str]:  # noqa: E501
        """Format unused import findings for output.

        Args:
            unused_imports: List of (name, line) tuples.

        Returns:
            Formatted findings lines.
        """
        return self._format_findings(
            "\nUnused imports:",
            [f"  line {line}: {name}" for name, line in unused_imports],
        )

    def _format_definition_findings(self: DeadCodeTool, unused_defs: list[tuple[str, str, int]]) -> list[str]:  # noqa: E501
        """Format unused definition findings for output.

        Args:
            unused_defs: List of (kind, name, line) tuples.

        Returns:
            Formatted findings lines.
        """
        return self._format_findings(
            "\nPossibly unused definitions:",
            [f"  line {line}: {kind} {name}" for kind, name, line in unused_defs],
        )

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
            result = self._analyze_file(py_file, params)
            if result.success and "No dead code" not in result.content:
                all_findings.append(result.content)
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

    def _find_unused_imports(
        self: DeadCodeTool,
        context: AnalysisContext,
    ) -> list[tuple[str, int]]:
        """Find imports that are never used in the file.

        Args:
            context: Analysis context.

        Returns:
            List of (import_name, line_number) tuples.
        """
        imported = collect_imported_names(context.tree)
        used_names = collect_used_names(context.tree)
        return _identify_unused_items(imported, used_names, context.params.whitelist)

    def _find_unused_definitions(
        self: DeadCodeTool,
        context: AnalysisContext,
    ) -> list[tuple[str, str, int]]:
        """Find functions/classes defined but never referenced.

        Only checks top-level definitions within the same file.

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
