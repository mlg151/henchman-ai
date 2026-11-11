"""Git file indexer for RAG.

This module provides incremental indexing of git-tracked files
with hash-based change detection.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from contextlib import suppress
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from rich.progress import Progress, SpinnerColumn, TextColumn

from henchman.rag.evidence import (
    EVIDENCE_VERSION,
    EvidenceUnavailable,
    WorkspaceBinding,
    read_source,
    repository_git_environment,
)
from henchman.rag.repo_id import get_repository_manifest_path

# Default chunk size used when not specified in manifest
DEFAULT_CHUNK_SIZE: int = 512
MAX_MANIFEST_BYTES = 4 * 1024 * 1024

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
    evidence_version: int = 0
    repository_id: str | None = None
    collection_id: str | None = None
    generation_id: str | None = None

    def save(self: IndexManifest, path: Path) -> None:
        """Save manifest to disk.

        Args:
            path: Path to save the manifest.

        Returns:
            None
        """
        text = json.dumps(
            {
                "files": self.files,
                "model_name": self.model_name,
                "chunk_size": self.chunk_size,
                "evidence_version": self.evidence_version,
                "repository_id": self.repository_id,
                "collection_id": self.collection_id,
                "generation_id": self.generation_id,
            },
        )
        if len(text.encode("utf-8")) > MAX_MANIFEST_BYTES:
            raise ValueError("RAG manifest exceeds byte budget")
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except BaseException:
            with suppress(OSError):
                os.unlink(temporary)
            raise

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
            with path.open("rb") as stream:
                raw = stream.read(MAX_MANIFEST_BYTES + 1)
            if len(raw) > MAX_MANIFEST_BYTES:
                raise ValueError("RAG manifest exceeds byte budget")
            data = json.loads(raw)
            if not isinstance(data, dict) or not isinstance(data.get("files", {}), dict):
                raise ValueError("Invalid RAG manifest")
            if type(data.get("evidence_version", 0)) is not int or data.get(
                "evidence_version", 0
            ) not in (0, EVIDENCE_VERSION):
                raise ValueError("Unsupported RAG manifest version")
            for name in ("collection_id", "generation_id"):
                value = data.get(name)
                if value is not None:
                    try:
                        valid = isinstance(value, str) and str(UUID(value)) == value
                    except ValueError:
                        valid = False
                    if not valid:
                        raise ValueError("Invalid RAG manifest generation") from None
            return _manifest_from_dict(cls, data)
        except (UnicodeError, json.JSONDecodeError, KeyError) as exc:
            raise ValueError("Invalid RAG manifest") from exc


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
        evidence_version=data.get("evidence_version", 0),  # type: ignore[arg-type]
        repository_id=data.get("repository_id"),  # type: ignore[arg-type]
        collection_id=data.get("collection_id"),  # type: ignore[arg-type]
        generation_id=data.get("generation_id"),  # type: ignore[arg-type]
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
                If None, uses the canonical versioned worktree cache manifest.
        """
        self.git_root = git_root
        self.store = store
        self.embedder = embedder
        self.chunker = chunker
        self.file_extensions = set(file_extensions) if file_extensions else None
        self._binding = WorkspaceBinding.bind(git_root)
        self._indexed_hashes: dict[str, str] = {}

        # Manifest path
        if manifest_path is None:
            self.manifest_path = get_repository_manifest_path(git_root)
        else:
            self.manifest_path = manifest_path

    def get_tracked_files(self: GitFileIndexer) -> list[Path]:
        """Get list of git-tracked files.

        Returns:
            List of paths to tracked files.
        """
        try:
            result = subprocess.run(
                ["git", "ls-files", "-z"],
                cwd=self.git_root,
                env=repository_git_environment(),
                capture_output=True,
                text=True,
                check=True,
            )
            files = []
            for line in result.stdout.split("\0"):
                if not line:
                    continue
                file_path = self.git_root / line
                if self._should_index(file_path):
                    files.append(file_path)
        except subprocess.CalledProcessError as exc:
            raise ValueError("Cannot enumerate repository tracked files") from exc
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
            bool(manifest.model_name) and manifest.model_name != self.embedder.model_name
        )
        chunk_size_changed = manifest.chunk_size != self.chunker.target_tokens
        provenance_changed = (
            manifest.evidence_version != EVIDENCE_VERSION
            or manifest.repository_id != self._binding.repository_id
            or manifest.generation_id is None
            or manifest.collection_id != self.store.collection_id
        )
        return model_changed or chunk_size_changed or provenance_changed

    def _compute_current_hashes(self: GitFileIndexer) -> dict[str, str]:
        """Return a mapping of repo-relative path to SHA-256 hash for tracked files.

        Returns:
            Dict mapping relative file paths to their content hashes.
        """
        workspace = self._binding.snapshot()
        hashes = {}
        for path in self.get_tracked_files():
            relative = path.relative_to(self.git_root).as_posix()
            hashes[relative] = read_source(workspace, relative).sha256
        workspace.check()
        return hashes

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
        workspace = self._binding.snapshot()
        embedder = self.embedder
        model_name = embedder.model_name
        chunk_size = self.chunker.target_tokens
        manifest = IndexManifest.load(self.manifest_path)
        self._indexed_hashes = {}

        rebuild = force or self._needs_full_reindex(manifest)
        if rebuild:
            manifest = IndexManifest()

        current_hashes = self._compute_current_hashes()
        files_to_index, files_to_remove, stats = self._classify_file_changes(
            current_hashes,
            manifest,
        )

        # Publish unavailability before any store effect. A fresh attempt token
        # also prevents queries spanning an incomplete -> ready ABA cycle from
        # publishing observations made while the backing collection was partial.
        manifest.collection_id = None
        manifest.generation_id = str(uuid4())
        manifest.save(self.manifest_path)
        if rebuild:
            self.store.clear()
        collection_id = self.store.collection_id

        for rel_path in files_to_remove:
            self.store.delete_by_file(rel_path)

        if files_to_index:
            self._index_files(
                files_to_index,
                console=console,
                progress_callback=progress_callback,
            )

        workspace.check()
        current_hashes.update(self._indexed_hashes)
        manifest.files = current_hashes
        if (
            self.embedder is not embedder
            or embedder.model_name != model_name
            or self.chunker.target_tokens != chunk_size
        ):
            raise EvidenceUnavailable("index_embedding_profile_changed_reindex_required")
        manifest.model_name = model_name
        manifest.chunk_size = chunk_size
        manifest.evidence_version = EVIDENCE_VERSION
        manifest.repository_id = self._binding.repository_id
        if self.store.collection_id != collection_id:
            raise EvidenceUnavailable("index_collection_changed_reindex_required")
        manifest.collection_id = collection_id
        manifest.save(self.manifest_path)

        stats.total_chunks = self.store.count()
        return stats

    def _index_single_file(self: GitFileIndexer, abs_path: Path, rel_path: str) -> None:
        """Index a single file: chunk, embed, and store.

        Args:
            abs_path: Absolute path to the source file.
            rel_path: Relative path used as the stored key.
        """
        workspace = self._binding.snapshot()
        source = read_source(workspace, rel_path)
        chunks = self.chunker.chunk_text(source.text, rel_path)
        for chunk in chunks:
            chunk.file_path = rel_path
            chunk.source_sha256 = source.sha256
            chunk.repository_id = self._binding.repository_id
            chunk.indexed_revision = workspace.revision
            chunk.evidence_version = EVIDENCE_VERSION
        embeddings = self.embedder.embed([c.content for c in chunks]) if chunks else []
        source.check(workspace)
        workspace.check()
        self.store.delete_by_file(rel_path)
        if chunks:
            self.store.add_chunks(chunks, embeddings)
        self._indexed_hashes[rel_path] = source.sha256

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
