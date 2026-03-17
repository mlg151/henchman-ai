"""Import graph analysis tool implementation."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.utils import (
    create_path_parameter_schema,
    validate_directory_path,
    validate_file_path,
)

STDLIB_MODULES: frozenset[str] = frozenset(sys.stdlib_module_names)


def _extract_top_level_module(import_str: str) -> str:
    """Extract the top-level module name from an import statement."""
    if import_str.startswith("from "):
        parts = import_str.split()
        return parts[1].split(".")[0] if len(parts) > 1 else ""
    if import_str.startswith("import "):
        parts = import_str.split()
        return parts[1].split(".")[0] if len(parts) > 1 else ""
    return ""


def _classify_import(import_str: str, local_modules: set[str]) -> str:
    """Classify an import as stdlib, local, or third-party."""
    if import_str.startswith(("from .", "from ..")):
        return "local"
    module = _extract_top_level_module(import_str)
    if not module:
        return "third-party"
    if module in STDLIB_MODULES:
        return "stdlib"
    if module in local_modules:
        return "local"
    return "third-party"


def _extract_imports_from_ast(tree: ast.AST) -> list[str]:
    """Extract import statements from AST."""
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(_extract_imports_from_import_node(node))
        elif isinstance(node, ast.ImportFrom):
            imports.append(_extract_import_from_import_from_node(node))
    return imports


def _extract_imports_from_import_node(node: ast.Import) -> list[str]:
    """Extract import strings from an Import node."""
    imports: list[str] = []
    for alias in node.names:
        name = alias.name
        if alias.asname:
            name += f" as {alias.asname}"
        imports.append(f"import {name}")
    return imports


def _extract_import_from_import_from_node(node: ast.ImportFrom) -> str:
    """Extract import string from an ImportFrom node."""
    module = node.module or ""
    level = "." * (node.level or 0)
    names = ", ".join(a.name + (f" as {a.asname}" if a.asname else "") for a in node.names)
    return f"from {level}{module} import {names}"


def _collect_python_module_stems(directory: Path) -> set[str]:
    """Collect Python module stem names from a directory tree.

    Returns empty set if directory does not exist.
    """
    if not directory.is_dir():
        return set()
    return {py_file.stem for py_file in directory.rglob("*.py")}


def _add_local_dep_if_known(
    module_name: str,
    current_module: str,
    local_modules: set[str],
    deps: set[str],
) -> None:
    """Add a module to deps if it is local and not the current module."""
    if module_name in local_modules and module_name != current_module:
        deps.add(module_name)


def _extract_import_node_deps(
    node: ast.Import,
    mod_name: str,
    local_modules: set[str],
    deps: set[str],
) -> None:
    """Extract local dependencies from a plain import node."""
    for alias in node.names:
        top = alias.name.split(".")[0]
        _add_local_dep_if_known(top, mod_name, local_modules, deps)


def _extract_import_from_node_deps(
    node: ast.ImportFrom,
    mod_name: str,
    local_modules: set[str],
    deps: set[str],
) -> None:
    """Extract local dependencies from a from-import node."""
    mod = node.module or ""
    top = mod.split(".")[0] if mod else ""
    _add_local_dep_if_known(top, mod_name, local_modules, deps)
    for alias in node.names:
        _add_local_dep_if_known(alias.name, mod_name, local_modules, deps)


def _extract_ast_node_deps(
    node: ast.AST,
    mod_name: str,
    local_modules: set[str],
    deps: set[str],
) -> None:
    """Dispatch dependency extraction to the appropriate AST node handler."""
    if isinstance(node, ast.Import):
        _extract_import_node_deps(node, mod_name, local_modules, deps)
    elif isinstance(node, ast.ImportFrom):
        _extract_import_from_node_deps(node, mod_name, local_modules, deps)


def _extract_file_dependencies(
    py_file: Path,
    mod_name: str,
    local_modules: set[str],
) -> set[str] | None:
    """Parse a Python file and return its local module dependencies."""
    try:
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_file))
    except (SyntaxError, OSError, UnicodeDecodeError):
        return None
    deps: set[str] = set()
    for node in ast.walk(tree):
        _extract_ast_node_deps(node, mod_name, local_modules, deps)
    return deps


def _import_node_contains_module(node: ast.Import, module_name: str) -> bool:
    """Return True if an Import node references the given module."""
    return any(module_name in alias.name.split(".") for alias in node.names)


def _import_from_node_contains_module(node: ast.ImportFrom, module_name: str) -> bool:
    """Return True if an ImportFrom node references the given module."""
    mod = node.module or ""
    if module_name in mod.split("."):
        return True
    return module_name in [a.name for a in node.names]


def _tree_imports_module(tree: ast.AST, module_name: str) -> bool:
    """Return True if any node in the AST imports the given module."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and _import_node_contains_module(node, module_name):
            return True
        if isinstance(node, ast.ImportFrom) and _import_from_node_contains_module(
            node, module_name,
        ):
            return True
    return False


