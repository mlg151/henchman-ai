"""Repository identification utilities for RAG.

This module provides functions to generate unique identifiers for
git repositories to use as cache keys for RAG indices.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass  # No type-only imports currently needed


def get_git_remote_url(git_root: Path) -> str | None:
    """Get the primary remote URL for a git repository.

    Args:
        git_root: Root directory of the git repository.

    Returns:
        Remote URL if available, None otherwise.
    """
    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=git_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return None


def get_git_revision(git_root: Path) -> str | None:
    """Get the current git revision (commit hash).

    Args:
        git_root: Root directory of the git repository.

    Returns:
        Git revision if available, None otherwise.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=git_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()[:12]  # Short hash
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return None


def compute_repository_id(git_root: Path) -> str:
    """Compute a unique identifier for a git repository.

    Uses a combination of remote URL and local path to create a
    deterministic identifier that's consistent across different
    checkouts of the same repository.

    Args:
        git_root: Root directory of the git repository.

    Returns:
        Unique identifier string (SHA256 hash).
    """
    # Try to use remote URL first (most stable)
    remote_url = get_git_remote_url(git_root)
    if remote_url:
        # Normalize URL (remove .git suffix, normalize protocols)
        normalized = remote_url.lower().removesuffix(".git")
        if normalized.startswith(("http://", "https://", "git@")):
            # Use normalized remote URL as base
            base = normalized
        else:
            # Fall back to path-based ID
            base = str(git_root.resolve())
    else:
        # No remote, use path with git revision if available
        revision = get_git_revision(git_root)
        base = f"{git_root.resolve()}:{revision}" if revision else str(git_root.resolve())

    # Compute SHA256 hash
    return hashlib.sha256(base.encode()).hexdigest()[:16]  # 16 chars is enough


def get_rag_cache_dir(base_cache_dir: Path | None = None) -> Path:
    """Get the RAG cache directory in user's home directory.

    Args:
        base_cache_dir: Optional custom base cache directory.
            If None, uses ~/.henchman/rag_indices/

    Returns:
        Path to the RAG cache directory.
    """
    if base_cache_dir:
        cache_dir = Path(base_cache_dir)
    else:
        home = Path.home()
        cache_dir = home / ".henchman" / "rag_indices"

    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_repository_index_dir(
    git_root: Path,
    base_cache_dir: Path | None = None,
) -> Path:
    """Get the index directory for a specific repository.

    Args:
        git_root: Root directory of the git repository.
        base_cache_dir: Optional custom base cache directory.

    Returns:
        Path to the repository-specific index directory.
    """
    cache_dir = get_rag_cache_dir(base_cache_dir)
    repo_id = compute_repository_id(git_root)
    return cache_dir / repo_id


def get_repository_manifest_path(
    git_root: Path,
    base_cache_dir: Path | None = None,
) -> Path:
    """Get the manifest file path for a repository.

    Args:
        git_root: Root directory of the git repository.
        base_cache_dir: Optional custom base cache directory.

    Returns:
        Path to the manifest file.
    """
    index_dir = get_repository_index_dir(git_root, base_cache_dir)
    return index_dir / "manifest.json"


def migrate_old_index(git_root: Path, new_index_dir: Path) -> bool:
    """Migrate old project-based index to new home directory location.

    Args:
        git_root: Root directory of the git repository.
        new_index_dir: New index directory in home directory.

    Returns:
        True if migration was performed, False if no old index found.
    """
    old_index_dir = git_root / ".henchman" / "rag_index"
    old_manifest = git_root / ".henchman" / "rag_manifest.json"

    if not old_index_dir.exists() and not old_manifest.exists():
        return False

    # Create new directory
    new_index_dir.mkdir(parents=True, exist_ok=True)

    migrated = False

    # Migrate ChromaDB if it exists
    if old_index_dir.exists():
        try:
            # ChromaDB is just a directory with files
            import shutil

            shutil.copytree(old_index_dir, new_index_dir / "chroma", dirs_exist_ok=True)
            migrated = True
        except Exception:
            # If migration fails, we'll just reindex
            pass

    # Migrate manifest if it exists
    if old_manifest.exists():
        try:
            import shutil

            shutil.copy2(old_manifest, new_index_dir / "manifest.json")
            migrated = True
        except Exception:
            pass

    return migrated
