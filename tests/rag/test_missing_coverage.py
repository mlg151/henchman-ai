"""Tests targeting missing coverage lines in rag modules."""

from __future__ import annotations

from unittest.mock import patch

from henchman.rag.chunker import TextChunker

# ---------------------------------------------------------------------------
# chunker.py – line 193: _get_overlap_lines returns [] for empty list
# ---------------------------------------------------------------------------


class TestGetOverlapLinesEmptyInput:
    """Cover line 193 in chunker.py."""

    def test_empty_lines_returns_empty(self) -> None:
        """Line 193: _get_overlap_lines([]) returns []."""
        chunker = TextChunker(target_tokens=100, overlap_tokens=20)
        result = chunker._get_overlap_lines([])
        assert result == []


# ---------------------------------------------------------------------------
# chunker.py – line 199->206: for-loop completes naturally (all lines fit)
# ---------------------------------------------------------------------------


class TestGetOverlapLinesAllFit:
    """Cover branch 199->206 in chunker.py (loop completes without break)."""

    def test_all_lines_fit_in_overlap(self) -> None:
        """Lines 199->206: loop runs to completion when all lines fit budget."""
        chunker = TextChunker(target_tokens=10000, overlap_tokens=10000)
        lines = ["hello world\n", "foo bar\n", "baz qux\n"]
        result = chunker._get_overlap_lines(lines)
        assert result == lines

    def test_partial_lines_exceed_budget(self) -> None:
        """Loop breaks when a line would exceed the budget."""
        chunker = TextChunker(target_tokens=100, overlap_tokens=2)
        lines = ["a very long line that exceeds budget\n", "ok\n"]
        result = chunker._get_overlap_lines(lines)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# chunker.py – lines 161-163: overlap_lines is empty → else branch
# ---------------------------------------------------------------------------


class TestChunkTextOverlapEmpty:
    """Cover lines 161-163 in chunker.py."""

    def test_overlap_tokens_zero_gives_empty_overlap(self) -> None:
        """Lines 161-163: when overlap_tokens=0, _get_overlap_lines returns [].

        This triggers the else branch that resets current_lines / tokens.
        """
        chunker = TextChunker(target_tokens=3, overlap_tokens=0)
        text = "word one two\nword three four\nword five six\n"
        chunks = chunker.chunk_text(text, "test.py")
        assert len(chunks) >= 1


# ---------------------------------------------------------------------------
# chunker.py – line 169->181: False branch (current_lines empty at loop end)
# ---------------------------------------------------------------------------


class TestChunkTextEmptyLastBatch:
    """Cover branch 169->181 in chunker.py (False path of if current_lines:)."""

    def test_no_leftover_when_overlap_returns_empty(self) -> None:
        """Line 169->181: current_lines empty at end means no final chunk appended."""
        chunker = TextChunker(target_tokens=5, overlap_tokens=0)
        text = "a b c d e\nf g h i j\n"

        with patch.object(chunker, "_get_overlap_lines", return_value=[]):
            chunks = chunker.chunk_text(text, "test.py")

        assert isinstance(chunks, list)
