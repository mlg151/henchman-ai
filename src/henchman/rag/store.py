"""Vector store for RAG.

This module provides a ChromaDB-based vector store for storing
and searching code embeddings.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import chromadb
from chromadb.config import Settings as ChromaSettings

from henchman.rag.concurrency import retry_on_locked

if TYPE_CHECKING:
    from henchman.rag.chunker import Chunk
    from henchman.rag.embedder import EmbeddingProvider

# Retry parameters for ChromaDB operations
_RETRY_MAX_RETRIES: int = 3
"""Default maximum retries for locked/concurrent ChromaDB operations."""

_RETRY_DELAY: float = 0.1
"""Default delay in seconds between retries for ChromaDB operations."""


@dataclass
class SearchResult:
    """Result from a similarity search.

    Attributes:
        content: The text content of the chunk.
        file_path: Path to the source file.
        start_line: Starting line number.
        end_line: Ending line number.
        score: Similarity score (0-1, higher is more similar).
        chunk_id: Unique identifier for the chunk.
    """

    content: str
    file_path: str
    start_line: int
    end_line: int
    score: float
    chunk_id: str

    def format_for_llm(self: SearchResult) -> str:
        """Format result for LLM consumption.

        Returns:
            Formatted string with file path, lines, and content.
        """
        return f"--- {self.file_path} (lines {self.start_line}-{self.end_line}) ---\n{self.content}"


class VectorStore:
    """ChromaDB-based vector store for code embeddings.

    Provides persistent storage of code chunk embeddings with
    similarity search capabilities.

    Attributes:
        persist_path: Path to persist the vector store.
        collection_name: Name of the ChromaDB collection.
        embedder: Embedding provider for queries.
    """

    def __init__(
        self: VectorStore,
        persist_path: Path | str,
        embedder: EmbeddingProvider,
        collection_name: str = "code_chunks",
        max_retries: int = 3,
    ) -> None:
        """Initialize the vector store.

        Args:
            persist_path: Path to persist the vector store.
            embedder: Embedding provider for query embedding.
            collection_name: Name of the ChromaDB collection.
            max_retries: Maximum retries for ChromaDB initialization.
        """
        import time

        self.persist_path = Path(persist_path)
        self.embedder = embedder
        self.collection_name = collection_name

        # Ensure persist directory exists
        self.persist_path.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB with persistence and retry logic
        last_error: Exception | None = None
        for attempt in range(max_retries):
            try:
                self.client = chromadb.PersistentClient(
                    path=str(self.persist_path),
                    settings=ChromaSettings(anonymized_telemetry=False),
                )

                # Get or create collection
                self.collection = self.client.get_or_create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"},  # Use cosine similarity
                )
                # Success - break out of retry loop
                break
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                # Retry on HNSW/compactor errors (concurrent access issues)
                if (
                    any(
                        phrase in error_str
                        for phrase in ["hnsw", "compactor", "segment", "backfill", "locked"]
                    )
                    and attempt < max_retries - 1
                ):
                    time.sleep(0.5 * (attempt + 1))  # Backoff
                    continue
                # Re-raise non-retryable errors immediately
                raise
        else:
            # All retries exhausted
            if last_error:
                raise last_error

    @retry_on_locked(max_retries=_RETRY_MAX_RETRIES, delay=_RETRY_DELAY)
    def add_chunks(self: VectorStore, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        """Add chunks with their embeddings to the store.

        Args:
            chunks: List of chunks to add.
            embeddings: Corresponding embeddings for each chunk.
        """
        if not chunks:
            return

        collection = self.collection
        collection.add(
            ids=[chunk.id for chunk in chunks],
            embeddings=embeddings,  # type: ignore[arg-type]
            documents=[chunk.content for chunk in chunks],
            metadatas=[
                {
                    "file_path": chunk.file_path,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "chunk_index": chunk.chunk_index,
                }
                for chunk in chunks
            ],
        )

    @retry_on_locked(max_retries=_RETRY_MAX_RETRIES, delay=_RETRY_DELAY)
    def search(self: VectorStore, query: str, top_k: int = 5) -> list[SearchResult]:
        """Search for similar chunks.

        Args:
            query: Query string to search for.
            top_k: Number of results to return.

        Returns:
            List of SearchResult objects, sorted by similarity.
        """
        # Embed the query
        query_embedding = self.embedder.embed_query(query)

        # Query the collection
        results = self.collection.query(
            query_embeddings=[query_embedding],  # type: ignore[arg-type]
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        # Convert to SearchResult objects
        search_results: list[SearchResult] = []
        if results["ids"] and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                # ChromaDB returns distances, convert to similarity score
                # For cosine distance, similarity = 1 - distance
                distance = results["distances"][0][i] if results["distances"] else 0
                score = 1.0 - float(distance)

                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                document = results["documents"][0][i] if results["documents"] else ""

                # Extract values with proper type handling
                start_line_val = metadata.get("start_line", 0)
                end_line_val = metadata.get("end_line", 0)

                search_results.append(
                    SearchResult(
                        content=str(document),
                        file_path=str(metadata.get("file_path", "")),
                        start_line=int(start_line_val)
                        if isinstance(start_line_val, (int, float, str))
                        else 0,
                        end_line=int(end_line_val)
                        if isinstance(end_line_val, (int, float, str))
                        else 0,
                        score=score,
                        chunk_id=chunk_id,
                    ),
                )

        return search_results

    @retry_on_locked(max_retries=_RETRY_MAX_RETRIES, delay=_RETRY_DELAY)
    def delete_by_file(self: VectorStore, file_path: str) -> None:
        """Delete all chunks from a specific file.

        Args:
            file_path: Path of the file whose chunks should be deleted.
        """
        # Query to find all chunks from this file
        results = self.collection.get(
            where={"file_path": file_path},
            include=["metadatas"],
        )

        if results["ids"]:
            self.collection.delete(ids=results["ids"])

    @retry_on_locked(max_retries=_RETRY_MAX_RETRIES, delay=_RETRY_DELAY)
    def delete_by_ids(self: VectorStore, chunk_ids: list[str]) -> None:
        """Delete chunks by their IDs.

        Args:
            chunk_ids: List of chunk IDs to delete.
        """
        if chunk_ids:
            self.collection.delete(ids=chunk_ids)

    @retry_on_locked(max_retries=_RETRY_MAX_RETRIES, delay=_RETRY_DELAY)
    def get_all_file_paths(self: VectorStore) -> set[str]:
        """Get all unique file paths in the store.

        Returns:
            Set of file paths that have chunks in the store.
        """
        results = self.collection.get(include=["metadatas"])
        file_paths: set[str] = set()
        if results["metadatas"]:
            for metadata in results["metadatas"]:
                if metadata and "file_path" in metadata:
                    file_paths.add(str(metadata["file_path"]))
        return file_paths

    @retry_on_locked(max_retries=_RETRY_MAX_RETRIES, delay=_RETRY_DELAY)
    def count(self: VectorStore) -> int:
        """Get the total number of chunks in the store.

        Returns:
            Number of chunks stored.
        """
        return self.collection.count()

    @retry_on_locked(max_retries=_RETRY_MAX_RETRIES, delay=_RETRY_DELAY)
    def clear(self: VectorStore) -> None:
        """Clear all chunks from the store."""
        # Delete and recreate the collection
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
