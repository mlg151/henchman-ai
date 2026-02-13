"""Tests for the RagSystem and initialization helpers."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from henchman.config.schema import RagSettings
from henchman.rag.system import RagSystem, find_git_root, initialize_rag


class TestFindGitRoot:
    """Tests for the find_git_root function."""

    def test_finds_git_root(self) -> None:
        """Finds git root when .git exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir) / "repo"
            git_root.mkdir()
            (git_root / ".git").mkdir()

            subdir = git_root / "src" / "nested"
            subdir.mkdir(parents=True)

            result = find_git_root(subdir)
            assert result == git_root

    def test_returns_none_outside_git(self) -> None:
        """Returns None when not in a git repo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = find_git_root(Path(tmpdir))
            assert result is None

    def test_uses_cwd_as_default(self) -> None:
        """Uses current directory as default start."""
        # This test is hard to mock properly, just verify it doesn't crash
        result = find_git_root()
        # Could be None or a path depending on test environment
        assert result is None or isinstance(result, Path)


class TestRagSystem:
    """Tests for the RagSystem class."""

    @patch("henchman.tools.builtins.rag_search.RagSearchTool")
    @patch("henchman.rag.indexer.GitFileIndexer")
    @patch("henchman.rag.store.VectorStore")
    @patch("henchman.rag.chunker.TextChunker")
    @patch("fastembed.TextEmbedding")
    @patch("henchman.rag.repo_id.get_repository_manifest_path")
    @patch("henchman.rag.repo_id.get_repository_index_dir")
    @patch("henchman.rag.repo_id.get_rag_cache_dir")
    def test_init_creates_components(
        self,
        mock_get_cache_dir: MagicMock,
        mock_get_index_dir: MagicMock,
        mock_get_manifest_path: MagicMock,
        mock_embedder: MagicMock,
        mock_chunker: MagicMock,
        mock_store: MagicMock,
        mock_indexer: MagicMock,
        mock_tool: MagicMock,
    ) -> None:
        """Initialization creates all components."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            settings = RagSettings()

            # Mock cache and index directories
            cache_dir = Path(tmpdir) / "cache"
            index_dir = cache_dir / "repo_hash"
            manifest_path = index_dir / "manifest.json"

            mock_get_cache_dir.return_value = cache_dir
            mock_get_index_dir.return_value = index_dir
            mock_get_manifest_path.return_value = manifest_path

            system = RagSystem(git_root=git_root, settings=settings)

            mock_embedder.assert_called_once()
            mock_chunker.assert_called_once()
            mock_store.assert_called_once()
            mock_indexer.assert_called_once()
            mock_tool.assert_called_once()

            assert system.git_root == git_root
            assert system.settings == settings

    @patch("henchman.tools.builtins.rag_search.RagSearchTool")
    @patch("henchman.rag.indexer.GitFileIndexer")
    @patch("henchman.rag.store.VectorStore")
    @patch("henchman.rag.chunker.TextChunker")
    @patch("fastembed.TextEmbedding")
    @patch("henchman.rag.repo_id.get_repository_manifest_path")
    @patch("henchman.rag.repo_id.get_repository_index_dir")
    @patch("henchman.rag.repo_id.get_rag_cache_dir")
    def test_properties_return_components(
        self,
        mock_get_cache_dir: MagicMock,
        mock_get_index_dir: MagicMock,
        mock_get_manifest_path: MagicMock,
        mock_embedder: MagicMock,
        mock_chunker: MagicMock,
        mock_store: MagicMock,
        mock_indexer: MagicMock,
        mock_tool: MagicMock,
    ) -> None:
        """Properties return correct components."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            settings = RagSettings()

            # Mock cache and index directories
            cache_dir = Path(tmpdir) / "cache"
            index_dir = cache_dir / "repo_hash"
            manifest_path = index_dir / "manifest.json"

            mock_get_cache_dir.return_value = cache_dir
            mock_get_index_dir.return_value = index_dir
            mock_get_manifest_path.return_value = manifest_path

            system = RagSystem(git_root=git_root, settings=settings)

            assert system.store is not None
            assert system.indexer is not None
            assert system.search_tool is not None

    @patch("henchman.tools.builtins.rag_search.RagSearchTool")
    @patch("henchman.rag.indexer.GitFileIndexer")
    @patch("henchman.rag.store.VectorStore")
    @patch("henchman.rag.chunker.TextChunker")
    @patch("fastembed.TextEmbedding")
    @patch("henchman.rag.repo_id.get_repository_manifest_path")
    @patch("henchman.rag.repo_id.get_repository_index_dir")
    @patch("henchman.rag.repo_id.get_rag_cache_dir")
    def test_index_calls_indexer(
        self,
        mock_get_cache_dir: MagicMock,
        mock_get_index_dir: MagicMock,
        mock_get_manifest_path: MagicMock,
        mock_embedder: MagicMock,
        mock_chunker: MagicMock,
        mock_store: MagicMock,
        mock_indexer: MagicMock,
        mock_tool: MagicMock,
    ) -> None:
        """Index method calls indexer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            settings = RagSettings()

            # Mock cache and index directories
            cache_dir = Path(tmpdir) / "cache"
            index_dir = cache_dir / "repo_hash"
            manifest_path = index_dir / "manifest.json"

            mock_get_cache_dir.return_value = cache_dir
            mock_get_index_dir.return_value = index_dir
            mock_get_manifest_path.return_value = manifest_path

            mock_indexer_instance = MagicMock()
            mock_indexer.return_value = mock_indexer_instance

            system = RagSystem(git_root=git_root, settings=settings)
            system.index(force=True)

            mock_indexer_instance.index.assert_called_once()

    @patch("henchman.tools.builtins.rag_search.RagSearchTool")
    @patch("henchman.rag.indexer.GitFileIndexer")
    @patch("henchman.rag.store.VectorStore")
    @patch("henchman.rag.chunker.TextChunker")
    @patch("fastembed.TextEmbedding")
    @patch("henchman.rag.repo_id.get_repository_manifest_path")
    @patch("henchman.rag.repo_id.get_repository_index_dir")
    @patch("henchman.rag.repo_id.get_rag_cache_dir")
    def test_clear_clears_store_and_manifest(
        self,
        mock_get_cache_dir: MagicMock,
        mock_get_index_dir: MagicMock,
        mock_get_manifest_path: MagicMock,
        mock_embedder: MagicMock,
        mock_chunker: MagicMock,
        mock_store_cls: MagicMock,
        mock_indexer: MagicMock,
        mock_tool: MagicMock,
    ) -> None:
        """Clear method clears store and manifest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            settings = RagSettings()

            mock_store = MagicMock()
            mock_store_cls.return_value = mock_store

            # Mock cache and index directories to be in temp directory for testing
            cache_dir = Path(tmpdir) / "cache"
            index_dir = cache_dir / "repo_hash"
            manifest_path = index_dir / "manifest.json"

            mock_get_cache_dir.return_value = cache_dir
            mock_get_index_dir.return_value = index_dir
            mock_get_manifest_path.return_value = manifest_path

            # Create the manifest file
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text("{}")

            system = RagSystem(git_root=git_root, settings=settings)
            system.clear()

            mock_store.clear.assert_called_once()
            assert not manifest_path.exists()


class TestInitializeRag:
    """Tests for the initialize_rag function."""

    @patch("henchman.rag.system.RagSystem")
    @patch("henchman.rag.system.find_git_root")
    def test_returns_none_when_disabled(
        self,
        mock_find_git_root: MagicMock,
        mock_rag_system: MagicMock,
    ) -> None:
        """Returns None when RAG is disabled."""
        settings = RagSettings(enabled=False)
        result = initialize_rag(settings)
        assert result is None
        mock_find_git_root.assert_not_called()
        mock_rag_system.assert_not_called()

    @patch("henchman.rag.system.RagSystem")
    @patch("henchman.rag.system.find_git_root")
    def test_returns_none_outside_git(
        self,
        mock_find_git_root: MagicMock,
        mock_rag_system: MagicMock,
    ) -> None:
        """Returns None when not in a git repository."""
        settings = RagSettings(enabled=True)
        mock_find_git_root.return_value = None
        result = initialize_rag(settings)
        assert result is None
        mock_find_git_root.assert_called_once()
        mock_rag_system.assert_not_called()

    @patch("henchman.rag.system.RagSystem")
    @patch("henchman.rag.system.find_git_root")
    def test_initializes_system(
        self,
        mock_find_git_root: MagicMock,
        mock_rag_system: MagicMock,
    ) -> None:
        """Initializes system when in git repo and enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            settings = RagSettings(enabled=True)
            mock_find_git_root.return_value = git_root

            mock_instance = MagicMock()
            mock_rag_system.return_value = mock_instance

            result = initialize_rag(settings)
            assert result is mock_instance
            mock_find_git_root.assert_called_once()
            mock_rag_system.assert_called_once_with(git_root=git_root, settings=settings)
            mock_instance.index.assert_called_once()

    @patch("henchman.rag.system.RagSystem")
    @patch("henchman.rag.system.find_git_root")
    def test_handles_exception(
        self,
        mock_find_git_root: MagicMock,
        mock_rag_system: MagicMock,
    ) -> None:
        """Handles exceptions during initialization."""
        settings = RagSettings(enabled=True)
        mock_find_git_root.return_value = Path("/some/path")
        mock_rag_system.side_effect = Exception("Test error")

        result = initialize_rag(settings, console=None)
        assert result is None
        mock_find_git_root.assert_called_once()
        mock_rag_system.assert_called_once()
