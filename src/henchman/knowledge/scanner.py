"""Lightweight code scanner for auto-populating the knowledge graph.

Walks git-tracked Python files to extract:
- File and package entities
- Import relationships
- Top-level class and function names with docstrings
"""

from __future__ import annotations

import ast
import hashlib
import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from henchman.knowledge.models import Entity, Observation, Relation

if TYPE_CHECKING:
    from pathlib import Path

    from henchman.knowledge.store import KnowledgeStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScanContext:
    """Context for scanning files in a repository."""

    store: KnowledgeStore
    git_root: Path
    incremental: bool
    module_to_eid: dict[str, str]


def _file_hash(path: Path) -> str:
    """Compute a fast content hash for change detection.

    Args:
        path: File to hash.

    Returns:
        Hex digest of the file contents.
    """
    return hashlib.md5(path.read_bytes()).hexdigest()


def _path_to_entity_id(rel_path: str) -> str:
    """Convert a relative file path to a graph entity id.

    Args:
        rel_path: Path relative to repo root (e.g. ``src/foo/bar.py``).

    Returns:
        Slugified entity id.
    """
    return (
        rel_path.lower()
        .replace("/", "-")
        .replace("\\", "-")
        .replace(".", "-")
        .replace("_", "-")
        .rstrip("-")
    )


def _path_to_module(rel_path: str) -> str:
    """Convert ``src/foo/bar.py`` to dotted module ``src.foo.bar``.

    Args:
        rel_path: Relative file path.

    Returns:
        Dotted module string.
    """
    return rel_path.replace("/", ".").replace("\\", ".").removesuffix(".py")


def _get_git_tracked_python_files(git_root: Path) -> list[str]:
    """Get all git-tracked Python files as repo-relative paths.

    Args:
        git_root: Repository root.

    Returns:
        List of relative paths (forward-slash separated).
    """
    try:
        result = subprocess.run(
            ["git", "ls-files", "*.py"],
            cwd=git_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except (subprocess.SubprocessError, FileNotFoundError):
        return []


def _extract_imports(source: str) -> list[str]:
    """Extract imported module names from Python source.

    Args:
        source: Python source code.

    Returns:
        List of top-level module names imported.
    """
    modules: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return modules

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module.split(".")[0])
    return list(set(modules))


def _extract_top_level_defs(source: str) -> list[tuple[str, str, str]]:
    """Extract top-level class and function definitions.

    Args:
        source: Python source code.

    Returns:
        List of ``(kind, name, docstring)`` tuples where kind is
        ``"class"`` or ``"function"``.
    """
    defs: list[tuple[str, str, str]] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return defs

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            docstring = ast.get_docstring(node) or ""
            defs.append((kind, node.name, docstring))
    return defs


def _get_package_entities(python_files: list[str]) -> dict[str, Entity]:
    """Create package entities from directory structure.

    Args:
        python_files: Relative paths of Python files.

    Returns:
        Mapping of entity id → Entity for each package directory.
    """
    packages: dict[str, Entity] = {}
    seen_dirs: set[str] = set()

    for rel_path in python_files:
        parts = rel_path.split("/")
        for i in range(1, len(parts)):
            dir_path = "/".join(parts[:i])
            if dir_path in seen_dirs:
                continue
            seen_dirs.add(dir_path)
            eid = _path_to_entity_id(dir_path)
            packages[eid] = Entity(
                id=eid,
                entity_type="package",
                name=dir_path,
                description=f"Python package: {dir_path}",
                file_path=dir_path,
                tags=["auto-scanned"],
            )
    return packages


