"""Import graph analysis tool implementation."""

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
    """Extract the top-level module name from an import statement.

    Args:
        import_str: The import statement string (e.g. 'import os').

    Returns:
        Top-level module name or empty string.
    """
    if import_str.startswith("from "):
        # "from X.Y import Z" -> extract X
        parts = import_str.split()
        return parts[1].split(".")[0] if len(parts) > 1 else ""
    elif import_str.startswith("import "):
        parts = import_str.split()
        return parts[1].split(".")[0] if len(parts) > 1 else ""
    return ""


def _classify_import(import_str: str, local_modules: set[str]) -> str:
    """Classify an import as stdlib, local, or third-party.

    Args:
        import_str: The import statement string (e.g. 'import os').
        local_modules: Set of local module names.

    Returns:
        One of 'stdlib', 'local', or 'third-party'.
    """
    # Extract the top-level module name
    if import_str.startswith("from .") or import_str.startswith("from .."):
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
    """Extract import statements from AST.

    Args:
        tree: Parsed AST.

    Returns:
        List of import strings.
    """
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(_extract_imports_from_import_node(node))
        elif isinstance(node, ast.ImportFrom):
            imports.append(_extract_import_from_import_from_node(node))
    return imports


def _extract_imports_from_import_node(node: ast.Import) -> list[str]:
    """Extract import strings from an Import node.

    Args:
        node: Import AST node.

    Returns:
        List of import strings.
    """
    imports: list[str] = []
    for alias in node.names:
        name = alias.name
        if alias.asname:
            name += f" as {alias.asname}"
        imports.append(f"import {name}")
    return imports


def _extract_import_from_import_from_node(node: ast.ImportFrom) -> str:
    """Extract import string from an ImportFrom node.

    Args:
        node: ImportFrom AST node.

    Returns:
        Import string.
    """
    module = node.module or ""
    level = "." * (node.level or 0)
    names = ", ".join(a.name + (f" as {a.asname}" if a.asname else "") for a in node.names)
    return f"from {level}{module} import {names}"


class ImportAnalyzer:
    """Analyzes imports in Python files."""

    def __init__(self, local_modules: set[str]) -> None:
        """Initialize analyzer with local module context.

        Args:
            local_modules: Set of local module names.
        """
        self.local_modules: set[str] = local_modules

    def extract_imports(self, tree: ast.AST) -> list[str]:
        """Extract import statements from AST.

        Args:
            tree: Parsed AST.

        Returns:
            List of import strings.
        """
        return _extract_imports_from_ast(tree)

    def classify_import(self, import_str: str) -> str:
        """Classify an import as stdlib, local, or third-party.

        Args:
            import_str: The import statement string (e.g. 'import os').

        Returns:
            One of 'stdlib', 'local', or 'third-party'.
        """
        return _classify_import(import_str, self.local_modules)


