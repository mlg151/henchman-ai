"""Tests for the GitFileIndexer."""

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from henchman.rag.indexer import GitFileIndexer, IndexManifest, IndexStats


class TestIndexManifest:
    """Tests for the IndexManifest dataclass."""

    def test_save_and_load(self) -> None:
        """Manifest can be saved and loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "manifest.json"

            manifest = IndexManifest(
                files={"file1.py": "hash1", "file2.py": "hash2"},
                model_name="test-model",
                chunk_size=256,
            )
            manifest.save(path)

            loaded = IndexManifest.load(path)
            assert loaded.files == manifest.files
            assert loaded.model_name == manifest.model_name
            assert loaded.chunk_size == manifest.chunk_size

    def test_load_nonexistent(self) -> None:
        """Loading nonexistent manifest returns empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nonexistent.json"
            loaded = IndexManifest.load(path)
            assert loaded.files == {}
            assert loaded.model_name == ""

    def test_load_invalid_json(self) -> None:
        """Loading invalid JSON returns empty manifest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "invalid.json"
            path.write_text("not valid json {{{")
            loaded = IndexManifest.load(path)
            assert loaded.files == {}

    def test_save_creates_parent_dirs(self) -> None:
        """Save creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "subdir" / "nested" / "manifest.json"
            manifest = IndexManifest()
            manifest.save(path)
            assert path.exists()


class TestIndexStats:
    """Tests for the IndexStats dataclass."""

    def test_defaults(self) -> None:
        """Default values are zeros."""
        stats = IndexStats()
        assert stats.files_added == 0
        assert stats.files_updated == 0
        assert stats.files_removed == 0
        assert stats.files_unchanged == 0
        assert stats.total_chunks == 0