def _build_module_lookup(python_files: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    """Build lookup dictionaries for import resolution.

    Args:
        python_files: Relative paths of Python files.

    Returns:
        Tuple of (module_to_eid, eid_to_module) dictionaries.
    """
    module_to_eid: dict[str, str] = {}
    eid_to_module: dict[str, str] = {}

    # First pass: collect all files and their mappings
    file_mappings: list[tuple[str, str, str]] = []  # (rel_path, module, eid)
    for rel_path in python_files:
        module = _path_to_module(rel_path)
        eid = _path_to_entity_id(rel_path)
        file_mappings.append((rel_path, module, eid))
        eid_to_module[eid] = module

    # Sort files to ensure consistent priority:
    # 1. __init__.py files first (for package priority)
    # 2. Then sort by module name for deterministic behavior
    def sort_key(item: tuple[str, str, str]) -> tuple[int, str]:
        rel_path, module, _ = item
        # __init__.py files get priority 0, others 1
        priority = (
            0 if rel_path.endswith("/__init__.py") or rel_path.endswith("\\__init__.py") else 1
        )
        return (priority, module)

    file_mappings.sort(key=sort_key)

    for rel_path, module, eid in file_mappings:
        # Store mapping for full module name
        module_to_eid[module] = eid

        # Handle package __init__.py files specially
        # For foo/__init__.py (module = "foo.__init__"), also map "foo" to this file
        if rel_path.endswith("/__init__.py") or rel_path.endswith("\\__init__.py"):
            package_name = module.removesuffix(".__init__")
            # Only map package name if not already mapped (module foo.py takes precedence)
            if package_name not in module_to_eid:  # pragma: no branch
                module_to_eid[package_name] = eid

        # Also store mapping for the last part (filename without .py)
        # This handles imports like "import foo" when file is "bar/foo.py"
        last_part = module.split(".")[-1]
        # Skip __init__ as a last_part mapping (not useful for imports)
        if last_part != "__init__" and last_part not in module_to_eid:
            module_to_eid[last_part] = eid

    return module_to_eid, eid_to_module


def _find_import_target(
    mod: str,
    file_eid: str,
    python_files: list[str],
) -> str | None:
    """Find the entity ID of a file that matches the import module name.

    Args:
        mod: Module name being imported.
        file_eid: Entity ID of the importing file (to avoid self-loops).
        python_files: Relative paths of all Python files in the repo.

    Returns:
        Entity ID of the first matching file, or None if not found.
    """
    for other_path in python_files:
        other_module = _path_to_module(other_path)
        if other_module.split(".")[-1] == mod or other_module.startswith(mod):
            other_eid = _path_to_entity_id(other_path)
            if other_eid != file_eid:
                return other_eid
            break  # self-match — stop searching
    return None


def _is_self_import(mod: str, file_module: str | None) -> bool:
    """Check if the module being imported is the file itself.

    Args:
        mod: Module name being imported.
        file_module: Module name of the importing file.

    Returns:
        True if it's a self-import.
    """
    if not file_module:
        return False
    if file_module == mod:
        return True
    if file_module.endswith(".__init__"):
        package_name = file_module.removesuffix(".__init__")
        if package_name == mod:
            return True
    return False


def _find_import_target_optimized(
    mod: str,
    file_eid: str,
    file_module: str | None,
    module_to_eid: dict[str, str],
) -> str | None:
    """Find the entity ID of a file that matches the import module name.

    Optimized version using precomputed lookup dictionaries.

    Args:
        mod: Module name being imported.
        file_eid: Entity ID of the importing file (to avoid self-loops).
        file_module: Module name of the importing file (for self-import detection).
        module_to_eid: Precomputed module to entity ID mapping.

    Returns:
        Entity ID of the first matching file, or None if not found.
    """
    if _is_self_import(mod, file_module):
        return None

    # Find all candidates (exact or prefix)
    candidates: list[tuple[str, str]] = []
    for key, value in module_to_eid.items():
        if key == mod or key.startswith(mod + "."):
            if value == file_eid:
                continue  # Skip self-match, but keep looking for others
            candidates.append((key, value))

    if not candidates:
        return None

    # Sort candidates by priority:
    # 1. Exact matches first (key == mod)
    # 2. Package __init__.py files next (key ends with .__init__)
    # 3. Everything else
    def candidate_priority(item: tuple[str, str]) -> tuple[int, str]:
        key, _ = item
        if key == mod:
            return (0, key)
        if key.endswith(".__init__"):
            return (1, key)
        return (2, key)

    candidates.sort(key=candidate_priority)
    return candidates[0][1]


def _scan_packages(store: KnowledgeStore, python_files: list[str]) -> None:
    """Identify and add package entities and their hierarchy to the store."""
    packages = _get_package_entities(python_files)
    for pkg in packages.values():
        store.add_entity(pkg)

    # Add parent-child "contains" edges for packages
    for eid, pkg in packages.items():
        parts = (pkg.file_path or "").split("/")
        if len(parts) > 1:
            parent_path = "/".join(parts[:-1])
            parent_id = _path_to_entity_id(parent_path)
            if parent_id in packages:  # pragma: no branch
                store.add_relation(
                    Relation(
                        source=parent_id,
                        target=eid,
                        relation_type="contains",
                    ),
                )


def _create_file_entity(rel_path: str, source: str) -> Entity:
    """Create a file entity with observations from top-level definitions.

    Args:
        rel_path: Relative path to the file.
        source: Source code of the file.

    Returns:
        The created file entity.
    """
    file_eid = _path_to_entity_id(rel_path)
    file_entity = Entity(
        id=file_eid,
        entity_type="file",
        name=rel_path,
        description=f"Python file: {rel_path}",
        file_path=rel_path,
        tags=["auto-scanned"],
    )

    # Extract top-level defs as observations on the file
    defs = _extract_top_level_defs(source)
    for kind, name, docstring in defs:
        summary = f"{kind} `{name}`"
        if docstring:
            first_line = docstring.strip().split("\n")[0]
            summary += f": {first_line}"
        file_entity.observations.append(
            Observation(content=summary, source=rel_path, author="auto"),
        )
    return file_entity


def _add_containment_relation(store: KnowledgeStore, rel_path: str, file_eid: str) -> None:
    """Add a relation between a file and its parent package.

    Args:
        store: Knowledge store.
        rel_path: Relative path to the file.
        file_eid: Entity ID of the file.
    """
    parts = rel_path.split("/")
    if len(parts) > 1:
        parent_dir = "/".join(parts[:-1])
        parent_id = _path_to_entity_id(parent_dir)
        store.add_relation(
            Relation(
                source=parent_id,
                target=file_eid,
                relation_type="contains",
            ),
        )


def _add_import_relations(
    ctx: ScanContext,
    rel_path: str,
    file_eid: str,
    source: str,
) -> None:
    """Add 'imports' relations for a file.

    Args:
        ctx: Scanning context.
        rel_path: Relative path to the file.
        file_eid: Entity ID of the file.
        source: Source code of the file.
    """
    imports = _extract_imports(source)
    file_module = _path_to_module(rel_path)
    for mod in imports:
        target_eid = _find_import_target_optimized(mod, file_eid, file_module, ctx.module_to_eid)
        if target_eid:
            ctx.store.add_relation(
                Relation(
                    source=file_eid,
                    target=target_eid,
                    relation_type="imports",
                ),
            )


def _scan_file(ctx: ScanContext, rel_path: str) -> bool:
    """Process a single Python file and update the store.

    Args:
        ctx: Scanning context.
        rel_path: Path relative to repository root.

    Returns:
        True if the file was processed, False if it was skipped or didn't exist.
    """
    abs_path = ctx.git_root / rel_path
    if not abs_path.exists():
        return False

    # Incremental: skip unchanged files
    content_hash = _file_hash(abs_path)
    if ctx.incremental and ctx.store.meta.file_hashes.get(rel_path) == content_hash:
        return False

    ctx.store.meta.file_hashes[rel_path] = content_hash
    source = abs_path.read_text(errors="replace")
    file_eid = _path_to_entity_id(rel_path)

    # Create and add file entity
    file_entity = _create_file_entity(rel_path, source)
    ctx.store.add_entity(file_entity)

    # Add relations
    _add_containment_relation(ctx.store, rel_path, file_eid)
    _add_import_relations(ctx, rel_path, file_eid, source)

    return True


def scan_repository(  # noqa: C901, PLR0912
    store: KnowledgeStore,
    git_root: Path,
    *,
    incremental: bool = True,
) -> int:
    """Scan a git repository and populate the knowledge graph.

    Args:
        store: Knowledge store to populate.
        git_root: Repository root directory.
        incremental: If True, skip files whose hash hasn't changed.

    Returns:
        Number of files processed.
    """
    python_files = _get_git_tracked_python_files(git_root)
    if not python_files:
        return 0

    now = datetime.now(timezone.utc).isoformat()

    # Precompute module lookups for O(1) import matching
    module_to_eid, _ = _build_module_lookup(python_files)

    # Process package hierarchy
    _scan_packages(store, python_files)

    ctx = ScanContext(
        store=store,
        git_root=git_root,
        incremental=incremental,
        module_to_eid=module_to_eid,
    )

    processed = 0
    for rel_path in python_files:
        if _scan_file(ctx, rel_path):
            processed += 1

    store.meta.last_indexed = now
    return processed
