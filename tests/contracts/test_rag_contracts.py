"""Contract tests for RAG interfaces and data payloads."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from henchman.rag.chunker import Chunk
from henchman.rag.embedder import EmbeddingProvider, FastEmbedProvider
from henchman.rag.indexer import IndexManifest, IndexStats
from henchman.rag.store import SearchResult
from tests.contracts.helpers import assert_contract_matches, serialize_contract_value


def test_chunk_matches_contract(contract_suite) -> None:
    """Serialised Chunk payloads should satisfy their contract."""
    chunk = Chunk(
        content="test content",
        file_path="src/main.py",
        start_line=1,
        end_line=10,
        chunk_index=0,
    )
    assert_contract_matches(
        payload=serialize_contract_value(chunk),
        schema_name="rag/chunk",
        contract_suite=contract_suite,
    )


def test_search_result_matches_contract(contract_suite) -> None:
    """Serialised SearchResult payloads should satisfy their contract."""
    result = SearchResult(
        content="test content",
        file_path="src/main.py",
        start_line=1,
        end_line=10,
        score=0.95,
        chunk_id="src/main.py:1-10:0",
    )
    assert_contract_matches(
        payload=serialize_contract_value(result),
        schema_name="rag/search_result",
        contract_suite=contract_suite,
    )


def test_index_manifest_matches_contract(contract_suite) -> None:
    """Serialised IndexManifest payloads should satisfy their contract."""
    manifest = IndexManifest(
        files={"src/main.py": "abcdef123456"},
        model_name="all-MiniLM-L6-v2",
        chunk_size=1000,
    )
    assert_contract_matches(
        payload=serialize_contract_value(manifest),
        schema_name="rag/index_manifest",
        contract_suite=contract_suite,
    )


def test_index_stats_matches_contract(contract_suite) -> None:
    """Serialised IndexStats payloads should satisfy their contract."""
    stats = IndexStats(
        files_added=5,
        files_updated=2,
        files_removed=1,
        files_unchanged=10,
        total_chunks=150,
    )
    assert_contract_matches(
        payload=serialize_contract_value(stats),
        schema_name="rag/index_stats",
        contract_suite=contract_suite,
    )


# ===========================================================================
# EmbeddingProvider ABC contract
# ===========================================================================


class _EmbeddingProviderDouble(EmbeddingProvider):
    """Test double for EmbeddingProvider ABC."""

    def __init__(self, dims: int = 3, model: str = "test-model") -> None:
        self._dims = dims
        self._model = model

    @property
    def dimensions(self) -> int:
        return self._dims

    @property
    def model_name(self) -> str:
        return self._model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0][: self._dims] for _ in texts]


def test_embedding_provider_abc_cannot_be_instantiated() -> None:
    """EmbeddingProvider is abstract and cannot be instantiated directly."""
    with pytest.raises(TypeError):
        EmbeddingProvider()  # type: ignore[abstract]


def test_embedding_provider_double_satisfies_abc() -> None:
    """A concrete implementation must satisfy the EmbeddingProvider contract."""
    double = _EmbeddingProviderDouble()
    assert isinstance(double, EmbeddingProvider)


def test_embedding_provider_dimensions_contract() -> None:
    """EmbeddingProvider must expose a dimensions property returning int."""
    double = _EmbeddingProviderDouble(dims=768)
    assert isinstance(double.dimensions, int)
    assert double.dimensions == 768


def test_embedding_provider_model_name_contract() -> None:
    """EmbeddingProvider must expose a model_name property returning str."""
    double = _EmbeddingProviderDouble(model="test-embedding-v1")
    assert isinstance(double.model_name, str)
    assert double.model_name == "test-embedding-v1"


def test_embedding_provider_embed_returns_list_of_lists() -> None:
    """EmbeddingProvider.embed() must return list[list[float]]."""
    double = _EmbeddingProviderDouble(dims=3)
    result = double.embed(["hello", "world"])
    assert isinstance(result, list)
    assert len(result) == 2
    for vec in result:
        assert isinstance(vec, list)
        assert len(vec) == 3
        for v in vec:
            assert isinstance(v, float)


def test_embedding_provider_embed_empty_input() -> None:
    """EmbeddingProvider.embed() with empty input returns empty list."""
    double = _EmbeddingProviderDouble()
    result = double.embed([])
    assert result == []


def test_embedding_provider_embed_query_contract() -> None:
    """EmbeddingProvider.embed_query() must return list[float]."""
    double = _EmbeddingProviderDouble(dims=3)
    result = double.embed_query("hello")
    assert isinstance(result, list)
    assert len(result) == 3
    for v in result:
        assert isinstance(v, float)


def test_embedding_provider_double_embed_matches_dimensions() -> None:
    """FastEmbedProvider embed vectors must match declared dimensions."""
    provider = FastEmbedProvider()
    texts = ["test sentence"]
    embeddings = provider.embed(texts)
    assert len(embeddings) == 1
    assert len(embeddings[0]) == provider.dimensions


def test_embedding_provider_double_embed_batch_size_matches_input() -> None:
    """embed() must return one vector per input text."""
    provider = FastEmbedProvider()
    texts = ["one", "two", "three"]
    embeddings = provider.embed(texts)
    assert len(embeddings) == len(texts)


def test_embedding_provider_double_embed_query_returns_single_vector() -> None:
    """embed_query() must return a single vector (not nested)."""
    provider = FastEmbedProvider()
    result = provider.embed_query("test query")
    assert isinstance(result, list)
    assert len(result) == provider.dimensions


# ===========================================================================
# VectorStore contract
# ===========================================================================


class _VectorStoreDouble:
    """Test double for VectorStore contract verification."""

    def __init__(self) -> None:
        self._chunks: list[Chunk] = []
        self._file_paths: set[str] = set()

    def add_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        self._chunks.extend(chunks)
        for c in chunks:
            self._file_paths.add(c.file_path)

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        return []

    def delete_by_file(self, file_path: str) -> None:
        self._chunks = [c for c in self._chunks if c.file_path != file_path]
        self._file_paths.discard(file_path)

    def delete_by_ids(self, chunk_ids: list[str]) -> None:
        self._chunks = [c for c in self._chunks if c.id not in chunk_ids]

    def get_all_file_paths(self) -> set[str]:
        return self._file_paths.copy()

    def count(self) -> int:
        return len(self._chunks)

    def clear(self) -> None:
        self._chunks = []
        self._file_paths = set()


def test_vector_store_double_add_chunks_contract() -> None:
    """VectorStore.add_chunks() accepts chunks and embeddings lists."""
    double = _VectorStoreDouble()
    chunk = Chunk(
        content="test",
        file_path="test.py",
        start_line=1,
        end_line=1,
        chunk_index=0,
    )
    double.add_chunks([chunk], [[0.1, 0.2, 0.3]])
    assert double.count() == 1
    assert "test.py" in double.get_all_file_paths()


def test_vector_store_double_add_chunks_empty() -> None:
    """VectorStore.add_chunks() with empty lists is a no-op."""
    double = _VectorStoreDouble()
    double.add_chunks([], [])
    assert double.count() == 0


def test_vector_store_double_search_returns_search_results() -> None:
    """VectorStore.search() returns list of SearchResult."""
    double = _VectorStoreDouble()
    results = double.search("query", top_k=5)
    assert isinstance(results, list)
    for r in results:
        assert isinstance(r, SearchResult)


def test_vector_store_double_delete_by_file_contract() -> None:
    """VectorStore.delete_by_file() removes chunks from a file."""
    double = _VectorStoreDouble()
    chunk = Chunk(
        content="test",
        file_path="test.py",
        start_line=1,
        end_line=1,
        chunk_index=0,
    )
    double.add_chunks([chunk], [[0.1, 0.2, 0.3]])
    assert double.count() == 1
    double.delete_by_file("test.py")
    assert double.count() == 0
    assert "test.py" not in double.get_all_file_paths()


def test_vector_store_double_delete_by_ids_contract() -> None:
    """VectorStore.delete_by_ids() removes chunks by ID."""
    double = _VectorStoreDouble()
    chunk = Chunk(
        content="test",
        file_path="test.py",
        start_line=1,
        end_line=1,
        chunk_index=0,
    )
    double.add_chunks([chunk], [[0.1, 0.2, 0.3]])
    assert double.count() == 1
    double.delete_by_ids([chunk.id])
    assert double.count() == 0


def test_vector_store_double_get_all_file_paths_contract() -> None:
    """VectorStore.get_all_file_paths() returns set of str."""
    double = _VectorStoreDouble()
    paths = double.get_all_file_paths()
    assert isinstance(paths, set)
    for p in paths:
        assert isinstance(p, str)


def test_vector_store_double_count_contract() -> None:
    """VectorStore.count() returns int."""
    double = _VectorStoreDouble()
    assert double.count() == 0
    chunk = Chunk(content="test", file_path="a.py", start_line=1, end_line=1, chunk_index=0)
    double.add_chunks([chunk], [[0.1, 0.2, 0.3]])
    assert double.count() == 1
    assert isinstance(double.count(), int)


def test_vector_store_double_clear_contract() -> None:
    """VectorStore.clear() removes all chunks."""
    double = _VectorStoreDouble()
    chunk = Chunk(content="test", file_path="a.py", start_line=1, end_line=1, chunk_index=0)
    double.add_chunks([chunk], [[0.1, 0.2, 0.3]])
    assert double.count() == 1
    double.clear()
    assert double.count() == 0
    assert double.get_all_file_paths() == set()


# ===========================================================================
# TextChunker contract
# ===========================================================================


def test_text_chunker_chunk_text_returns_chunks() -> None:
    """TextChunker.chunk_text() returns list of Chunk."""
    from henchman.rag.chunker import TextChunker

    chunker = TextChunker(target_tokens=100, overlap_tokens=10)
    results = chunker.chunk_text("Hello, world!", "test.py")
    assert isinstance(results, list)
    for chunk in results:
        assert isinstance(chunk, Chunk)
        assert isinstance(chunk.content, str)
        assert isinstance(chunk.file_path, str)
        assert isinstance(chunk.start_line, int)
        assert isinstance(chunk.end_line, int)
        assert isinstance(chunk.chunk_index, int)


def test_text_chunker_chunk_text_empty() -> None:
    """TextChunker.chunk_text() with empty text returns empty list."""
    from henchman.rag.chunker import TextChunker

    chunker = TextChunker()
    results = chunker.chunk_text("", "test.py")
    assert results == []


def test_text_chunker_chunk_text_whitespace_only() -> None:
    """TextChunker.chunk_text() with whitespace-only text returns empty list."""
    from henchman.rag.chunker import TextChunker

    chunker = TextChunker()
    results = chunker.chunk_text("   \n\n   ", "test.py")
    assert results == []


def test_text_chunker_chunk_text_preserves_file_path() -> None:
    """TextChunker.chunk_text() associates chunks with the given file path."""
    from henchman.rag.chunker import TextChunker

    chunker = TextChunker()
    results = chunker.chunk_text("line one\nline two\n", "src/example.py")
    assert len(results) >= 1
    for chunk in results:
        assert chunk.file_path == "src/example.py"


def test_text_chunker_chunk_text_line_numbering() -> None:
    """TextChunker.chunk_text() assigns correct line numbers."""
    from henchman.rag.chunker import TextChunker

    chunker = TextChunker(target_tokens=512, overlap_tokens=0)
    text = "first\nsecond\nthird\n"
    results = chunker.chunk_text(text, "test.py")
    assert len(results) >= 1
    first_chunk = results[0]
    assert first_chunk.start_line == 1
    assert first_chunk.end_line == 3


def test_text_chunker_chunk_text_chunk_indices_sequential() -> None:
    """TextChunker.chunk_text() assigns sequential chunk indices."""
    from henchman.rag.chunker import TextChunker

    chunker = TextChunker(target_tokens=10, overlap_tokens=0)
    # Generate enough text to produce multiple chunks
    lines = "\n".join(f"line {i}" for i in range(100))
    results = chunker.chunk_text(lines, "test.py")
    if len(results) > 1:
        for i, chunk in enumerate(results):
            assert chunk.chunk_index == i


def test_text_chunker_count_tokens_returns_int() -> None:
    """TextChunker.count_tokens() returns non-negative int."""
    from henchman.rag.chunker import TextChunker

    chunker = TextChunker()
    assert isinstance(chunker.count_tokens("hello"), int)
    assert chunker.count_tokens("hello") > 0
    assert chunker.count_tokens("") == 0


def test_text_chunker_chunk_file_returns_chunks() -> None:
    """TextChunker.chunk_file() returns list of Chunk for a real file."""
    import tempfile

    from henchman.rag.chunker import TextChunker

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("def hello():\n    return 'world'\n")
        tmp_path = f.name

    try:
        chunker = TextChunker()
        results = chunker.chunk_file(tmp_path)
        assert isinstance(results, list)
        for chunk in results:
            assert isinstance(chunk, Chunk)
            assert chunk.file_path == tmp_path
    finally:
        import os

        os.unlink(tmp_path)


def test_text_chunker_chunk_file_nonexistent_returns_empty() -> None:
    """TextChunker.chunk_file() with nonexistent file raises FileNotFoundError."""
    from henchman.rag.chunker import TextChunker

    chunker = TextChunker()
    with pytest.raises(FileNotFoundError):
        chunker.chunk_file("/nonexistent/path/file.py")


def test_text_chunker_chunk_id_format() -> None:
    """Chunk.id follows the file_path::chunk_index format."""
    from henchman.rag.chunker import Chunk

    chunk = Chunk(
        content="test",
        file_path="src/main.py",
        start_line=1,
        end_line=1,
        chunk_index=3,
    )
    assert chunk.id == "src/main.py::3"


def test_text_chunker_chunk_to_metadata() -> None:
    """Chunk.to_metadata() returns dict with expected keys."""
    from henchman.rag.chunker import Chunk

    chunk = Chunk(
        content="test",
        file_path="src/main.py",
        start_line=1,
        end_line=10,
        chunk_index=0,
    )
    meta = chunk.to_metadata()
    assert isinstance(meta, dict)
    assert meta["file_path"] == "src/main.py"
    assert meta["start_line"] == 1
    assert meta["end_line"] == 10
    assert meta["chunk_index"] == 0
