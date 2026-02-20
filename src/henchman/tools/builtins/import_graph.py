"""Import graph analysis tool implementation."""

import ast
from pathlib import Path

from henchman.tools.base import Tool, ToolKind, ToolResult


class ImportGraphTool(Tool):
    """Analyze Python import dependencies.

    Parses a Python file to extract its imports, and optionally scans
    a directory for reverse imports (files that import the target).
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
            "file imports and optionally which files import it."
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
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Analyze imports of a Python file.

        Args:
            path: Target Python file to analyze.
            scan_dir: Optional directory for reverse-import scan.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with import analysis.
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

        # Extract imports
        imports = self._extract_imports(tree)

        parts: list[str] = [f"Imports in {target.name}:"]
        if imports:
            for imp in imports:
                parts.append(f"  {imp}")
        else:
            parts.append("  (none)")

        # Reverse imports if scan_dir provided
        if scan_dir:
            scan_path = Path(scan_dir)
            if scan_path.exists() and scan_path.is_dir():
                module_name = target.stem
                reverse = self._find_reverse_imports(scan_path, module_name, target)
                parts.append(f"\nFiles importing {module_name}:")
                if reverse:
                    for rev in sorted(reverse):
                        parts.append(f"  {rev}")
                else:
                    parts.append("  (none)")

        return ToolResult(
            content="\n".join(parts),
            success=True,
        )

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
