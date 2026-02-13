"""RAG system initialization and management.

This module provides helper functions for initializing and managing
the RAG system in the CLI.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console

    from henchman.config.schema import RagSettings
    from henchman.rag.indexer import GitFileIndexer, IndexStats
    from henchman.rag.store import VectorStore
    from henchman.tools.builtins.rag_search import RagSearchTool

from henchman.rag.concurrency import RagLock
from henchman.rag.repo_id import (
    get_repository_index_dir,
    get_repository_manifest_path,
    migrate_old_index,
)


def find_git_root(start: Path | None = None) -> Path | None:
    """Find the git repository root.

    Args:
        start: Starting directory. Defaults to cwd.

    Returns:
        Path to git root, or None if not in a git repo.
    """
    current = (start or Path.cwd()).resolve()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return None


class RagSystem:
    """Manages the RAG system components.

    This class initializes and provides access to the RAG components
    including embedder, chunker, store, indexer, and search tool.

    Attributes:
        git_root: Root directory of the git repository.
        settings: RAG settings from configuration.
        store: The vector store.
        indexer: The git file indexer.
        search_tool: The RAG search tool.
    """

    def __init__(
        self,
        git_root: Path,
        settings: RagSettings,
        read_only: bool = False,
    ) -> None:
        """Initialize the RAG system.

        Args:
            git_root: Root directory of the git repository.
            settings: RAG settings from configuration.
            read_only: If True, skip indexing (for concurrent instances).
        """
        from henchman.rag.chunker import TextChunker
        from henchman.rag.embedder import FastEmbedProvider
        from henchman.rag.indexer import GitFileIndexer
        from henchman.rag.store import VectorStore
        from henchman.tools.builtins.rag_search import RagSearchTool

        self.git_root = git_root
        self.settings = settings
        self.read_only = read_only
        self.is_indexing = False

        # Get cache directory
        cache_dir = Path(settings.cache_dir) if settings.cache_dir else None

        # Get repository-specific index directory
        self.index_dir = get_repository_index_dir(git_root, cache_dir)
        self.manifest_path = get_repository_manifest_path(git_root, cache_dir)

        # Initialize lock for this RAG index
        self._lock = RagLock(self.index_dir / ".rag.lock")
        self._init_lock_held = False

        # Acquire lock during initialization to prevent ChromaDB conflicts
        # This is especially important when multiple instances start simultaneously
        if not read_only:
            if self._lock.acquire(timeout=10.0):
                self._init_lock_held = True
            else:
                # Another instance is initializing, switch to read-only mode
                self.read_only = True

        # Initialize embedder
        self._embedder = FastEmbedProvider(model_name=settings.embedding_model)

        # Initialize chunker
        self._chunker = TextChunker(
            target_tokens=settings.chunk_size,
            overlap_tokens=settings.chunk_overlap,
        )

        # Initialize vector store
        # Store ChromaDB in subdirectory for cleanliness
        chroma_path = self.index_dir / "chroma"
        self._store = VectorStore(
            persist_path=chroma_path,
            embedder=self._embedder,
        )

        # Initialize indexer
        self._indexer = GitFileIndexer(
            git_root=git_root,
            store=self._store,
            embedder=self._embedder,
            chunker=self._chunker,
            file_extensions=settings.file_extensions,
            manifest_path=self.manifest_path,
        )

        # Initialize search tool
        self._search_tool = RagSearchTool(
            store=self._store,
            top_k=settings.top_k,
        )

        # Release lock after initialization if we held it
        # (indexing will re-acquire it)
        if self._init_lock_held:
            self._lock.release()
            self._init_lock_held = False

    @property
    def store(self) -> VectorStore:
        """Get the vector store."""
        return self._store

    @property
    def indexer(self) -> GitFileIndexer:
        """Get the git file indexer."""
        return self._indexer

    @property
    def search_tool(self) -> RagSearchTool:
        """Get the RAG search tool."""
        return self._search_tool

    def index(
        self,
        console: Console | None = None,
        force: bool = False,
        skip_if_locked: bool = True,
    ) -> IndexStats | None:
        """Run indexing operation with locking.

        Args:
            console: Rich console for progress display.
            force: If True, force full reindex.
            skip_if_locked: If True and lock cannot be acquired,
                skip indexing and return None.

        Returns:
            Statistics about the indexing operation, or None if
            indexing was skipped due to lock contention.
        """
        # Skip indexing if in read-only mode
        if self.read_only:
            if console:
                console.print("[dim]RAG: Read-only mode, skipping indexing[/dim]")
            return None

        # Try to acquire lock
        if not self._lock.acquire(timeout=5.0):
            if skip_if_locked:
                if console:
                    console.print(
                        "[dim]RAG index is locked by another instance, skipping indexing[/dim]"
                    )
                return None
            else:
                # This would raise LockTimeoutError from the context manager
                # if we were using `with self._lock:`
                raise RuntimeError(f"Could not acquire RAG lock at {self._lock.lock_path}")

        self.is_indexing = True
        try:
            # Run indexing with lock held
            return self._indexer.index(console=console, force=force)
        finally:
            # Always release the lock
            self._lock.release()
            self.is_indexing = False

    async def index_async(
        self,
        console: Console | None = None,
        force: bool = False,
        skip_if_locked: bool = True,
    ) -> IndexStats | None:
        """Run indexing operation asynchronously in a separate thread.

        Args:
            console: Rich console for progress display.
            force: If True, force full reindex.
            skip_if_locked: If True and lock cannot be acquired,
                skip indexing and return None.

        Returns:
            Statistics about the indexing operation.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: self.index(console=console, force=force, skip_if_locked=skip_if_locked)
        )

    def get_stats(self) -> IndexStats:
        """Get current index statistics.

        Returns:
            Current index statistics.
        """
        return self._indexer.get_stats()

    def clear(self) -> None:
        """Clear the index."""
        self._store.clear()
        # Also clear the manifest
        if self.manifest_path.exists():
            self.manifest_path.unlink()