def _should_skip_file(py_file: Path, exclude_resolved: Path) -> bool:
    """Return True if a file should be excluded from reverse-import search."""
    return py_file.resolve() == exclude_resolved


def _file_imports_module(py_file: Path, module_name: str) -> bool:
    """Return True if a source file imports the given module."""
    try:
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_file))
    except (SyntaxError, OSError, UnicodeDecodeError):
        return False
    return _tree_imports_module(tree, module_name)


def _find_reverse_imports(scan_dir: Path, module_name: str, exclude: Path) -> list[str]:
    """Find all files in a directory that import the given module."""
    exclude_resolved = exclude.resolve()
    return [
        str(py_file)
        for py_file in scan_dir.rglob("*.py")
        if not _should_skip_file(py_file, exclude_resolved)
        and _file_imports_module(py_file, module_name)
    ]


def _parse_import_analysis_request(params: dict[str, object]) -> ImportAnalysisRequest:
    """Build an ImportAnalysisRequest from raw tool parameters."""
    return ImportAnalysisRequest(
        path=str(params.get("path", "")),
        scan_dir=str(params.get("scan_dir", "")),
        detect_cycles=bool(params.get("detect_cycles", False)),
        classify=bool(params.get("classify", False)),
    )


def _add_imports_section(
    parts: list[str],
    filename: str,
    imports: list[str],
    *,
    classify: bool,
    analyzer: ImportAnalyzer,
) -> None:
    """Append an imports summary block to the result parts list."""
    parts.append(f"Imports in {filename}:")
    if imports:
        for imp in imports:
            if classify:
                label = analyzer.classify_import(imp)
                parts.append(f"  {imp}  [{label}]")
            else:
                parts.append(f"  {imp}")
    else:
        parts.append("  (none)")


def _add_reverse_imports_section(
    parts: list[str],
    scan_path: Path,
    target: Path,
) -> None:
    """Append a reverse-imports summary block to the result parts list."""
    module_name = target.stem
    reverse = _find_reverse_imports(scan_path, module_name, target)
    parts.append(f"\nFiles importing {module_name}:")
    if reverse:
        parts.extend(f"  {rev}" for rev in sorted(reverse))
    else:
        parts.append("  (none)")


def _add_circular_imports_section(parts: list[str], scan_path: Path) -> None:
    """Append a circular-imports summary block to the result parts list."""
    builder = ImportGraphBuilder(scan_path)
    cycles = builder.detect_cycles()
    parts.append("\nCircular imports:")
    if cycles:
        parts.extend(f"  {' -> '.join(cycle)}" for cycle in cycles)
    else:
        parts.append("  (none detected)")


class ImportAnalyzer:
    """Analyzes imports in Python files."""

    def __init__(self: ImportAnalyzer, local_modules: set[str]) -> None:
        """Initialize analyzer with local module context."""
        self.local_modules: set[str] = local_modules

    def extract_imports(self: ImportAnalyzer, tree: ast.AST) -> list[str]:
        """Extract import statements from AST.

        Args:
            tree: The AST (Abstract Syntax Tree) to analyze.

        Returns:
            List of import strings found in the AST.
        """
        return _extract_imports_from_ast(tree)

    def classify_import(self: ImportAnalyzer, import_str: str) -> str:
        """Classify an import as stdlib, local, or third-party.

        Args:
            import_str: The import statement string to classify.

        Returns:
            Classification string: 'stdlib', 'local', or 'third-party'.
        """
        return _classify_import(import_str, self.local_modules)


