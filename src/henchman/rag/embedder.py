"""Embedding providers for RAG.

This module provides abstraction for embedding text into vectors,
with FastEmbed as the default local implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers.

    Embedding providers convert text into dense vector representations
    for similarity search in vector stores.
    """

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Get the dimensionality of the embeddings.

        Returns:
            Number of dimensions in the embedding vectors.
        """
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Get the model name.

        Returns:
            Name of the embedding model.
        """
        ...

    @abstractmethod
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed a batch of texts into vectors.

        Args:
            texts: Sequence of texts to embed.

        Returns:
            List of embedding vectors, one per input text.
        """
        ...

    def embed_query(self, query: str) -> list[float]:
        """Embed a single query string.

        This is a convenience method that wraps embed() for single queries.
        Some providers may optimize query embedding differently.

        Args:
            query: Query string to embed.

        Returns:
            Embedding vector for the query.
        """
        return self.embed([query])[0]


class FastEmbedProvider(EmbeddingProvider):
    """FastEmbed-based local embedding provider.

    Uses ONNX models for fast, local embedding generation without
    requiring external API calls or GPU.

    Attributes:
        model: The FastEmbed TextEmbedding model instance.
        _model_name: Name of the embedding model.
        _dimensions: Dimensionality of embeddings.
    """

    # Known model dimensions
    MODEL_DIMENSIONS: dict[str, int] = {
        "BAAI/bge-small-en-v1.5": 384,
        "BAAI/bge-base-en-v1.5": 768,
        "BAAI/bge-large-en-v1.5": 1024,
        "sentence-transformers/all-MiniLM-L6-v2": 384,
    }

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        """Initialize the FastEmbed provider.

        Args:
            model_name: Name of the FastEmbed model to use.
                Defaults to BAAI/bge-small-en-v1.5 (384 dimensions).
        """
        from fastembed import TextEmbedding

        self._model_name = model_name
        self.model = TextEmbedding(model_name=model_name)
        self._dimensions = self.MODEL_DIMENSIONS.get(model_name, 384)

    @property
    def dimensions(self) -> int:
        """Get the dimensionality of the embeddings.

        Returns:
            Number of dimensions in the embedding vectors.
        """
        return self._dimensions

    @property
    def model_name(self) -> str:
        """Get the model name.

        Returns:
            Name of the embedding model.
        """
        return self._model_name

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed a batch of texts into vectors.

        Args:
            texts: Sequence of texts to embed.

        Returns:
            List of embedding vectors, one per input text.
        """
        # FastEmbed returns a generator, convert to list
        embeddings = list(self.model.embed(list(texts)))
        return [emb.tolist() for emb in embeddings]

    def embed_query(self, query: str) -> list[float]:
        """Embed a single query string.

        FastEmbed has a dedicated query_embed method that may apply
        query-specific preprocessing.

        Args:
            query: Query string to embed.

        Returns:
            Embedding vector for the query.
        """
        # FastEmbed returns a generator, get first result
        result = list(self.model.query_embed(query))
        return list(result[0].tolist())
