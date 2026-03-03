"""Dead code detection tool implementation."""

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

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

# Constants for AST node types
_ALL_NAME = "__all__"
_PRIVATE_PREFIX = "_"


@dataclass(frozen=True)
class AnalysisParameters:
    """Parameters for dead code analysis."""
    check_imports: bool = True
    check_functions: bool = True
    whitelist: FrozenSet[str] = frozenset()


@dataclass(frozen=True)
class AnalysisContext:
    """Context for analyzing a single file."""
    tree: ast.Module
    filename: str
    params: AnalysisParameters


class ASTAnalyzer:
    """Utility class for AST analysis operations."""
    
    @staticmethod
    def is_import_context(node: ast.Name, tree: ast.Module) -> bool:
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
    
    @staticmethod
    def collect_top_level_definitions(tree: ast.Module) -> Dict[str, Tuple[str, int]]:
        """Collect top-level function and class definitions.

        Args:
            tree: Parsed AST module.

        Returns:
            Dictionary mapping name to (kind, line_number).
        """
        definitions: Dict[str, Tuple[str, int]] = {}
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                if not node.name.startswith(_PRIVATE_PREFIX):
                    definitions[node.name] = ("function", node.lineno)
            elif isinstance(node, ast.ClassDef) and not node.name.startswith(_PRIVATE_PREFIX):
                definitions[node.name] = ("class", node.lineno)
        return definitions
    
    @staticmethod
    def find_all_assignment(node: ast.AST) -> Optional[ast.expr]:
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
                and isinstance(node.value, ast.List | ast.Tuple)
            ):
                return node.value
        return None


class ImportAnalyzer:
    """Analyzes import usage in Python code."""
    
    @staticmethod
    def collect_imported_names(tree: ast.Module) -> Dict[str, int]:
        """Collect all imported names from AST.

        Args:
            tree: Parsed AST module.

        Returns:
            Dictionary mapping imported name to line number.
        """
        imported: Dict[str, int] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                ImportAnalyzer._collect_import_names(node, imported)
            elif isinstance(node, ast.ImportFrom):
                ImportAnalyzer._collect_import_from_names(node, imported)
        return imported
    
    @staticmethod
    def _collect_import_names(node: ast.Import, imported: Dict[str, int]) -> None:
        """Collect names from ast.Import node.

        Args:
            node: Import AST node.
            imported: Dictionary to update with imported names.
        """
        for alias in node.names:
            name = alias.asname or alias.name.split(".")[0]
            imported[name] = node.lineno
    
    @staticmethod
    def _collect_import_from_names(node: ast.ImportFrom, imported: Dict[str, int]) -> None:
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
    
    @staticmethod
    def collect_used_names(tree: ast.Module) -> Set[str]:
        """Collect all used names from AST (excluding import context).

        Args:
            tree: Parsed AST module.

        Returns:
            Set of used names.
        """
        used_names: Set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and not ASTAnalyzer.is_import_context(node, tree):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                root_name = ImportAnalyzer._extract_attribute_root_name(node)
                if root_name:
                    used_names.add(root_name)
        return used_names
    
    @staticmethod
    def _extract_attribute_root_name(node: ast.Attribute) -> Optional[str]:
        """Extract the root name from an attribute chain.

        Args:
            node: Attribute AST node.

        Returns:
            Root name if found, None otherwise.
        """
        current: ast.expr = node
        while isinstance(current, ast.Attribute):
            current = current.value
        return current.id if isinstance(current, ast.Name) else None