class ImportGraphBuilder:
    """Builds and analyzes import graphs."""

    def __init__(self: ImportGraphBuilder, scan_dir: Path) -> None:
        """Initialize graph builder."""
        self.scan_dir = scan_dir

    def build_graph(self: ImportGraphBuilder) -> dict[str, set[str]]:
        """Build a module-level import graph for a directory.

        Returns:
            Dictionary mapping module names to sets of their dependencies.
        """
        graph: dict[str, set[str]] = {}
        local_modules = _collect_python_module_stems(self.scan_dir)
        for py_file in self.scan_dir.rglob("*.py"):
            mod_name = py_file.stem
            deps = _extract_file_dependencies(py_file, mod_name, local_modules)
            if deps is not None:
                graph[mod_name] = deps
        return graph

    def detect_cycles(self: ImportGraphBuilder) -> list[list[str]]:
        """Detect circular import chains using DFS.

        Returns:
            List of cycles, each cycle is a list of module names.
        """
        graph = self.build_graph()
        return _CycleFinder(graph).find_cycles()

    def _extract_dependencies_from_file(
        self: ImportGraphBuilder,
        py_file: Path,
        mod_name: str,
        local_modules: set[str],
    ) -> set[str] | None:
        """Thin wrapper around ``_extract_file_dependencies`` for test compatibility.

        Returns:
            Set of dependency module names, or None if the file has no dependencies.
        """
        return _extract_file_dependencies(py_file, mod_name, local_modules)


class _CycleFinder:
    """Finds cycles in a directed graph using DFS."""

    def __init__(self: _CycleFinder, graph: dict[str, set[str]]) -> None:
        """Initialize cycle finder with graph.

        Args:
            graph: Directed graph as adjacency list.
        """
        self.graph = graph
        self.visited: set[str] = set()
        self.rec_stack: set[str] = set()
        self.path: list[str] = []
        self.cycles: list[list[str]] = []
        self.seen_cycles: set[frozenset[str]] = set()

    def find_cycles(self: _CycleFinder) -> list[list[str]]:
        """Find all cycles in the graph.

        Returns:
            List of cycles, each cycle is a list of node names.
        """
        for node in sorted(self.graph):
            if node not in self.visited:
                self._dfs(node)
        return self.cycles

    def _dfs(self: _CycleFinder, node: str) -> None:
        """Depth-first search to find cycles.

        Args:
            node: Current node being visited.
        """
        self.visited.add(node)
        self.rec_stack.add(node)
        self.path.append(node)

        for neighbor in sorted(self.graph.get(node, set())):
            if neighbor not in self.visited:
                self._dfs(neighbor)
            elif neighbor in self.rec_stack:
                self._record_cycle(neighbor)

        self.path.pop()
        self.rec_stack.discard(node)

    def _record_cycle(self: _CycleFinder, cycle_start: str) -> None:
        """Record a found cycle.

        Args:
            cycle_start: Node where the cycle starts/ends.
        """
        idx = self.path.index(cycle_start)
        cycle = [*self.path[idx:], cycle_start]
        key = frozenset(cycle[:-1])

        if key not in self.seen_cycles:
            self.seen_cycles.add(key)
            self.cycles.append(cycle)


@dataclass
class ImportAnalysisRequest:
    """Request object for import analysis to replace primitive parameters."""

    path: str
    scan_dir: str = ""
    detect_cycles: bool = False
    classify: bool = False

    def validate(self: ImportAnalysisRequest) -> ToolResult | None:
        """Validate parameters.

        Returns:
            ToolResult with error if validation fails, None if valid.
        """
        # Validate main file path
        path_error = validate_file_path(self.path)
        if path_error:
            return path_error

        # Validate scan directory if provided
        if self.scan_dir:
            dir_error = validate_directory_path(self.scan_dir)
            if dir_error:
                return dir_error

        return None

    def extract_params(self: ImportAnalysisRequest) -> tuple[Path, Path | None, bool, bool]:
        """Extract parameters as typed values.

        Returns:
            Tuple of (target_path, scan_path, should_classify, should_detect_cycles).
        """
        target_path = Path(self.path)
        scan_path = Path(self.scan_dir) if self.scan_dir else None
        should_classify = self.classify
        should_detect_cycles = self.detect_cycles
        return target_path, scan_path, should_classify, should_detect_cycles


