"""Import graph analysis tool implementation."""

import ast
import sys
from pathlib import Path

from henchman.tools.base import Tool, ToolKind, ToolResult

STDLIB_MODULES: frozenset[str] = frozenset(sys.stdlib_module_names)


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
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the Python file to analyze",
                },
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
                    "description": (
                        "Classify imports as stdlib, local, or third-party"
                    ),
                    "default": False,
                },
            },
            "required": ["path"],
        }

    @property
    def kind(self) -> ToolKind:
        """Tool kind - read-only analysis."""
        return ToolKind.READ

    async def execute(  # type: ignore[override]
        self,
        path: str = "",
        scan_dir: str = "",
        detect_cycles: bool = False,
        classify: bool = False,
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Analyze imports of a Python file.

        Args:
            path: Target Python file to analyze.
            scan_dir: Optional directory for reverse-import scan.
            detect_cycles: Detect circular import chains in scan_dir.
            classify: Classify imports as stdlib/local/third-party.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with import analysis.
        """
        # Validate input
        validation_result = self._validate_input(path)
        if validation_result is not None:
            return validation_result

        target = Path(path)

        # Parse file and extract AST
        parse_result = self._parse_file(target, path)
        if isinstance(parse_result, ToolResult):
            return parse_result
        tree, source = parse_result

        # Analyze imports
        imports = self._extract_imports(tree)
        scan_path = Path(scan_dir) if scan_dir else None
        local_modules = self._collect_local_modules(scan_path) if scan_path else set()

        # Build result parts
        parts: list[str] = []

        # Add imports analysis
        self._add_imports_analysis(parts, target.name, imports, classify, local_modules)

        # Add reverse imports analysis if scan_dir provided
        if scan_path and scan_path.exists() and scan_path.is_dir():
            self._add_reverse_imports_analysis(parts, scan_path, target)

        # Add circular import detection if requested
        if detect_cycles and scan_path and scan_path.exists() and scan_path.is_dir():
            self._add_circular_imports_analysis(parts, scan_path)

        return ToolResult(
            content="\n".join(parts),
            success=True,
        )

    def _validate_input(self, path: str) -> ToolResult | None:
        """Validate input parameters.

        Args:
            path: Path to validate.

        Returns:
            ToolResult with error if validation fails, None otherwise.
        """
        if not path:
            return ToolResult(
                content="Error: No path provided",
                success=False,
                error="Empty path",
            )

        target = Path(path)
        if not target.exists():
            return ToolResult(
                content=f"Error: File not found: {path}",
                success=False,
                error=f"File not found: {path}",
            )

        return None

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
        local_modules: set[str],
    ) -> None:
        """Add imports analysis to result parts.

        Args:
            parts: List to append result parts to.
            filename: Name of the file being analyzed.
            imports: List of import statements.
            classify: Whether to classify imports.
            local_modules: Set of local module names.
        """
        parts.append(f"Imports in {filename}:")
        if imports:
            for imp in imports:
                if classify:
                    label = self._classify_import(imp, local_modules)
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
        cycles = self._detect_cycles(scan_path)
        parts.append("\nCircular imports:")
        if cycles:
            for cycle in cycles:
                parts.append(f"  {' -> '.join(cycle)}")
        else:
            parts.append("  (none detected)")

    def _extract_imports(self, tree: ast.AST) -> list[str]:
        """Extract import statements from AST.

        Args:
            tree: Parsed AST.

        Returns:
            List of import strings.
        """
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    if alias.asname:
                        name += f" as {alias.asname}"
                    imports.append(f"import {name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                level = "." * (node.level or 0)
                names = ", ".join(
                    a.name + (f" as {a.asname}" if a.asname else "") for a in node.names
                )
                imports.append(f"from {level}{module} import {names}")
        return imports

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
            if py_file.resolve() == exclude_resolved:
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, OSError, UnicodeDecodeError):
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if module_name in alias.name.split("."):
                            results.append(str(py_file))
                            break
                    else:
                        continue
                    break
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    if module_name in mod.split("."):
                        results.append(str(py_file))
                        break
                    names = [a.name for a in node.names]
                    if module_name in names:
                        results.append(str(py_file))
                        break

        return results

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

    def _classify_import(self, import_str: str, local_modules: set[str]) -> str:
        """Classify an import as stdlib, local, or third-party.

        Args:
            import_str: The import statement string (e.g. 'import os').
            local_modules: Set of local module names from scan_dir.

        Returns:
            One of 'stdlib', 'local', or 'third-party'.
        """
        # Extract the top-level module name
        if import_str.startswith("from .") or import_str.startswith("from .."):
            return "local"

        if import_str.startswith("from "):
            # "from X.Y import Z" -> extract X
            parts = import_str.split()
            module = parts[1].split(".")[0] if len(parts) > 1 else ""
        elif import_str.startswith("import "):
            parts = import_str.split()
            module = parts[1].split(".")[0] if len(parts) > 1 else ""
        else:
            return "third-party"

        if module in STDLIB_MODULES:
            return "stdlib"
        if module in local_modules:
            return "local"
        return "third-party"

    def _build_import_graph(self, scan_dir: Path) -> dict[str, set[str]]:
        """Build a module-level import graph for a directory.

        Args:
            scan_dir: Directory to scan.

        Returns:
            Dict mapping module stems to sets of imported module stems.
        """
        graph: dict[str, set[str]] = {}

        # Collect all local module names
        local_modules = self._collect_local_modules_for_graph(scan_dir)

        # Build import edges for each file
        for py_file in scan_dir.rglob("*.py"):
            mod_name = py_file.stem
            deps = self._extract_dependencies_from_file(py_file, mod_name, local_modules)
            if deps is not None:
                graph[mod_name] = deps

        return graph

    def _collect_local_modules_for_graph(self, scan_dir: Path) -> set[str]:
        """Collect local module names for graph building.

        Args:
            scan_dir: Directory to scan.

        Returns:
            Set of local module names.
        """
        local_modules: set[str] = set()
        for py_file in scan_dir.rglob("*.py"):
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

    def _detect_cycles(self, scan_dir: Path) -> list[list[str]]:
        """Detect circular import chains using DFS.

        Args:
            scan_dir: Directory to scan for Python files.

        Returns:
            List of cycles, each cycle is a list of module names.
        """
        graph = self._build_import_graph(scan_dir)
        visited: set[str] = set()
        rec_stack: set[str] = set()
        path: list[str] = []
        cycles: list[list[str]] = []
        seen_cycles: set[frozenset[str]] = set()

        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in sorted(graph.get(node, set())):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    # Found a cycle
                    idx = path.index(neighbor)
                    cycle = path[idx:] + [neighbor]
                    key = frozenset(cycle[:-1])
                    if key not in seen_cycles:
                        seen_cycles.add(key)
                        cycles.append(cycle)

            path.pop()
            rec_stack.discard(node)

        for node in sorted(graph):
            if node not in visited:
                dfs(node)

        return cycles