class TestGitFileIndexer:
    """Tests for the GitFileIndexer."""

    def _create_mock_components(self) -> tuple[MagicMock, MagicMock, MagicMock]:
        """Create mock store, embedder, and chunker."""
        store = MagicMock()
        store.count.return_value = 0
        store.delete_by_file = MagicMock()
        store.add_chunks = MagicMock()
        store.clear = MagicMock()

        embedder = MagicMock()
        embedder.model_name = "test-model"
        embedder.embed.return_value = [[0.1] * 384]

        chunker = MagicMock()
        chunker.target_tokens = 512
        chunker.chunk_file.return_value = []

        return store, embedder, chunker

    def test_should_index_respects_extensions(self) -> None:
        """File extension filter is respected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            store, embedder, chunker = self._create_mock_components()

            indexer = GitFileIndexer(
                git_root=git_root,
                store=store,
                embedder=embedder,
                chunker=chunker,
                file_extensions=[".py", ".md"],
            )

            # Create test files
            py_file = git_root / "test.py"
            py_file.write_text("print('hello')")

            js_file = git_root / "test.js"
            js_file.write_text("console.log('hello')")

            assert indexer._should_index(py_file) is True
            assert indexer._should_index(js_file) is False

    def test_should_index_no_filter(self) -> None:
        """Without extension filter, all files pass."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            store, embedder, chunker = self._create_mock_components()

            indexer = GitFileIndexer(
                git_root=git_root,
                store=store,
                embedder=embedder,
                chunker=chunker,
                file_extensions=None,
            )

            any_file = git_root / "test.xyz"
            any_file.write_text("content")

            assert indexer._should_index(any_file) is True

    def test_should_index_rejects_directories(self) -> None:
        """Directories are not indexed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            store, embedder, chunker = self._create_mock_components()

            indexer = GitFileIndexer(
                git_root=git_root,
                store=store,
                embedder=embedder,
                chunker=chunker,
            )

            subdir = git_root / "subdir"
            subdir.mkdir()

            assert indexer._should_index(subdir) is False

    def test_compute_file_hash(self) -> None:
        """File hash is computed correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            store, embedder, chunker = self._create_mock_components()

            indexer = GitFileIndexer(
                git_root=git_root,
                store=store,
                embedder=embedder,
                chunker=chunker,
            )

            test_file = git_root / "test.txt"
            test_file.write_text("hello world")

            hash1 = indexer._compute_file_hash(test_file)
            assert len(hash1) == 64  # SHA256 hex

            # Same content = same hash
            hash2 = indexer._compute_file_hash(test_file)
            assert hash1 == hash2

            # Different content = different hash
            test_file.write_text("different content")
            hash3 = indexer._compute_file_hash(test_file)
            assert hash1 != hash3

    def test_compute_file_hash_nonexistent(self) -> None:
        """Nonexistent file returns empty hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            store, embedder, chunker = self._create_mock_components()

            indexer = GitFileIndexer(
                git_root=git_root,
                store=store,
                embedder=embedder,
                chunker=chunker,
            )

            hash_val = indexer._compute_file_hash(git_root / "nonexistent.txt")
            assert hash_val == ""

    def test_get_stats(self) -> None:
        """Get stats returns current statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            store, embedder, chunker = self._create_mock_components()
            store.count.return_value = 42

            # Create a manifest
            manifest_path = git_root / ".henchman" / "rag_manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "files": {"a.py": "hash1", "b.py": "hash2"},
                        "model_name": "test",
                        "chunk_size": 512,
                    }
                )
            )

            indexer = GitFileIndexer(
                git_root=git_root,
                store=store,
                embedder=embedder,
                chunker=chunker,
            )

            stats = indexer.get_stats()
            assert stats.files_unchanged == 2
            assert stats.total_chunks == 42

    @patch("subprocess.run")
    def test_get_tracked_files_git_error(self, mock_run: MagicMock) -> None:
        """Git error returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            store, embedder, chunker = self._create_mock_components()

            mock_run.side_effect = subprocess.CalledProcessError(1, "git")

            indexer = GitFileIndexer(
                git_root=git_root,
                store=store,
                embedder=embedder,
                chunker=chunker,
            )

            files = indexer.get_tracked_files()
            assert files == []


class TestGitFileIndexerIndex:
    """Tests for the index() method."""

    def _create_mock_components(self) -> tuple[MagicMock, MagicMock, MagicMock]:
        """Create mock store, embedder, and chunker."""
        store = MagicMock()
        store.count.return_value = 0
        store.delete_by_file = MagicMock()
        store.add_chunks = MagicMock()
        store.clear = MagicMock()

        embedder = MagicMock()
        embedder.model_name = "test-model"
        embedder.embed.return_value = [[0.1] * 384]

        chunker = MagicMock()
        chunker.target_tokens = 512
        chunker.chunk_file.return_value = []

        return store, embedder, chunker

    def test_index_new_files(self) -> None:
        """Index adds new files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            store, embedder, chunker = self._create_mock_components()

            # Create a git repo with a file
            subprocess.run(["git", "init"], cwd=git_root, check=True, capture_output=True)
            test_file = git_root / "test.py"
            test_file.write_text("print('hello')")
            subprocess.run(["git", "add", "."], cwd=git_root, check=True, capture_output=True)

            manifest_path = git_root / "manifest.json"

            indexer = GitFileIndexer(
                git_root=git_root,
                store=store,
                embedder=embedder,
                chunker=chunker,
                manifest_path=manifest_path,
            )

            stats = indexer.index()
            assert stats.files_added == 1

    def test_index_force_reindex(self) -> None:
        """Force reindex clears store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            store, embedder, chunker = self._create_mock_components()

            # Create a git repo
            subprocess.run(["git", "init"], cwd=git_root, check=True, capture_output=True)

            manifest_path = git_root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "files": {"old.py": "oldhash"},
                        "model_name": "test-model",
                        "chunk_size": 512,
                    }
                )
            )

            indexer = GitFileIndexer(
                git_root=git_root,
                store=store,
                embedder=embedder,
                chunker=chunker,
                manifest_path=manifest_path,
            )

            indexer.index(force=True)
            store.clear.assert_called_once()

    def test_index_with_progress_callback(self) -> None:
        """Index calls progress callback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            store, embedder, chunker = self._create_mock_components()

            # Mock a chunk being returned
            from henchman.rag.chunker import Chunk

            mock_chunk = Chunk(
                content="test content",
                file_path="test.py",
                start_line=1,
                end_line=10,
                chunk_index=0,
            )
            chunker.chunk_file.return_value = [mock_chunk]

            # Create a git repo with a file
            subprocess.run(["git", "init"], cwd=git_root, check=True, capture_output=True)
            test_file = git_root / "test.py"
            test_file.write_text("print('hello')")
            subprocess.run(["git", "add", "."], cwd=git_root, check=True, capture_output=True)

            manifest_path = git_root / "manifest.json"

            indexer = GitFileIndexer(
                git_root=git_root,
                store=store,
                embedder=embedder,
                chunker=chunker,
                manifest_path=manifest_path,
            )

            callback_calls = []

            def callback(path: str, current: int, total: int) -> None:
                callback_calls.append((path, current, total))

            indexer.index(progress_callback=callback)
            assert len(callback_calls) == 1
            assert callback_calls[0][0] == "test.py"

    def test_index_removes_deleted_files(self) -> None:
        """Index removes files no longer in git."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            store, embedder, chunker = self._create_mock_components()

            # Create a git repo
            subprocess.run(["git", "init"], cwd=git_root, check=True, capture_output=True)

            manifest_path = git_root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "files": {"deleted.py": "hash123"},
                        "model_name": "test-model",
                        "chunk_size": 512,
                    }
                )
            )

            indexer = GitFileIndexer(
                git_root=git_root,
                store=store,
                embedder=embedder,
                chunker=chunker,
                manifest_path=manifest_path,
            )

            stats = indexer.index()
            assert stats.files_removed == 1
            store.delete_by_file.assert_called_with("deleted.py")

    def test_index_updates_modified_files(self) -> None:
        """Index updates files with changed hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            store, embedder, chunker = self._create_mock_components()

            # Create a git repo with a file
            subprocess.run(["git", "init"], cwd=git_root, check=True, capture_output=True)
            test_file = git_root / "test.py"
            test_file.write_text("new content")
            subprocess.run(["git", "add", "."], cwd=git_root, check=True, capture_output=True)

            manifest_path = git_root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "files": {"test.py": "old_hash_value"},
                        "model_name": "test-model",
                        "chunk_size": 512,
                    }
                )
            )

            indexer = GitFileIndexer(
                git_root=git_root,
                store=store,
                embedder=embedder,
                chunker=chunker,
                manifest_path=manifest_path,
            )

            stats = indexer.index()
            assert stats.files_updated == 1

    def test_index_forces_on_model_change(self) -> None:
        """Index forces reindex when model changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            store, embedder, chunker = self._create_mock_components()
            embedder.model_name = "new-model"

            # Create a git repo
            subprocess.run(["git", "init"], cwd=git_root, check=True, capture_output=True)

            manifest_path = git_root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "files": {},
                        "model_name": "old-model",
                        "chunk_size": 512,
                    }
                )
            )

            indexer = GitFileIndexer(
                git_root=git_root,
                store=store,
                embedder=embedder,
                chunker=chunker,
                manifest_path=manifest_path,
            )

            indexer.index()
            store.clear.assert_called_once()

    def test_index_forces_on_chunk_size_change(self) -> None:
        """Index forces reindex when chunk size changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            store, embedder, chunker = self._create_mock_components()
            chunker.target_tokens = 1024  # Different from manifest

            # Create a git repo
            subprocess.run(["git", "init"], cwd=git_root, check=True, capture_output=True)

            manifest_path = git_root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "files": {},
                        "model_name": "test-model",
                        "chunk_size": 512,  # Different
                    }
                )
            )

            indexer = GitFileIndexer(
                git_root=git_root,
                store=store,
                embedder=embedder,
                chunker=chunker,
                manifest_path=manifest_path,
            )

            indexer.index()
            store.clear.assert_called_once()

    def test_should_index_special_files(self) -> None:
        """Special files like Makefile are indexed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            store, embedder, chunker = self._create_mock_components()

            indexer = GitFileIndexer(
                git_root=git_root,
                store=store,
                embedder=embedder,
                chunker=chunker,
                file_extensions=[".py", ".makefile", ".dockerfile"],
            )

            # Create special files
            makefile = git_root / "Makefile"
            makefile.write_text("all:\n\techo hello")

            dockerfile = git_root / "Dockerfile"
            dockerfile.write_text("FROM python:3.9")

            # These should match via special names
            assert indexer._should_index(makefile) is True
            assert indexer._should_index(dockerfile) is True