class ImportGraphBuilder:
    """Builds and analyzes import graphs."""

    def __init__(self, scan_dir: Path) -> None:
        """Initialize graph builder.

        Args:
            scan_dir: Directory to scan for imports.
        """
        self.scan_dir = scan_dir

    def build_graph(self) -> dict[str, set[str]]:
        """Build a module-level import graph for a directory.

        Returns:
            Dict mapping module stems to sets of imported module stems.
        """
        graph: dict[str, set[str]] = {}

        # Collect all local module names
        local_modules = self._collect_local_modules()

        # Build import edges for each file
        for py_file in self.scan_dir.rglob("*.py"):
            mod_name = py_file.stem
            deps = self._extract_dependencies_from_file(py_file, mod_name, local_modules)
            if deps is not None:
                graph[mod_name] = deps

        return graph

    def _collect_local_modules(self) -> set[str]:
        """Collect local module names for graph building.

        Returns:
            Set of local module names.
        """
        local_modules: set[str] = set()
        for py_file in self.scan_dir.rglob("*.py"):
            local_modules.add(py_file.stem)
        return local_modules

    def _extract_dependencies_from_file(
        self,
        py_file: Path,
        mod_name: str,
        local_modules: set[str],
    ) -> set[str] | None:
        """Extract dependencies from a Python file.

        Args:
            py_file: Path to Python file.
            mod_name: Name of the module (file stem).
            local_modules: Set of local module names.

        Returns:
            Set of dependencies or None if file cannot be parsed.
        """
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, OSError, UnicodeDecodeError):
            return None

        deps: set[str] = set()
        for node in ast.walk(tree):
            self._extract_dependencies_from_node(node, mod_name, local_modules, deps)

        return deps

    def _extract_dependencies_from_node(
        self,
        node: ast.AST,
        mod_name: str,
        local_modules: set[str],
        deps: set[str],
    ) -> None:
        """Extract dependencies from an AST node.

        Args:
            node: AST node to analyze.
            mod_name: Name of the current module.
            local_modules: Set of local module names.
            deps: Set to add dependencies to.
        """
        if isinstance(node, ast.Import):
            self._extract_dependencies_from_import(node, mod_name, local_modules, deps)
        elif isinstance(node, ast.ImportFrom):
            self._extract_dependencies_from_import_from(node, mod_name, local_modules, deps)

    def _extract_dependencies_from_import(
        self,
        node: ast.Import,
        mod_name: str,
        local_modules: set[str],
        deps: set[str],
    ) -> None:
        """Extract dependencies from an Import node.

        Args:
            node: Import AST node.
            mod_name: Name of the current module.
            local_modules: Set of local module names.
            deps: Set to add dependencies to.
        """
        for alias in node.names:
            top = alias.name.split(".")[0]
            if top in local_modules and top != mod_name:
                deps.add(top)

    def _extract_dependencies_from_import_from(
        self,
        node: ast.ImportFrom,
        mod_name: str,
        local_modules: set[str],
        deps: set[str],
    ) -> None:
        """Extract dependencies from an ImportFrom node.

        Args:
            node: ImportFrom AST node.
            mod_name: Name of the current module.
            local_modules: Set of local module names.
            deps: Set to add dependencies to.
        """
        mod = node.module or ""
        top = mod.split(".")[0] if mod else ""
        if top in local_modules and top != mod_name:
            deps.add(top)

        for alias in node.names:
            if alias.name in local_modules and alias.name != mod_name:
                deps.add(alias.name)

    def detect_cycles(self) -> list[list[str]]:
        """Detect circular import chains using DFS.

        Returns:
            List of cycles, each cycle is a list of module names.
        """
        graph = self.build_graph()
        return self._find_cycles_in_graph(graph)

    def _find_cycles_in_graph(self, graph: dict[str, set[str]]) -> list[list[str]]:
        """Find cycles in a directed graph using DFS.

        Args:
            graph: Directed graph as adjacency list.

        Returns:
            List of cycles, each cycle is a list of node names.
        """
        cycle_finder = _CycleFinder(graph)
        return cycle_finder.find_cycles()


class _CycleFinder:
    """Finds cycles in a directed graph using DFS."""

    def __init__(self, graph: dict[str, set[str]]) -> None:
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

    def find_cycles(self) -> list[list[str]]:
        """Find all cycles in the graph.

        Returns:
            List of cycles, each cycle is a list of node names.
        """
        for node in sorted(self.graph):
            if node not in self.visited:
                self._dfs(node)
        return self.cycles

    def _dfs(self, node: str) -> None:
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

    def _record_cycle(self, cycle_start: str) -> None:
        """Record a found cycle.

        Args:
            cycle_start: Node where the cycle starts/ends.
        """
        idx = self.path.index(cycle_start)
        cycle = self.path[idx:] + [cycle_start]
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

    def validate(self) -> ToolResult | None:
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

    @classmethod
    def from_primitives(
        cls,
        path: str = "",
        scan_dir: str = "",
        detect_cycles: bool = False,
        classify: bool = False,
    ) -> "ImportAnalysisRequest":
        """Create request from primitive parameters.

        Args:
            path: Target Python file to analyze.
            scan_dir: Optional directory for reverse-import scan.
            detect_cycles: Detect circular import chains in scan_dir.
            classify: Classify imports as stdlib/local/third-party.

        Returns:
            ImportAnalysisRequest instance.
        """
        return cls(
            path=path,
            scan_dir=scan_dir,
            detect_cycles=detect_cycles,
            classify=classify,
        )


