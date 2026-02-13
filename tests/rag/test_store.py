"""Tests for the VectorStore."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from henchman.rag.chunker import Chunk
from henchman.rag.store import SearchResult, VectorStore


class TestSearchResult:
    """Tests for the SearchResult dataclass."""

    def test_format_for_llm(self) -> None:
        """Format for LLM produces readable output."""
        result = SearchResult(
            content="def hello():\n    print('world')\n",
            file_path="src/greet.py",
            start_line=10,
            end_line=12,
            score=0.85,
            chunk_id="src/greet.py::0",
        )
        formatted = result.format_for_llm()

        assert "src/greet.py" in formatted
        assert "10-12" in formatted
        assert "def hello" in formatted


class TestVectorStore:
    """Tests for the VectorStore."""

    def _create_mock_embedder(self) -> MagicMock:
        """Create a mock embedder."""
        mock = MagicMock()
        mock.embed_query.return_value = [0.1] * 384
        return mock

    def test_init_creates_directory(self) -> None:
        """Init creates persist directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "subdir" / "index"
            embedder = self._create_mock_embedder()
            _ = VectorStore(persist_path=path, embedder=embedder)
            assert path.exists()

    def test_count_empty(self) -> None:
        """Empty store has count 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            embedder = self._create_mock_embedder()
            store = VectorStore(persist_path=tmpdir, embedder=embedder)
            assert store.count() == 0

    def test_add_chunks(self) -> None:
        """Adding chunks increases count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            embedder = self._create_mock_embedder()
            store = VectorStore(persist_path=tmpdir, embedder=embedder)

            chunks = [
                Chunk(
                    content="test content 1",
                    file_path="test.py",
                    start_line=1,
                    end_line=5,
                    chunk_index=0,
                ),
                Chunk(
                    content="test content 2",
                    file_path="test.py",
                    start_line=6,
                    end_line=10,
                    chunk_index=1,
                ),
            ]
            embeddings = [[0.1] * 384, [0.2] * 384]

            store.add_chunks(chunks, embeddings)
            assert store.count() == 2

    def test_add_empty_chunks(self) -> None:
        """Adding empty list does nothing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            embedder = self._create_mock_embedder()
            store = VectorStore(persist_path=tmpdir, embedder=embedder)
            store.add_chunks([], [])
            assert store.count() == 0

    def test_search_empty_store(self) -> None:
        """Search on empty store returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            embedder = self._create_mock_embedder()
            store = VectorStore(persist_path=tmpdir, embedder=embedder)
            results = store.search("query", top_k=5)
            assert results == []

    def test_search_returns_results(self) -> None:
        """Search returns matching results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            embedder = self._create_mock_embedder()
            store = VectorStore(persist_path=tmpdir, embedder=embedder)

            chunks = [
                Chunk(
                    content="authentication middleware",
                    file_path="auth.py",
                    start_line=1,
                    end_line=10,
                    chunk_index=0,
                ),
            ]
            embeddings = [[0.1] * 384]
            store.add_chunks(chunks, embeddings)

            results = store.search("auth", top_k=5)
            assert len(results) == 1
            assert results[0].file_path == "auth.py"
            assert "authentication" in results[0].content

    def test_delete_by_file(self) -> None:
        """Delete by file removes correct chunks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            embedder = self._create_mock_embedder()
            store = VectorStore(persist_path=tmpdir, embedder=embedder)

            chunks = [
                Chunk(
                    content="content 1",
                    file_path="file1.py",
                    start_line=1,
                    end_line=5,
                    chunk_index=0,
                ),
                Chunk(
                    content="content 2",
                    file_path="file2.py",
                    start_line=1,
                    end_line=5,
                    chunk_index=0,
                ),
            ]
            embeddings = [[0.1] * 384, [0.2] * 384]
            store.add_chunks(chunks, embeddings)

            assert store.count() == 2
            store.delete_by_file("file1.py")
            assert store.count() == 1

    def test_delete_by_ids(self) -> None:
        """Delete by IDs removes correct chunks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            embedder = self._create_mock_embedder()
            store = VectorStore(persist_path=tmpdir, embedder=embedder)

            chunks = [
                Chunk(
                    content="content 1",
                    file_path="file.py",
                    start_line=1,
                    end_line=5,
                    chunk_index=0,
                ),
                Chunk(
                    content="content 2",
                    file_path="file.py",
                    start_line=6,
                    end_line=10,
                    chunk_index=1,
                ),
            ]
            embeddings = [[0.1] * 384, [0.2] * 384]
            store.add_chunks(chunks, embeddings)

            assert store.count() == 2
            store.delete_by_ids(["file.py::0"])
            assert store.count() == 1

    def test_get_all_file_paths(self) -> None:
        """Get all file paths returns unique paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            embedder = self._create_mock_embedder()
            store = VectorStore(persist_path=tmpdir, embedder=embedder)

            chunks = [
                Chunk(
                    content="content 1",
                    file_path="file1.py",
                    start_line=1,
                    end_line=5,
                    chunk_index=0,
                ),
                Chunk(
                    content="content 2",
                    file_path="file1.py",
                    start_line=6,
                    end_line=10,
                    chunk_index=1,
                ),
                Chunk(
                    content="content 3",
                    file_path="file2.py",
                    start_line=1,
                    end_line=5,
                    chunk_index=0,
                ),
            ]
            embeddings = [[0.1] * 384, [0.2] * 384, [0.3] * 384]
            store.add_chunks(chunks, embeddings)

            paths = store.get_all_file_paths()
            assert paths == {"file1.py", "file2.py"}

    def test_clear(self) -> None:
        """Clear removes all chunks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            embedder = self._create_mock_embedder()
            store = VectorStore(persist_path=tmpdir, embedder=embedder)

            chunks = [
                Chunk(
                    content="content",
                    file_path="file.py",
                    start_line=1,
                    end_line=5,
                    chunk_index=0,
                ),
            ]
            embeddings = [[0.1] * 384]
            store.add_chunks(chunks, embeddings)

            assert store.count() == 1
            store.clear()
            assert store.count() == 0
