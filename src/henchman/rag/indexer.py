"""Git file indexer for RAG.

This module provides incremental indexing of git-tracked files
with hash-based change detection.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from rich.progress import Progress, SpinnerColumn, TextColumn

if TYPE_CHECKING:
    from collections.abc import Callable

    from rich.console import Console

    from henchman.rag.chunker import TextChunker
    from henchman.rag.embedder import EmbeddingProvider
    from henchman.rag.store import VectorStore


@dataclass
class IndexManifest:
    """Manifest tracking indexed files and their hashes.

    Attributes:
        files: Mapping of file path to content hash.
        model_name: Name of the embedding model used.
        chunk_size: Chunk size used for indexing.
    """

    files: dict[str, str] = field(default_factory=dict)
    model_name: str = ""
    chunk_size: int = 512

    def save(self, path: Path) -> None:
        """Save manifest to disk.

        Args:
            path: Path to save the manifest.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "files": self.files,
                    "model_name": self.model_name,
                    "chunk_size": self.chunk_size,
                }
            )
        )

    @classmethod
    def load(cls, path: Path) -> IndexManifest:
        """Load manifest from disk.

        Args:
            path: Path to load the manifest from.

        Returns:
            Loaded IndexManifest, or empty manifest if file doesn't exist.
        """
        if not path.exists():
            return cls()

        try:
            data = json.loads(path.read_text())
            return cls(
                files=data.get("files", {}),
                model_name=data.get("model_name", ""),
                chunk_size=data.get("chunk_size", 512),
            )
        except (json.JSONDecodeError, KeyError):
            return cls()


@dataclass
class IndexStats:
    """Statistics from an indexing operation.

    Attributes:
        files_added: Number of files added.
        files_updated: Number of files updated.
        files_removed: Number of files removed.
        files_unchanged: Number of files unchanged.
        total_chunks: Total chunks in the index.
    """

    files_added: int = 0
    files_updated: int = 0
    files_removed: int = 0
    files_unchanged: int = 0
    total_chunks: int = 0