class ImportGraphTool(Tool):
    """Analyze Python import dependencies.

    Parses a Python file to extract its imports, and optionally scans
    a directory for reverse imports (files that import the target).
    Supports circular import detection and import classification.
    """

    @property
    def name(self) -> str:
        """Tool name."""
        return "import_graph"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Analyze import dependencies of a Python file. Shows what a "
            "file imports and optionally which files import it. "
            "Can detect circular imports and classify imports as stdlib, "
            "local, or third-party."
        )

    @property
    def parameters(self) -> dict[str, object]:
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
            }
        )

    @property
    def kind(self) -> ToolKind:
        """Tool kind - read-only analysis."""
        return ToolKind.READ

    async def execute(
        self,
        **params: object,
    ) -> ToolResult:
        """Analyze imports of a Python file.

        Args:
            **params: Tool parameters including path, scan_dir, detect_cycles, classify.

        Returns:
            ToolResult with import analysis.
        """
        # Extract parameters with defaults
        path = str(params.get("path", ""))
        scan_dir = str(params.get("scan_dir", ""))
        detect_cycles = bool(params.get("detect_cycles", False))
        classify = bool(params.get("classify", False))

        # Create and validate request using factory method
        request = ImportAnalysisRequest.from_primitives(
            path=path,
            scan_dir=scan_dir,
            detect_cycles=detect_cycles,
            classify=classify,
        )

        validation_result = request.validate()
        if validation_result is not None:
            return validation_result

        return await self._execute_with_request(request)

    async def _execute_with_request(self, request: ImportAnalysisRequest) -> ToolResult:
        """Execute import analysis with validated request.

        Args:
            request: Validated import analysis request.

        Returns:
            ToolResult with import analysis.
        """
        # Extract parameters from request
        target_path, scan_path, should_classify, should_detect_cycles = (
            self._extract_request_params(request)
        )

        # Parse file and extract AST
        parse_result = self._parse_file(target_path, str(target_path))
        if isinstance(parse_result, ToolResult):
            return parse_result
        tree, _ = parse_result

        # Analyze imports
        local_modules = self._collect_local_modules(scan_path) if scan_path else set()
        analyzer = ImportAnalyzer(local_modules)
        imports = analyzer.extract_imports(tree)

        # Build and return analysis result
        return self._build_analysis_result(
            target_path=target_path,
            scan_path=scan_path,
            imports=imports,
            analyzer=analyzer,
            should_classify=should_classify,
            should_detect_cycles=should_detect_cycles,
        )

    @staticmethod
    def _extract_request_params(
        request: ImportAnalysisRequest,
    ) -> tuple[Path, Path | None, bool, bool]:
        """Extract parameters from ImportAnalysisRequest.

        Args:
            request: The request object.

        Returns:
            Tuple of (target_path, scan_path, should_classify, should_detect_cycles).
        """
        target_path = Path(request.path)
        scan_path = Path(request.scan_dir) if request.scan_dir else None
        should_classify = request.classify
        should_detect_cycles = request.detect_cycles
        return target_path, scan_path, should_classify, should_detect_cycles

    def _build_analysis_result(
        self,
        target_path: Path,
        scan_path: Path | None,
        imports: list[str],
        analyzer: ImportAnalyzer,
        should_classify: bool,
        should_detect_cycles: bool,
    ) -> ToolResult:
        """Build the analysis result from extracted data.

        Args:
            target_path: Path to the target file.
            scan_path: Optional directory to scan for reverse imports.
            imports: List of import statements.
            analyzer: Import analyzer instance.
            should_classify: Whether to classify imports.
            should_detect_cycles: Whether to detect circular imports.

        Returns:
            ToolResult with import analysis.
        """
        parts: list[str] = []

        # Add imports analysis
        self._add_imports_analysis(parts, target_path.name, imports, should_classify, analyzer)

        # Add reverse imports analysis if scan_dir provided
        if scan_path:
            self._add_reverse_imports_analysis(parts, scan_path, target_path)

        # Add circular import detection if requested
        if should_detect_cycles and scan_path:
            self._add_circular_imports_analysis(parts, scan_path)

        return ToolResult(
            content="\n".join(parts),
            success=True,
        )

    def _parse_file(self, target: Path, path: str) -> tuple[ast.AST, str] | ToolResult:
        """Parse a Python file and return AST and source.

        Args:
            target: Path object for the file.
            path: Original path string for error messages.

        Returns:
            Tuple of (AST, source) or ToolResult with error.
        """
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

    def _add_imports_analysis(
        self,
        parts: list[str],
        filename: str,
        imports: list[str],
        classify: bool,
        analyzer: ImportAnalyzer,
    ) -> None:
        """Add imports analysis to result parts.

        Args:
            parts: List to append result parts to.
            filename: Name of the file being analyzed.
            imports: List of import statements.
            classify: Whether to classify imports.
            analyzer: Import analyzer instance.
        """
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

    def _add_reverse_imports_analysis(
        self,
        parts: list[str],
        scan_path: Path,
        target: Path,
    ) -> None:
        """Add reverse imports analysis to result parts.

        Args:
            parts: List to append result parts to.
            scan_path: Directory to scan for reverse imports.
            target: Target file to find imports of.
        """
        module_name = target.stem
        reverse = self._find_reverse_imports(scan_path, module_name, target)
        parts.append(f"\nFiles importing {module_name}:")
        if reverse:
            for rev in sorted(reverse):
                parts.append(f"  {rev}")
        else:
            parts.append("  (none)")

    def _add_circular_imports_analysis(
        self,
        parts: list[str],
        scan_path: Path,
    ) -> None:
        """Add circular imports analysis to result parts.

        Args:
            parts: List to append result parts to.
            scan_path: Directory to scan for circular imports.
        """
        builder = ImportGraphBuilder(scan_path)
        cycles = builder.detect_cycles()
        parts.append("\nCircular imports:")
        if cycles:
            for cycle in cycles:
                parts.append(f"  {' -> '.join(cycle)}")
        else:
            parts.append("  (none detected)")

    def _find_reverse_imports(
        self,
        scan_dir: Path,
        module_name: str,
        exclude: Path,
    ) -> list[str]:
        """Find files that import the given module.

        Args:
            scan_dir: Directory to scan.
            module_name: Module name to search for.
            exclude: File to exclude (the target itself).

        Returns:
            List of file paths that import the module.
        """
        results: list[str] = []
        exclude_resolved = exclude.resolve()

        for py_file in scan_dir.rglob("*.py"):
            if self._should_skip_file(py_file, exclude_resolved):
                continue

            if self._file_imports_module(py_file, module_name):
                results.append(str(py_file))

        return results

    def _should_skip_file(self, py_file: Path, exclude_resolved: Path) -> bool:
        """Check if a file should be skipped in reverse import search.

        Args:
            py_file: File to check.
            exclude_resolved: Resolved path of file to exclude.

        Returns:
            True if file should be skipped, False otherwise.
        """
        return py_file.resolve() == exclude_resolved

    def _file_imports_module(self, py_file: Path, module_name: str) -> bool:
        """Check if a file imports a specific module.

        Args:
            py_file: File to check.
            module_name: Module name to search for.

        Returns:
            True if file imports the module, False otherwise.
        """
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, OSError, UnicodeDecodeError):
            return False

        return self._tree_imports_module(tree, module_name)

    def _tree_imports_module(self, tree: ast.AST, module_name: str) -> bool:
        """Check if an AST tree imports a specific module.

        Args:
            tree: AST to check.
            module_name: Module name to search for.

        Returns:
            True if tree imports the module, False otherwise.
        """
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Import)
                and self._import_node_contains_module(node, module_name)
                or isinstance(node, ast.ImportFrom)
                and self._import_from_node_contains_module(node, module_name)
            ):
                return True
        return False

    def _import_node_contains_module(self, node: ast.Import, module_name: str) -> bool:
        """Check if an Import node contains a specific module.

        Args:
            node: Import AST node.
            module_name: Module name to search for.

        Returns:
            True if import contains the module, False otherwise.
        """
        return any(module_name in alias.name.split(".") for alias in node.names)

    def _import_from_node_contains_module(self, node: ast.ImportFrom, module_name: str) -> bool:
        """Check if an ImportFrom node contains a specific module.

        Args:
            node: ImportFrom AST node.
            module_name: Module name to search for.

        Returns:
            True if import contains the module, False otherwise.
        """
        mod = node.module or ""
        if module_name in mod.split("."):
            return True

        names = [a.name for a in node.names]
        return module_name in names

    def _collect_local_modules(self, scan_dir: Path) -> set[str]:
        """Collect module names from a local directory.

        Args:
            scan_dir: Directory to scan for Python files.

        Returns:
            Set of module stem names found locally.
        """
        modules: set[str] = set()
        if scan_dir.exists() and scan_dir.is_dir():
            for py_file in scan_dir.rglob("*.py"):
                modules.add(py_file.stem)
        return modules