def initialize_rag(
    settings: RagSettings,
    console: Console | None = None,
    git_root: Path | None = None,
    index: bool = True,
) -> RagSystem | None:
    """Initialize the RAG system if in a git repository.

    Args:
        settings: RAG settings from configuration.
        console: Rich console for output.
        git_root: Optional pre-computed git root.
        index: Whether to run indexing immediately (blocking).

    Returns:
        RagSystem instance if successful, None if not in a git repo
        or RAG is disabled.
    """
    if not settings.enabled:
        return None

    root = git_root or find_git_root()
    if not root:
        return None

    try:
        # Check for and migrate old index
        cache_dir = Path(settings.cache_dir) if settings.cache_dir else None
        new_index_dir = get_repository_index_dir(root, cache_dir)

        migrated = migrate_old_index(root, new_index_dir)
        if migrated and console:
            console.print(
                "[dim]Migrated RAG index from project directory to ~/.henchman/rag_indices/[/dim]"
            )

        rag_system = RagSystem(git_root=root, settings=settings)

        if not index:
            return rag_system

        # Run indexing (blocking)
        stats = rag_system.index(console=console)

        # Show summary
        if console and stats is not None and (stats.files_added or stats.files_updated or stats.files_removed):
            console.print(
                f"[dim]RAG index updated: "
                f"{stats.files_added} added, "
                f"{stats.files_updated} updated, "
                f"{stats.files_removed} removed "
                f"({stats.total_chunks} chunks)[/dim]"
            )
        elif console and stats is not None and stats.total_chunks > 0:
            console.print(
                f"[dim]RAG index ready: {stats.files_unchanged} files, "
                f"{stats.total_chunks} chunks[/dim]"
            )

        return rag_system

    except Exception as e:
        if console:
            console.print(f"[yellow]Warning: Failed to initialize RAG: {e}[/yellow]")
        return None