class ImportGraphTool(Tool):
    """Analyze Python import dependencies."""

    @property
    def name(self: ImportGraphTool) -> str:
        """Tool name."""
        return "import_graph"

    @property
    def description(self: ImportGraphTool) -> str:
        """Tool description."""
        return (
            "Analyze import dependencies of a Python file. Shows what a "
            "file imports and optionally which files import it. "
            "Can detect circular imports and classify imports as stdlib, "
            "local, or third-party."
        )

    @property
    def parameters(self: ImportGraphTool) -> dict[str, object]:
        """JSON Schema for parameters."""
        return create_path_parameter_schema(
            additional_params={
                "scan_dir": {
                    "type": "string",
                    "description": (
                        "Directory to scan for reverse imports (files that import the target)"
                    ),
                },
                "detect_cycles": {
                    "type": "boolean",
                    "description": (
                        "Scan directory for circular import chains (requires scan_dir)"
                    ),
                    "default": False,
                },
                "classify": {
                    "type": "boolean",
                    "description": "Classify imports as stdlib, local, or third-party",
                    "default": False,
                },
            },
        )

    @property
    def kind(self: ImportGraphTool) -> ToolKind:
        """Tool kind - read-only analysis."""
        return ToolKind.READ

    async def execute(
        self: ImportGraphTool,
        **params: object,
    ) -> ToolResult:
        """Analyze imports of a Python file.

        Args:
            params: Tool parameters passed as keyword arguments.
                Expected parameters:
                    path (str): Path to the Python file to analyze.
                    scan_dir (str, optional): Directory to scan for reverse imports
                        (files that import the target).
                    detect_cycles (bool, optional): Scan directory for circular import
                        chains (requires scan_dir). Defaults to False.
                    classify (bool, optional): Classify imports as stdlib, local, or
                        third-party. Defaults to False.

        Returns:
            ToolResult with import analysis results.
        """
        request = _parse_import_analysis_request(params)
        validation_result = request.validate()
        if validation_result is not None:
            return validation_result
        return await self._execute_with_request(request)

    async def _execute_with_request(
        self: ImportGraphTool,
        request: ImportAnalysisRequest,
    ) -> ToolResult:
        """Execute import analysis with a validated request."""
        target_path, scan_path, should_classify, should_detect_cycles = request.extract_params()

        parse_result = self._parse_file(target_path, str(target_path))
        if isinstance(parse_result, ToolResult):
            return parse_result
        tree, _ = parse_result

        local_modules = _collect_python_module_stems(scan_path) if scan_path else set()
        analyzer = ImportAnalyzer(local_modules)
        imports = analyzer.extract_imports(tree)

        return self._build_analysis_result(
            target_path=target_path,
            scan_path=scan_path,
            imports=imports,
            analyzer=analyzer,
            should_classify=should_classify,
            should_detect_cycles=should_detect_cycles,
        )

    def _build_analysis_result(
        self: ImportGraphTool,
        target_path: Path,
        scan_path: Path | None,
        imports: list[str],
        analyzer: ImportAnalyzer,
        *,
        should_classify: bool,
        should_detect_cycles: bool,
    ) -> ToolResult:
        """Assemble the final ToolResult from all analysis sections."""
        parts: list[str] = []

        _add_imports_section(
            parts,
            target_path.name,
            imports,
            classify=should_classify,
            analyzer=analyzer,
        )

        if scan_path:
            _add_reverse_imports_section(parts, scan_path, target_path)

        if should_detect_cycles and scan_path:
            _add_circular_imports_section(parts, scan_path)

        return ToolResult(
            content="\n".join(parts),
            success=True,
        )

    def _parse_file(
        self: ImportGraphTool,
        target: Path,
        path: str,
    ) -> tuple[ast.AST, str] | ToolResult:
        """Parse a Python source file and return its AST and source text."""
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

        return tree, source

    # ── Test-compatibility wrappers ──────────────────────────────────────────

    def _file_imports_module(self: ImportGraphTool, py_file: Path, module_name: str) -> bool:
        """Thin wrapper around module-level ``_file_imports_module``.

        Args:
            py_file: Path to the Python file.
            module_name: Name of the module to check for.

        Returns:
            True if the file imports the module.
        """
        if py_file is None:  # pragma: no cover
            return False
        return _file_imports_module(py_file, module_name)

    def _import_from_node_contains_module(
        self: ImportGraphTool,
        node: ast.ImportFrom,
        module_name: str,
    ) -> bool:
        """Thin wrapper around module-level ``_import_from_node_contains_module``."""
        return _import_from_node_contains_module(node, module_name)

    def _collect_local_modules(self: ImportGraphTool, scan_dir: Path) -> set[str]:
        """Thin wrapper around ``_collect_python_module_stems``."""
        return _collect_python_module_stems(scan_dir)
