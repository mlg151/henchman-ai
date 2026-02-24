"""Dead code detection tool implementation."""

import ast
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
    }
)


class DeadCodeTool(Tool):
    """Detect unused imports, functions, and classes in Python code.

    Uses AST analysis to find imports that are never referenced,
    functions that are never called, and classes that are never
    instantiated within the analyzed scope.
    """

    @property
    def name(self) -> str:
        """Tool name."""
        return "dead_code"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Detect unused imports, functions, and classes in Python files. "
            "Scans a file or directory and reports dead code candidates."
        )

    @property
    def parameters(self) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to a Python file or directory to analyze",
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
                "whitelist": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Names to exclude from dead code detection",
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
        if not target.exists():
            return ToolResult(
                content=f"Error: Path not found: {path}",
                success=False,
                error=f"Path not found: {path}",
            )

        ignore = DEFAULT_WHITELIST | frozenset(whitelist or [])

        if target.is_file():
            return self._analyze_file(target, check_imports, check_functions, ignore)
        return self._analyze_directory(target, check_imports, check_functions, ignore)

    def _analyze_file(
        self,
        path: Path,
        check_imports: bool,
        check_functions: bool,
        whitelist: frozenset[str],
    ) -> ToolResult:
        """Analyze a single Python file.

        Args:
            path: Path to the file.
            check_imports: Check for unused imports.
            check_functions: Check for unused functions/classes.
            whitelist: Names to ignore.

        Returns:
            ToolResult with findings.
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
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            return ToolResult(
                content=f"Syntax error in {path}: {exc}",
                success=False,
                error=str(exc),
            )

        parts: list[str] = [f"Dead code analysis: {path.name}"]
        found_any = False

        if check_imports:
            unused = self._find_unused_imports(tree, whitelist)
            if unused:
                found_any = True
                parts.append("\nUnused imports:")
                for name, line in unused:
                    parts.append(f"  line {line}: {name}")

        if check_functions:
            unused_defs = self._find_unused_definitions(tree, whitelist)
            if unused_defs:
                found_any = True
                parts.append("\nPossibly unused definitions:")
                for kind, name, line in unused_defs:
                    parts.append(f"  line {line}: {kind} {name}")

        if not found_any:
            parts.append("\n  No dead code detected.")

        return ToolResult(content="\n".join(parts), success=True)

    def _analyze_directory(
        self,
        directory: Path,
        check_imports: bool,
        check_functions: bool,
        whitelist: frozenset[str],
    ) -> ToolResult:
        """Analyze all Python files in a directory.

        Args:
            directory: Directory to scan.
            check_imports: Check for unused imports.
            check_functions: Check for unused functions/classes.
            whitelist: Names to ignore.

        Returns:
            ToolResult with findings.
        """
        all_findings: list[str] = []
        files_scanned = 0

        for py_file in sorted(directory.rglob("*.py")):
            result = self._analyze_file(
                py_file, check_imports, check_functions, whitelist
            )
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
        self,
        tree: ast.Module,
        whitelist: frozenset[str],
    ) -> list[tuple[str, int]]:
        """Find imports that are never used in the file.

        Args:
            tree: Parsed AST module.
            whitelist: Names to ignore.

        Returns:
            List of (import_name, line_number) tuples.
        """
        # Collect imported names
        imported: dict[str, int] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    imported[name] = node.lineno
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    name = alias.asname or alias.name
                    imported[name] = node.lineno

        # Collect all used names (excluding import nodes)
        used_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and not self._is_import_context(node, tree):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                # Check if root of attribute chain is used
                root = node
                while isinstance(root, ast.Attribute):
                    root = root.value  # type: ignore[assignment]
                if isinstance(root, ast.Name):
                    used_names.add(root.id)

        # Find unused
        unused: list[tuple[str, int]] = []
        for name, line in sorted(imported.items(), key=lambda x: x[1]):
            if name not in used_names and name not in whitelist:
                unused.append((name, line))

        return unused

    def _is_import_context(self, node: ast.Name, tree: ast.Module) -> bool:
        """Check if a Name node is part of an import statement.

        Args:
            node: The Name AST node.
            tree: The module AST.

        Returns:
            True if the node is within an import statement.
        """
        for imp_node in ast.walk(tree):
            if (
                isinstance(imp_node, (ast.Import, ast.ImportFrom))
                and hasattr(imp_node, "lineno")
                and imp_node.lineno == node.lineno
            ):
                return True
        return False

    def _find_unused_definitions(
        self,
        tree: ast.Module,
        whitelist: frozenset[str],
    ) -> list[tuple[str, str, int]]:
        """Find functions/classes defined but never referenced.

        Only checks top-level definitions within the same file.

        Args:
            tree: Parsed AST module.
            whitelist: Names to ignore.

        Returns:
            List of (kind, name, line_number) tuples.
        """
        # Collect top-level definitions
        definitions: dict[str, tuple[str, int]] = {}
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                if not node.name.startswith("_"):
                    definitions[node.name] = ("function", node.lineno)
            elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                definitions[node.name] = ("class", node.lineno)

        # Collect all references
        used: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used.add(node.id)
            elif isinstance(node, ast.Attribute):
                used.add(node.attr)

        # Check __all__ for exported names
        all_names = self._get_all_names(tree)
        if all_names is not None:
            used.update(all_names)

        unused: list[tuple[str, str, int]] = []
        for name, (kind, line) in sorted(definitions.items(), key=lambda x: x[1][1]):
            if name not in whitelist and name not in used:
                unused.append((kind, name, line))

        return unused

    def _get_all_names(self, tree: ast.Module) -> set[str] | None:
        """Extract names from __all__ if defined.

        Args:
            tree: Parsed AST module.

        Returns:
            Set of names in __all__, or None if not defined.
        """
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Name)
                        and target.id == "__all__"
                        and isinstance(node.value, ast.List | ast.Tuple)
                    ):
                        names: set[str] = set()
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(
                                elt.value, str
                            ):
                                names.add(elt.value)
                        return names
        return None
