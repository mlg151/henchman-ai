"""Git file indexer for RAG.

This module provides incremental indexing of git-tracked files
with hash-based change detection.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rich.progress import Progress, SpinnerColumn, TextColumn

# Default chunk size used when not specified in manifest
DEFAULT_CHUNK_SIZE: int = 512

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

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
    chunk_size: int = DEFAULT_CHUNK_SIZE

    def save(self: IndexManifest, path: Path) -> None:
        """Save manifest to disk.

        Args:
            path: Path to save the manifest.

        Returns:
            None
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "files": self.files,
                    "model_name": self.model_name,
                    "chunk_size": self.chunk_size,
                },
            ),
        )

    @classmethod
    def load(cls: type[IndexManifest], path: Path) -> IndexManifest:
        """Load manifest from disk.

        Args:
            path: Path to load the manifest from.

        Returns:
            Loaded IndexManifest, or empty manifest if file doesn't exist.
        """
        if not path.exists():
            return cls()

        try:
            return _manifest_from_dict(cls, json.loads(path.read_text()))
        except (json.JSONDecodeError, KeyError):
            return cls()


def _manifest_from_dict(
    cls: type[IndexManifest],
    data: dict[str, object],
) -> IndexManifest:
    """Construct an IndexManifest from a raw JSON-decoded dictionary.

    Extracted as a module-level helper so that the logic of converting
    JSON data lives close to the data, not inside a classmethod that
    merely orchestrates I/O.

    Args:
        cls: The IndexManifest class (or a subclass) to instantiate.
        data: Dictionary with optional keys ``files``, ``model_name``,
            and ``chunk_size``.

    Returns:
        Populated IndexManifest instance.
    """
    return cls(
        files=data.get("files", {}),  # type: ignore[arg-type]
        model_name=data.get("model_name", ""),  # type: ignore[arg-type]
        chunk_size=data.get("chunk_size", DEFAULT_CHUNK_SIZE),  # type: ignore[arg-type]
    )


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