class DefinitionAnalyzer:
    """Analyzes function and class definitions in Python code."""
    
    @staticmethod
    def collect_all_references(tree: ast.Module) -> Set[str]:
        """Collect all name references from AST.

        Args:
            tree: Parsed AST module.

        Returns:
            Set of referenced names.
        """
        used: Set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used.add(node.id)
            elif isinstance(node, ast.Attribute):
                used.add(node.attr)
        return used
    
    @staticmethod
    def get_all_names(tree: ast.Module) -> Optional[Set[str]]:
        """Extract names from __all__ if defined.

        Args:
            tree: Parsed AST module.

        Returns:
            Set of names in __all__, or None if not defined.
        """
        for node in ast.iter_child_nodes(tree):
            all_assignment = ASTAnalyzer.find_all_assignment(node)
            if all_assignment is not None:
                return DefinitionAnalyzer._extract_names_from_all(all_assignment)
        return None
    
    @staticmethod
    def _extract_names_from_all(value: ast.expr) -> Optional[Set[str]]:
        """Extract string names from __all__ list/tuple.

        Args:
            value: AST expression (list or tuple).

        Returns:
            Set of string names, or None if extraction fails.
        """
        if not isinstance(value, ast.List | ast.Tuple):
            return None

        names: Set[str] = set()
        for element in value.elts:
            if isinstance(element, ast.Constant) and isinstance(element.value, str):
                names.add(element.value)
        return names if names else None


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
        return self._build_parameter_schema()

    def _build_parameter_schema(self) -> dict[str, object]:
        """Build the parameter schema for dead code detection."""
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
        whitelist: Optional[List[str]] = None,
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

        params = AnalysisParameters(
            check_imports=check_imports,
            check_functions=check_functions,
            whitelist=DEFAULT_WHITELIST | frozenset(whitelist or [])
        )

        if target.is_file():
            return self._analyze_file(target, params)
        return self._analyze_directory(target, params)

    def _analyze_file(
        self,
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
            context=AnalysisContext(tree=tree, filename=path.name, params=params)
        )
        return ToolResult(content=analysis_result, success=True)

    def _parse_file(self, path: Path) -> ast.Module | ToolResult:
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

    def _perform_analysis(self, context: AnalysisContext) -> str:
        """Perform dead code analysis on parsed AST.

        Args:
            context: Analysis context containing tree, filename, and parameters.

        Returns:
            Formatted analysis results.
        """
        parts: List[str] = [f"Dead code analysis: {context.filename}"]
        findings: List[str] = []

        if context.params.check_imports:
            unused_imports = self._find_unused_imports(context)
            if unused_imports:
                findings.extend(self._format_findings(unused_imports, "Unused imports"))

        if context.params.check_functions:
            unused_defs = self._find_unused_definitions(context)
            if unused_defs:
                findings.extend(self._format_findings(unused_defs, "Possibly unused definitions", include_kind=True))

        if findings:
            parts.extend(findings)
        else:
            parts.append("\n  No dead code detected.")

        return "\n".join(parts)

    def _format_findings(
        self, 
        findings: List[Tuple[str, ...]], 
        title: str,
        include_kind: bool = False
    ) -> List[str]:
        """Format findings for output.

        Args:
            findings: List of finding tuples.
            title: Section title.
            include_kind: Whether to include kind in output.

        Returns:
            Formatted findings lines.
        """
        formatted: List[str] = [f"\n{title}:"]
        for finding in findings:
            if include_kind:
                kind, name, line = finding
                formatted.append(f"  line {line}: {kind} {name}")
            else:
                name, line = finding
                formatted.append(f"  line {line}: {name}")
        return formatted

    def _analyze_directory(
        self,
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
        all_findings: List[str] = []
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
        self,
        context: AnalysisContext,
    ) -> List[Tuple[str, int]]:
        """Find imports that are never used in the file.

        Args:
            context: Analysis context.

        Returns:
            List of (import_name, line_number) tuples.
        """
        imported = ImportAnalyzer.collect_imported_names(context.tree)
        used_names = ImportAnalyzer.collect_used_names(context.tree)
        return self._identify_unused_items(imported, used_names, context.params.whitelist)

    def _find_unused_definitions(
        self,
        context: AnalysisContext,
    ) -> List[Tuple[str, str, int]]:
        """Find functions/classes defined but never referenced.

        Only checks top-level definitions within the same file.

        Args:
            context: Analysis context.

        Returns:
            List of (kind, name, line_number) tuples.
        """
        definitions = ASTAnalyzer.collect_top_level_definitions(context.tree)
        used_names = DefinitionAnalyzer.collect_all_references(context.tree)
        all_names = DefinitionAnalyzer.get_all_names(context.tree)

        if all_names is not None:
            used_names.update(all_names)

        return self._identify_unused_definitions(definitions, used_names, context.params.whitelist)

    def _identify_unused_items(
        self,
        items: Dict[str, int],
        used_names: Set[str],
        whitelist: FrozenSet[str],
    ) -> List[Tuple[str, int]]:
        """Identify unused items from collected data.

        Args:
            items: Dictionary mapping item name to line number.
            used_names: Set of used names.
            whitelist: Names to ignore.

        Returns:
            List of (item_name, line_number) tuples.
        """
        unused: List[Tuple[str, int]] = []
        for name, line in sorted(items.items(), key=lambda x: x[1]):
            if name not in used_names and name not in whitelist:
                unused.append((name, line))
        return unused

    def _identify_unused_definitions(
        self,
        definitions: Dict[str, Tuple[str, int]],
        used_names: Set[str],
        whitelist: FrozenSet[str],
    ) -> List[Tuple[str, str, int]]:
        """Identify unused definitions from collected data.

        Args:
            definitions: Dictionary mapping name to (kind, line_number).
            used_names: Set of used names.
            whitelist: Names to ignore.

        Returns:
            List of (kind, name, line_number) tuples.
        """
        unused: List[Tuple[str, str, int]] = []
        for name, (kind, line) in sorted(definitions.items(), key=lambda x: x[1][1]):
            if name not in whitelist and name not in used_names:
                unused.append((kind, name, line))
        return unused