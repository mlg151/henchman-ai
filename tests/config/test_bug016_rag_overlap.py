"""Tests for BUG-016: RAG chunk_overlap can exceed chunk_size.

RagSettings has no validator to ensure chunk_overlap < chunk_size.
When overlap exceeds size, text splitters produce empty or negative-span
chunks, silently corrupting the RAG index.
"""

from __future__ import annotations

import pytest

from henchman.config.schema import RagSettings


class TestBug016RagOverlapVsSize:
    """RagSettings should reject chunk_overlap >= chunk_size."""

    def test_overlap_greater_than_size_raises(self) -> None:
        """chunk_overlap > chunk_size should be rejected."""
        with pytest.raises(ValueError):
            RagSettings(chunk_size=100, chunk_overlap=200)

    def test_overlap_equal_to_size_raises(self) -> None:
        """chunk_overlap == chunk_size should be rejected (zero-length chunks)."""
        with pytest.raises(ValueError):
            RagSettings(chunk_size=100, chunk_overlap=100)

    def test_overlap_less_than_size_passes(self) -> None:
        """chunk_overlap < chunk_size should pass."""
        settings = RagSettings(chunk_size=200, chunk_overlap=50)
        assert settings.chunk_size == 200
        assert settings.chunk_overlap == 50

    def test_default_values_are_valid(self) -> None:
        """Default values (512/50) should pass."""
        settings = RagSettings()
        assert settings.chunk_overlap < settings.chunk_size

    def test_zero_overlap_passes(self) -> None:
        """chunk_overlap=0 is valid (no overlap)."""
        settings = RagSettings(chunk_size=100, chunk_overlap=0)
        assert settings.chunk_overlap == 0
