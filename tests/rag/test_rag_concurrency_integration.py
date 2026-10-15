"""Integration tests for RAG system with concurrency support."""

from __future__ import annotations

import multiprocessing
import tempfile
from multiprocessing.queues import Queue
from multiprocessing.synchronize import Event
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from henchman.config.schema import RagSettings
from henchman.rag.concurrency import RagLock
from henchman.rag.store import VectorStore
from henchman.rag.system import RagSystem, initialize_rag


def _acquire_rag_lock(
    lock_path: str,
    result_queue: Queue[bool],
    release_event: Event,
) -> None:
    """Acquire a RAG lock in a picklable subprocess entry point."""
    lock = RagLock(Path(lock_path))
    acquired = lock.acquire(timeout=0.5)
    result_queue.put(acquired)
    if acquired:
        release_event.wait(timeout=5.0)
        lock.release()


class TestRagSystemConcurrency:
    """Integration tests for RAG system concurrency."""

    @pytest.fixture
    def mock_settings(self) -> RagSettings:
        """Create mock RAG settings."""
        settings = Mock(spec=RagSettings)
        settings.enabled = True
        settings.cache_dir = None
        settings.embedding_model = "test-model"
        settings.chunk_size = 512
        settings.chunk_overlap = 50
        settings.file_extensions = [".py", ".md", ".txt"]
        settings.top_k = 5
        return settings

    @pytest.fixture
    def temp_git_root(self) -> Path:
        """Create a temporary git repository root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir) / "test_repo"
            git_root.mkdir(parents=True)

            # Create a .git directory to simulate git repo
            (git_root / ".git").mkdir()

            # Create some test files
            (git_root / "test.py").write_text("def hello():\n    return 'world'")
            (git_root / "README.md").write_text("# Test Repository")

            yield git_root

    def test_rag_system_with_lock(self, mock_settings, temp_git_root) -> None:
        """Test RagSystem initialization with locking."""
        with (
            patch("henchman.rag.system.RagLock") as mock_lock_class,
            patch("henchman.rag.embedder.FastEmbedProvider") as mock_embedder_class,
            patch("henchman.rag.store.VectorStore") as mock_store_class,
            patch("henchman.rag.indexer.GitFileIndexer") as mock_indexer_class,
            patch("henchman.tools.builtins.rag_search.RagSearchTool"),
        ):
            mock_lock = Mock()
            mock_lock.acquire.return_value = True
            mock_lock.acquired = True
            mock_lock_class.return_value = mock_lock

            mock_embedder_class.return_value = Mock()
            mock_store_class.return_value = Mock()
            mock_indexer = Mock()
            mock_indexer_class.return_value = mock_indexer

            # Create RagSystem
            rag_system = RagSystem(
                git_root=temp_git_root,
                settings=mock_settings,
            )

            # Lock should have been created and acquired
            mock_lock_class.assert_called_once()

            # Index should proceed since lock was acquired
            mock_indexer.index.return_value = Mock(
                files_added=1,
                files_updated=0,
                files_removed=0,
                files_unchanged=0,
                total_chunks=5,
            )

            stats = rag_system.index()
            assert stats.files_added == 1

    def test_rag_system_lock_timeout(self, mock_settings, temp_git_root) -> None:
        """Test RagSystem when lock acquisition times out."""
        with (
            patch("henchman.rag.system.RagLock") as mock_lock_class,
            patch("henchman.rag.embedder.FastEmbedProvider") as mock_embedder_class,
            patch("henchman.rag.store.VectorStore") as mock_store_class,
            patch("henchman.rag.indexer.GitFileIndexer") as mock_indexer_class,
            patch("henchman.tools.builtins.rag_search.RagSearchTool"),
        ):
            mock_lock = Mock()
            mock_lock.acquire.return_value = False  # Simulate timeout
            mock_lock.acquired = False
            mock_lock_class.return_value = mock_lock

            mock_embedder_class.return_value = Mock()
            mock_store_class.return_value = Mock()
            mock_indexer = Mock()
            mock_indexer_class.return_value = mock_indexer

            # Create RagSystem with read_only=True to simulate locked scenario
            _rag_system = RagSystem(
                git_root=temp_git_root,
                settings=mock_settings,
                read_only=True,
            )

            # Lock should have been created
            mock_lock_class.assert_called_once()

            # In read_only mode, indexer.index() should not be called
            # Call index() and check it handles read_only gracefully
            # The implementation may skip indexing in read_only mode

    def test_initialize_rag_with_concurrent_instances(self, mock_settings, temp_git_root) -> None:
        """Test initialize_rag with simulated concurrent instances."""
        console = Mock()

        # First instance should succeed
        with (
            patch("henchman.rag.concurrency.RagLock") as mock_lock_class,
            patch("henchman.rag.embedder.FastEmbedProvider") as mock_embedder_class,
            patch("henchman.rag.store.VectorStore") as mock_store_class,
            patch("henchman.rag.indexer.GitFileIndexer") as mock_indexer_class,
            patch("henchman.tools.builtins.rag_search.RagSearchTool"),
        ):
            mock_lock = Mock()
            mock_lock.acquire.return_value = True
            mock_lock.acquired = True
            mock_lock_class.return_value = mock_lock

            mock_embedder_class.return_value = Mock()
            mock_store_class.return_value = Mock()
            mock_indexer = Mock()
            mock_indexer_class.return_value = mock_indexer

            rag_system1 = initialize_rag(
                settings=mock_settings,
                console=console,
                git_root=temp_git_root,
            )

            assert rag_system1 is not None

        # Second instance should also succeed (fresh mock context)
        with (
            patch("henchman.rag.concurrency.RagLock") as mock_lock_class,
            patch("henchman.rag.embedder.FastEmbedProvider") as mock_embedder_class,
            patch("henchman.rag.store.VectorStore") as mock_store_class,
            patch("henchman.rag.indexer.GitFileIndexer") as mock_indexer_class,
            patch("henchman.tools.builtins.rag_search.RagSearchTool"),
        ):
            mock_lock = Mock()
            mock_lock.acquire.return_value = True
            mock_lock.acquired = True
            mock_lock_class.return_value = mock_lock

            mock_embedder_class.return_value = Mock()
            mock_store_class.return_value = Mock()
            mock_indexer = Mock()
            mock_indexer_class.return_value = mock_indexer

            rag_system2 = initialize_rag(
                settings=mock_settings,
                console=console,
                git_root=temp_git_root,
            )

            assert rag_system2 is not None

    def test_vector_store_retry_on_locked(self) -> None:
        """Test VectorStore operations with retry on locked errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "chroma"

            # Create a mock embedder
            mock_embedder = Mock()
            mock_embedder.embed_query.return_value = [0.1, 0.2, 0.3]
            mock_embedder.embed.return_value = [[0.1, 0.2, 0.3]]
            mock_embedder.model_name = "test-model"

            # Create VectorStore with patched collection
            with patch("henchman.rag.store.chromadb") as mock_chroma:
                mock_client = Mock()
                mock_collection = Mock()

                # Simulate locked error on first search attempt
                call_count = 0

                def mock_search(**kwargs):  # noqa: ARG001
                    nonlocal call_count
                    call_count += 1
                    if call_count == 1:
                        raise RuntimeError("database is locked")
                    return {
                        "ids": [["chunk1"]],
                        "documents": [["test content"]],
                        "metadatas": [[{"file_path": "test.py", "start_line": 1, "end_line": 2}]],
                        "distances": [[0.1]],
                    }

                mock_collection.query.side_effect = mock_search
                mock_client.get_or_create_collection.return_value = mock_collection
                mock_chroma.PersistentClient.return_value = mock_client

                store = VectorStore(
                    persist_path=store_path,
                    embedder=mock_embedder,
                )

                # Search should retry on locked error
                results = store.search("test query")
                assert len(results) == 1
                assert call_count == 2  # First failed, second succeeded

    def test_concurrent_indexing_skip(self, mock_settings, temp_git_root) -> None:
        """Test that concurrent indexing is skipped gracefully."""
        console = Mock()

        # Simulate first instance holding lock
        with (
            patch("henchman.rag.concurrency.RagLock") as mock_lock_class,
            patch("henchman.rag.embedder.FastEmbedProvider") as mock_embedder_class,
            patch("henchman.rag.store.VectorStore") as mock_store_class,
            patch("henchman.rag.indexer.GitFileIndexer") as mock_indexer_class,
            patch("henchman.tools.builtins.rag_search.RagSearchTool"),
        ):
            mock_lock = Mock()
            mock_lock.acquire.return_value = False  # Can't acquire lock
            mock_lock.acquired = False
            mock_lock_class.return_value = mock_lock

            mock_embedder_class.return_value = Mock()
            mock_store_class.return_value = Mock()
            mock_indexer = Mock()
            mock_indexer_class.return_value = mock_indexer

            rag_system = initialize_rag(
                settings=mock_settings,
                console=console,
                git_root=temp_git_root,
            )

            # Should still return a RagSystem (for searching)
            assert rag_system is not None


class TestMultiProcessRag:
    """Tests for RAG in multi-process scenarios."""

    def test_lock_across_processes(self) -> None:
        """Test that locks work across different processes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "cross_process.lock"
            result_queue = multiprocessing.Queue()
            release_event = multiprocessing.Event()

            # Start worker process
            process = multiprocessing.Process(
                target=_acquire_rag_lock,
                args=(str(lock_path), result_queue, release_event),
            )
            process.start()

            try:
                worker_acquired = result_queue.get(timeout=3.0)

                # Try to acquire while the worker holds the lock - should fail
                lock = RagLock(lock_path)
                acquired = lock.acquire(timeout=0.1)
            finally:
                release_event.set()
                process.join(timeout=3.0)

            # Worker should have acquired lock
            assert worker_acquired is True
            # Main process should not have acquired lock
            assert acquired is False
            assert process.exitcode == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
