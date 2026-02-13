"""Tests for repository identification utilities."""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from henchman.rag.repo_id import (
    compute_repository_id,
    get_git_remote_url,
    get_git_revision,
    get_rag_cache_dir,
    get_repository_index_dir,
    get_repository_manifest_path,
    migrate_old_index,
)


class TestGetGitRemoteUrl:
    """Tests for get_git_remote_url function."""

    def test_returns_remote_url(self) -> None:
        """Returns remote URL for a repository with origin."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            subprocess.run(["git", "init"], cwd=git_root, check=True, capture_output=True)
            subprocess.run(
                ["git", "remote", "add", "origin", "https://github.com/test/repo.git"],
                cwd=git_root,
                check=True,
                capture_output=True,
            )

            result = get_git_remote_url(git_root)
            assert result == "https://github.com/test/repo.git"

    def test_returns_none_without_remote(self) -> None:
        """Returns None when no remote is configured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            subprocess.run(["git", "init"], cwd=git_root, check=True, capture_output=True)

            result = get_git_remote_url(git_root)
            assert result is None

    def test_returns_none_for_non_git_dir(self) -> None:
        """Returns None for non-git directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = get_git_remote_url(Path(tmpdir))
            assert result is None


class TestGetGitRevision:
    """Tests for get_git_revision function."""

    def test_returns_revision(self) -> None:
        """Returns commit hash for a repository with commits."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            subprocess.run(["git", "init"], cwd=git_root, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=git_root,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=git_root,
                check=True,
                capture_output=True,
            )
            (git_root / "test.txt").write_text("test")
            subprocess.run(["git", "add", "."], cwd=git_root, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial"],
                cwd=git_root,
                check=True,
                capture_output=True,
            )

            result = get_git_revision(git_root)
            assert result is not None
            assert len(result) == 12  # Short hash

    def test_returns_none_without_commits(self) -> None:
        """Returns None for repository without commits."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            subprocess.run(["git", "init"], cwd=git_root, check=True, capture_output=True)

            result = get_git_revision(git_root)
            assert result is None


class TestComputeRepositoryId:
    """Tests for compute_repository_id function."""

    def test_uses_remote_url_when_available(self) -> None:
        """Uses remote URL as base when available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            subprocess.run(["git", "init"], cwd=git_root, check=True, capture_output=True)
            subprocess.run(
                ["git", "remote", "add", "origin", "https://github.com/test/repo.git"],
                cwd=git_root,
                check=True,
                capture_output=True,
            )

            result = compute_repository_id(git_root)
            assert len(result) == 16

    def test_uses_path_without_remote(self) -> None:
        """Uses path as base when no remote."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            subprocess.run(["git", "init"], cwd=git_root, check=True, capture_output=True)

            result = compute_repository_id(git_root)
            assert len(result) == 16

    def test_consistent_ids(self) -> None:
        """Same repository gets same ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            subprocess.run(["git", "init"], cwd=git_root, check=True, capture_output=True)
            subprocess.run(
                ["git", "remote", "add", "origin", "https://github.com/test/repo.git"],
                cwd=git_root,
                check=True,
                capture_output=True,
            )

            result1 = compute_repository_id(git_root)
            result2 = compute_repository_id(git_root)
            assert result1 == result2


class TestGetRagCacheDir:
    """Tests for get_rag_cache_dir function."""

    def test_default_cache_dir(self) -> None:
        """Uses default home directory location."""
        result = get_rag_cache_dir()
        assert result == Path.home() / ".henchman" / "rag_indices"

    def test_custom_cache_dir(self) -> None:
        """Uses custom cache directory when provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir) / "custom"
            result = get_rag_cache_dir(custom_dir)
            assert result == custom_dir
            assert custom_dir.exists()


class TestGetRepositoryIndexDir:
    """Tests for get_repository_index_dir function."""

    def test_returns_repo_specific_dir(self) -> None:
        """Returns repository-specific subdirectory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir) / "repo"
            git_root.mkdir()
            subprocess.run(["git", "init"], cwd=git_root, check=True, capture_output=True)

            cache_dir = Path(tmpdir) / "cache"
            result = get_repository_index_dir(git_root, cache_dir)
            assert result.parent == cache_dir
            assert len(result.name) == 16


class TestGetRepositoryManifestPath:
    """Tests for get_repository_manifest_path function."""

    def test_returns_manifest_path(self) -> None:
        """Returns manifest.json path in index directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir) / "repo"
            git_root.mkdir()
            subprocess.run(["git", "init"], cwd=git_root, check=True, capture_output=True)

            cache_dir = Path(tmpdir) / "cache"
            result = get_repository_manifest_path(git_root, cache_dir)
            assert result.name == "manifest.json"


class TestMigrateOldIndex:
    """Tests for migrate_old_index function."""

    def test_returns_false_when_no_old_index(self) -> None:
        """Returns False when no old index exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            new_index_dir = Path(tmpdir) / "new_index"

            result = migrate_old_index(git_root, new_index_dir)
            assert result is False

    def test_migrates_old_index_dir(self) -> None:
        """Migrates old index directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            henchman_dir = git_root / ".henchman"
            henchman_dir.mkdir()
            old_index = henchman_dir / "rag_index"
            old_index.mkdir()
            (old_index / "test.txt").write_text("test content")

            new_index_dir = Path(tmpdir) / "new_index"
            result = migrate_old_index(git_root, new_index_dir)

            assert result is True
            assert (new_index_dir / "chroma" / "test.txt").exists()

    def test_migrates_old_manifest(self) -> None:
        """Migrates old manifest file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            henchman_dir = git_root / ".henchman"
            henchman_dir.mkdir()
            old_manifest = henchman_dir / "rag_manifest.json"
            old_manifest.write_text('{"files": {}}')

            new_index_dir = Path(tmpdir) / "new_index"
            result = migrate_old_index(git_root, new_index_dir)

            assert result is True
            assert (new_index_dir / "manifest.json").exists()

    def test_handles_migration_errors(self) -> None:
        """Handles errors during migration gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            henchman_dir = git_root / ".henchman"
            henchman_dir.mkdir()
            old_index = henchman_dir / "rag_index"
            old_index.mkdir()

            new_index_dir = Path(tmpdir) / "new_index"

            with patch("shutil.copytree", side_effect=PermissionError("denied")):
                # Should not raise, just return False or handle gracefully
                migrate_old_index(git_root, new_index_dir)
                # Migration fails but doesn't raise
