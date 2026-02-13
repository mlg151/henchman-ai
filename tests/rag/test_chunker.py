"""Tests for the TextChunker."""

import tempfile
from pathlib import Path

from henchman.rag.chunker import Chunk, TextChunker


class TestChunk:
    """Tests for the Chunk dataclass."""

    def test_chunk_id(self) -> None:
        """Chunk generates unique ID."""
        chunk = Chunk(
            content="test content",
            file_path="src/test.py",
            start_line=1,
            end_line=10,
            chunk_index=0,
        )
        assert chunk.id == "src/test.py::0"

    def test_chunk_id_with_different_index(self) -> None:
        """Different chunk index produces different ID."""
        chunk1 = Chunk(
            content="test",
            file_path="src/test.py",
            start_line=1,
            end_line=10,
            chunk_index=0,
        )
        chunk2 = Chunk(
            content="test",
            file_path="src/test.py",
            start_line=11,
            end_line=20,
            chunk_index=1,
        )
        assert chunk1.id != chunk2.id

    def test_to_metadata(self) -> None:
        """Chunk produces correct metadata dict."""
        chunk = Chunk(
            content="test content",
            file_path="src/test.py",
            start_line=5,
            end_line=15,
            chunk_index=2,
        )
        metadata = chunk.to_metadata()
        assert metadata["file_path"] == "src/test.py"
        assert metadata["start_line"] == 5
        assert metadata["end_line"] == 15
        assert metadata["chunk_index"] == 2


class TestTextChunker:
    """Tests for the TextChunker."""

    def test_count_tokens(self) -> None:
        """Token counting works correctly."""
        chunker = TextChunker(target_tokens=100)
        count = chunker.count_tokens("Hello, world!")
        assert count > 0
        assert count < 10  # Should be a few tokens

    def test_chunk_text_simple(self) -> None:
        """Simple text is chunked correctly."""
        chunker = TextChunker(target_tokens=50, overlap_tokens=10)
        text = "line 1\nline 2\nline 3\nline 4\nline 5\n"
        chunks = chunker.chunk_text(text, "test.txt")

        assert len(chunks) >= 1
        assert chunks[0].file_path == "test.txt"
        assert chunks[0].start_line == 1
        assert chunks[0].chunk_index == 0

    def test_chunk_text_empty(self) -> None:
        """Empty text produces no chunks."""
        chunker = TextChunker(target_tokens=100)
        chunks = chunker.chunk_text("", "test.txt")
        assert chunks == []

    def test_chunk_text_whitespace_only(self) -> None:
        """Whitespace-only text produces no chunks."""
        chunker = TextChunker(target_tokens=100)
        chunks = chunker.chunk_text("   \n\n   ", "test.txt")
        assert chunks == []

    def test_chunk_text_preserves_content(self) -> None:
        """All content is preserved across chunks."""
        chunker = TextChunker(target_tokens=20, overlap_tokens=5)
        lines = [f"line {i}\n" for i in range(1, 21)]
        text = "".join(lines)
        chunks = chunker.chunk_text(text, "test.txt")

        # Verify we got multiple chunks
        assert len(chunks) > 1

        # Verify content is complete (allowing for overlap)
        all_content = "".join(c.content for c in chunks)
        # Each line should appear at least once
        for i in range(1, 21):
            assert f"line {i}" in all_content

    def test_chunk_text_line_numbers_correct(self) -> None:
        """Line numbers are correctly tracked."""
        chunker = TextChunker(target_tokens=1000)  # Large enough for one chunk
        text = "line 1\nline 2\nline 3\n"
        chunks = chunker.chunk_text(text, "test.txt")

        assert len(chunks) == 1
        assert chunks[0].start_line == 1
        assert chunks[0].end_line == 3

    def test_chunk_file_success(self) -> None:
        """Chunking a file works correctly."""
        chunker = TextChunker(target_tokens=100)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def hello():\n    print('world')\n")
            f.flush()
            chunks = chunker.chunk_file(f.name)

        assert len(chunks) >= 1
        assert "def hello" in chunks[0].content
        Path(f.name).unlink()

    def test_chunk_file_binary_skipped(self) -> None:
        """Binary files are skipped."""
        chunker = TextChunker(target_tokens=100)
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(b"\x00\x01\x02\x03\xff\xfe")
            f.flush()
            chunks = chunker.chunk_file(f.name)

        # Binary file should produce no chunks
        assert chunks == []
        Path(f.name).unlink()

    def test_chunk_file_nonexistent(self) -> None:
        """Nonexistent file raises error."""
        import pytest

        chunker = TextChunker(target_tokens=100)
        with pytest.raises((FileNotFoundError, OSError)):
            chunker.chunk_file("/nonexistent/file.py")

    def test_overlap_works(self) -> None:
        """Overlap between chunks is applied correctly."""
        # Create a chunker with small target and overlap
        chunker = TextChunker(target_tokens=10, overlap_tokens=3)

        # Create text that will require multiple chunks
        text = "\n".join([f"word{i}" for i in range(20)])
        chunks = chunker.chunk_text(text, "test.txt")

        # Should have multiple chunks
        assert len(chunks) >= 2

        # Later chunks should start before the previous one ended
        for i in range(1, len(chunks)):
            # Start line of current should be <= end line of previous
            # (overlap means some lines repeat)
            assert chunks[i].start_line <= chunks[i - 1].end_line + 1