class GitFileIndexer:
    """Indexes git-tracked files for RAG.

    Provides incremental indexing based on file content hashes,
    only re-indexing files that have changed.

    Attributes:
        git_root: Root directory of the git repository.
        store: Vector store for embeddings.
        embedder: Embedding provider.
        chunker: Text chunker.
        file_extensions: File extensions to index.
    """

    def __init__(
        self,
        git_root: Path,
        store: VectorStore,
        embedder: EmbeddingProvider,
        chunker: TextChunker,
        file_extensions: list[str] | None = None,
        manifest_path: Path | None = None,
    ) -> None:
        """Initialize the git file indexer.

        Args:
            git_root: Root directory of the git repository.
            store: Vector store for embeddings.
            embedder: Embedding provider.
            chunker: Text chunker.
            file_extensions: File extensions to index (None = all).
            manifest_path: Optional custom path for manifest file.
                If None, uses git_root/.henchman/rag_manifest.json
        """
        self.git_root = git_root
        self.store = store
        self.embedder = embedder
        self.chunker = chunker
        self.file_extensions = set(file_extensions) if file_extensions else None

        # Manifest path
        if manifest_path is None:
            self.manifest_path = git_root / ".henchman" / "rag_manifest.json"
        else:
            self.manifest_path = manifest_path

    def get_tracked_files(self) -> list[Path]:
        """Get list of git-tracked files.

        Returns:
            List of paths to tracked files.
        """
        try:
            result = subprocess.run(
                ["git", "ls-files"],
                cwd=self.git_root,
                capture_output=True,
                text=True,
                check=True,
            )
            files = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                file_path = self.git_root / line
                if self._should_index(file_path):
                    files.append(file_path)
            return files
        except subprocess.CalledProcessError:
            return []

    def _should_index(self, path: Path) -> bool:
        """Check if a file should be indexed.

        Args:
            path: Path to check.

        Returns:
            True if the file should be indexed.
        """
        if not path.is_file():
            return False

        # Check extension filter
        if self.file_extensions:
            suffix = path.suffix.lower()
            # Also check for files without extension but matching name
            name_lower = path.name.lower()
            if suffix not in self.file_extensions:
                # Check special files like Makefile, Dockerfile
                special_names = {".dockerfile", ".makefile"}
                if f".{name_lower}" not in special_names:
                    return False

        return True

    def _compute_file_hash(self, path: Path) -> str:
        """Compute content hash for a file.

        Args:
            path: Path to the file.

        Returns:
            SHA256 hash of file contents.
        """
        try:
            content = path.read_bytes()
            return hashlib.sha256(content).hexdigest()
        except OSError:
            return ""

    def index(
        self,
        console: Console | None = None,
        force: bool = False,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> IndexStats:
        """Index or update the vector store.

        Args:
            console: Rich console for progress display.
            force: If True, force full reindex.
            progress_callback: Optional callback for progress updates.

        Returns:
            Statistics about the indexing operation.
        """
        stats = IndexStats()

        # Load existing manifest
        manifest = IndexManifest.load(self.manifest_path)

        # Check if we need full reindex due to config change
        if (
            manifest.model_name
            and manifest.model_name != self.embedder.model_name
            or manifest.chunk_size != self.chunker.target_tokens
        ):
            force = True

        if force:
            self.store.clear()
            manifest = IndexManifest()

        # Get current tracked files
        tracked_files = self.get_tracked_files()
        current_file_hashes: dict[str, str] = {}

        # Compute hashes for all tracked files
        for file_path in tracked_files:
            rel_path = str(file_path.relative_to(self.git_root))
            current_file_hashes[rel_path] = self._compute_file_hash(file_path)

        # Find files to add/update/remove
        files_to_index: list[tuple[Path, str]] = []
        files_to_remove: list[str] = []

        # Check for new or modified files
        for rel_path, current_hash in current_file_hashes.items():
            if rel_path not in manifest.files:
                # New file
                files_to_index.append((self.git_root / rel_path, rel_path))
                stats.files_added += 1
            elif manifest.files[rel_path] != current_hash:
                # Modified file
                files_to_index.append((self.git_root / rel_path, rel_path))
                stats.files_updated += 1
            else:
                stats.files_unchanged += 1

        # Check for removed files
        for rel_path in manifest.files:
            if rel_path not in current_file_hashes:
                files_to_remove.append(rel_path)
                stats.files_removed += 1

        # Remove deleted files from store
        for rel_path in files_to_remove:
            self.store.delete_by_file(rel_path)

        # Index new/modified files
        if files_to_index:
            self._index_files(
                files_to_index,
                console=console,
                progress_callback=progress_callback,
            )

        # Update manifest
        manifest.files = current_file_hashes
        manifest.model_name = self.embedder.model_name
        manifest.chunk_size = self.chunker.target_tokens
        manifest.save(self.manifest_path)

        stats.total_chunks = self.store.count()
        return stats

    def _index_files(
        self,
        files: list[tuple[Path, str]],
        console: Console | None = None,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Index a list of files.

        Args:
            files: List of (absolute_path, relative_path) tuples.
            console: Rich console for progress display.
            progress_callback: Optional callback for progress updates.
        """
        total = len(files)

        if console:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(f"Indexing {total} files...", total=total)

                for i, (abs_path, rel_path) in enumerate(files):
                    # Delete existing chunks for this file (if updating)
                    self.store.delete_by_file(rel_path)

                    # Chunk the file
                    chunks = self.chunker.chunk_file(abs_path)
                    if chunks:
                        # Update chunk file paths to relative
                        for chunk in chunks:
                            chunk.file_path = rel_path

                        # Generate embeddings
                        embeddings = self.embedder.embed([c.content for c in chunks])

                        # Add to store
                        self.store.add_chunks(chunks, embeddings)

                    progress.update(task, advance=1)
                    if progress_callback:
                        progress_callback(rel_path, i + 1, total)
        else:
            for i, (abs_path, rel_path) in enumerate(files):
                # Delete existing chunks for this file (if updating)
                self.store.delete_by_file(rel_path)

                # Chunk the file
                chunks = self.chunker.chunk_file(abs_path)
                if chunks:
                    # Update chunk file paths to relative
                    for chunk in chunks:
                        chunk.file_path = rel_path

                    # Generate embeddings
                    embeddings = self.embedder.embed([c.content for c in chunks])

                    # Add to store
                    self.store.add_chunks(chunks, embeddings)

                if progress_callback:
                    progress_callback(rel_path, i + 1, total)

    def get_stats(self) -> IndexStats:
        """Get current index statistics.

        Returns:
            Current index statistics.
        """
        manifest = IndexManifest.load(self.manifest_path)
        return IndexStats(
            files_unchanged=len(manifest.files),
            total_chunks=self.store.count(),
        )
