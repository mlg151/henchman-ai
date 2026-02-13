"""Tests for the embedding providers."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from henchman.rag.embedder import EmbeddingProvider, FastEmbedProvider


class TestEmbeddingProviderABC:
    """Tests for the EmbeddingProvider abstract base class."""

    def test_abc_cannot_instantiate(self) -> None:
        """Cannot instantiate ABC directly."""
        with pytest.raises(TypeError):
            EmbeddingProvider()  # type: ignore[abstract]


class TestFastEmbedProvider:
    """Tests for the FastEmbedProvider."""

    def test_model_name_property(self) -> None:
        """Model name property returns correct value."""
        with patch("fastembed.TextEmbedding") as mock_cls:
            mock_cls.return_value = MagicMock()
            provider = FastEmbedProvider(model_name="BAAI/bge-small-en-v1.5")
            assert provider.model_name == "BAAI/bge-small-en-v1.5"

    def test_dimensions_known_model(self) -> None:
        """Dimensions correct for known models."""
        with patch("fastembed.TextEmbedding") as mock_cls:
            mock_cls.return_value = MagicMock()
            provider = FastEmbedProvider(model_name="BAAI/bge-small-en-v1.5")
            assert provider.dimensions == 384

    def test_dimensions_base_model(self) -> None:
        """Dimensions correct for base model."""
        with patch("fastembed.TextEmbedding") as mock_cls:
            mock_cls.return_value = MagicMock()
            provider = FastEmbedProvider(model_name="BAAI/bge-base-en-v1.5")
            assert provider.dimensions == 768

    def test_dimensions_unknown_model_defaults(self) -> None:
        """Unknown model uses default dimensions."""
        with patch("fastembed.TextEmbedding") as mock_cls:
            mock_cls.return_value = MagicMock()
            provider = FastEmbedProvider(model_name="unknown/model")
            assert provider.dimensions == 384

    def test_embed_batch(self) -> None:
        """Embed returns embeddings for batch."""
        with patch("fastembed.TextEmbedding") as mock_cls:
            mock_model = MagicMock()
            mock_model.embed.return_value = iter(
                [
                    np.array([0.1, 0.2, 0.3]),
                    np.array([0.4, 0.5, 0.6]),
                ]
            )
            mock_cls.return_value = mock_model

            provider = FastEmbedProvider()
            embeddings = provider.embed(["text 1", "text 2"])

            assert len(embeddings) == 2
            assert embeddings[0] == [0.1, 0.2, 0.3]
            assert embeddings[1] == [0.4, 0.5, 0.6]

    def test_embed_query(self) -> None:
        """Embed query uses query_embed method."""
        with patch("fastembed.TextEmbedding") as mock_cls:
            mock_model = MagicMock()
            mock_model.query_embed.return_value = iter(
                [
                    np.array([0.7, 0.8, 0.9]),
                ]
            )
            mock_cls.return_value = mock_model

            provider = FastEmbedProvider()
            embedding = provider.embed_query("search query")

            assert embedding == [0.7, 0.8, 0.9]
            mock_model.query_embed.assert_called_once_with("search query")
