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
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from henchman.knowledge.models import Entity, Observation, Relation

if TYPE_CHECKING:
    from pathlib import Path

    from henchman.knowledge.store import KnowledgeStore

logger = logging.getLogger(__name__)


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


def scan_repository(
    store: KnowledgeStore,
    git_root: Path,
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
    processed = 0

    # Add package entities and contains relations
    packages = _get_package_entities(python_files)
    for pkg in packages.values():
        store.add_entity(pkg)

    # Add parent-child "contains" edges for packages
    for eid, pkg in packages.items():
        parts = (pkg.file_path or "").split("/")
        if len(parts) > 1:
            parent_path = "/".join(parts[:-1])
            parent_id = _path_to_entity_id(parent_path)
            if parent_id in packages:
                store.add_relation(
                    Relation(
                        source=parent_id,
                        target=eid,
                        relation_type="contains",
                    ),
                )

    for rel_path in python_files:
        abs_path = git_root / rel_path
        if not abs_path.exists():
            continue

        # Incremental: skip unchanged files
        content_hash = _file_hash(abs_path)
        if incremental and store.meta.file_hashes.get(rel_path) == content_hash:
            continue

        store.meta.file_hashes[rel_path] = content_hash
        source = abs_path.read_text(errors="replace")
        file_eid = _path_to_entity_id(rel_path)

        # File entity
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

        store.add_entity(file_entity)

        # File → package "contains" relation
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

        # Import relations (file-to-file within the repo)
        imports = _extract_imports(source)
        for mod in imports:
            target_eid = _find_import_target(mod, file_eid, python_files)
            if target_eid:
                store.add_relation(
                    Relation(
                        source=file_eid,
                        target=target_eid,
                        relation_type="imports",
                    ),
                )

        processed += 1

    store.meta.last_indexed = now
    return processed
