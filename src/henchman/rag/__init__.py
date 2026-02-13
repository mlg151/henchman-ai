"""RAG (Retrieval Augmented Generation) module for Henchman-AI.

This module provides semantic code search by indexing git-tracked files
into a local vector store using FastEmbed for embeddings and ChromaDB
for vector storage.
"""

from henchman.rag.chunker import Chunk, TextChunker
from henchman.rag.embedder import EmbeddingProvider, FastEmbedProvider
from henchman.rag.indexer import GitFileIndexer, IndexStats
from henchman.rag.repo_id import (
    compute_repository_id,
    get_rag_cache_dir,
    get_repository_index_dir,
    get_repository_manifest_path,
    migrate_old_index,
)
from henchman.rag.store import SearchResult, VectorStore
from henchman.rag.system import RagSystem, find_git_root, initialize_rag

__all__ = [
    "Chunk",
    "EmbeddingProvider",
    "FastEmbedProvider",
    "GitFileIndexer",
    "IndexStats",
    "RagSystem",
    "SearchResult",
    "TextChunker",
    "VectorStore",
    "compute_repository_id",
    "find_git_root",
    "get_rag_cache_dir",
    "get_repository_index_dir",
    "get_repository_manifest_path",
    "initialize_rag",
    "migrate_old_index",
]