def _file_should_be_indexed(path: Path, file_extensions: set[str] | None) -> bool:
    """Determine whether a file should be included in the RAG index.

    Args:
        path: Candidate file path.
        file_extensions: Allowed suffix set (e.g. ``{".py", ".md"}``), or
            ``None`` to accept every file.

    Returns:
        True if the file exists and passes the extension filter.
    """
    if not path.is_file():
        return False

    if file_extensions is None:
        return True

    suffix = path.suffix.lower()
    if suffix in file_extensions:
        return True

    # Accept special extensionless files like Makefile, Dockerfile
    special_names = {".dockerfile", ".makefile"}
    return f".{path.name.lower()}" in special_names


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
        self: GitFileIndexer,
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

    def get_tracked_files(self: GitFileIndexer) -> list[Path]:
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
        except subprocess.CalledProcessError:
            return []
        else:
            return files

    def _should_index(self: GitFileIndexer, path: Path) -> bool:
        """Check if a file should be indexed.

        Args:
            path: Path to check.

        Returns:
            True if the file should be indexed.
        """
        return _file_should_be_indexed(path, self.file_extensions)

    def _compute_file_hash(self: GitFileIndexer, path: Path) -> str:
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

    def _needs_full_reindex(self: GitFileIndexer, manifest: IndexManifest) -> bool:
        """Return True when the embedding config has changed since the last run.

        Args:
            manifest: Previously saved manifest to compare against.

        Returns:
            True if a full reindex is required.
        """
        model_changed = (
            bool(manifest.model_name)
            and manifest.model_name != self.embedder.model_name
        )
        chunk_size_changed = manifest.chunk_size != self.chunker.target_tokens
        return model_changed or chunk_size_changed

    def _compute_current_hashes(self: GitFileIndexer) -> dict[str, str]:
        """Return a mapping of repo-relative path to SHA-256 hash for tracked files.

        Returns:
            Dict mapping relative file paths to their content hashes.
        """
        return {
            str(fp.relative_to(self.git_root)): self._compute_file_hash(fp)
            for fp in self.get_tracked_files()
        }

    def _classify_file_changes(
        self: GitFileIndexer,
        current_hashes: dict[str, str],
        manifest: IndexManifest,
    ) -> tuple[list[tuple[Path, str]], list[str], IndexStats]:
        """Classify files as added, updated, unchanged, or removed.

        Args:
            current_hashes: Current mapping of relative path to hash.
            manifest: Previously saved manifest with old hashes.

        Returns:
            Tuple of (files_to_index, files_to_remove, stats) where
            *files_to_index* contains (abs_path, rel_path) pairs and
            *files_to_remove* contains relative paths of deleted files.
        """
        files_to_index: list[tuple[Path, str]] = []
        files_to_remove: list[str] = []
        stats = IndexStats()

        for rel_path, current_hash in current_hashes.items():
            if rel_path not in manifest.files:
                files_to_index.append((self.git_root / rel_path, rel_path))
                stats.files_added += 1
            elif manifest.files[rel_path] != current_hash:
                files_to_index.append((self.git_root / rel_path, rel_path))
                stats.files_updated += 1
            else:
                stats.files_unchanged += 1

        for rel_path in manifest.files:
            if rel_path not in current_hashes:
                files_to_remove.append(rel_path)
                stats.files_removed += 1

        return files_to_index, files_to_remove, stats

    def index(
        self: GitFileIndexer,
        console: Console | None = None,
        *,
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
        manifest = IndexManifest.load(self.manifest_path)

        if force or self._needs_full_reindex(manifest):
            self.store.clear()
            manifest = IndexManifest()

        current_hashes = self._compute_current_hashes()
        files_to_index, files_to_remove, stats = self._classify_file_changes(
            current_hashes, manifest,
        )

        for rel_path in files_to_remove:
            self.store.delete_by_file(rel_path)

        if files_to_index:
            self._index_files(
                files_to_index, console=console, progress_callback=progress_callback,
            )

        manifest.files = current_hashes
        manifest.model_name = self.embedder.model_name
        manifest.chunk_size = self.chunker.target_tokens
        manifest.save(self.manifest_path)

        stats.total_chunks = self.store.count()
        return stats

    def _index_single_file(self: GitFileIndexer, abs_path: Path, rel_path: str) -> None:
        """Index a single file: chunk, embed, and store.

        Args:
            abs_path: Absolute path to the source file.
            rel_path: Relative path used as the stored key.
        """
        self.store.delete_by_file(rel_path)
        chunks = self.chunker.chunk_file(abs_path)
        if not chunks:
            return
        for chunk in chunks:
            chunk.file_path = rel_path
        embeddings = self.embedder.embed([c.content for c in chunks])
        self.store.add_chunks(chunks, embeddings)

    def _index_files_with_progress(
        self: GitFileIndexer,
        files: list[tuple[Path, str]],
        console: Console,
        progress_callback: Callable[[str, int, int], None] | None,
    ) -> None:
        """Index files while rendering a Rich progress spinner.

        Args:
            files: List of (absolute_path, relative_path) tuples.
            console: Rich console used to display the spinner.
            progress_callback: Optional per-file progress callback.
        """
        total = len(files)
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Indexing {total} files...", total=total)
            for i, (abs_path, rel_path) in enumerate(files):
                self._index_single_file(abs_path, rel_path)
                progress.update(task, advance=1)
                if progress_callback:
                    progress_callback(rel_path, i + 1, total)

    def _index_files(
        self: GitFileIndexer,
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
        if console:
            self._index_files_with_progress(files, console, progress_callback)
            return

        for i, (abs_path, rel_path) in enumerate(files):
            self._index_single_file(abs_path, rel_path)
            if progress_callback:
                progress_callback(rel_path, i + 1, len(files))

    def get_stats(self: GitFileIndexer) -> IndexStats:
        """Get current index statistics.

        Returns:
            Current index statistics.
        """
        manifest = IndexManifest.load(self.manifest_path)
        return IndexStats(
            files_unchanged=len(manifest.files),
            total_chunks=self.store.count(),
        )
