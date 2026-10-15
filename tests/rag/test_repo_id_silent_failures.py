"""Tests for BUG-018: RAG Index Migration Silently Swallows Failures.

Verifies that migrate_old_index() logs warnings when migration fails
instead of silently passing.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from henchman.rag.repo_id import migrate_old_index


def test_migrate_old_index_logs_warning_on_copytree_failure() -> None:
    """When shutil.copytree fails, a warning should be logged."""
    git_root = Path("/fake/git/root")
    new_index_dir = Path("/fake/new/index")

    with (
        patch("henchman.rag.repo_id.logger") as mock_logger,
        patch("henchman.rag.repo_id.Path.exists", return_value=True),
        patch("henchman.rag.repo_id.shutil.copytree", side_effect=PermissionError("Permission denied")),
        patch("henchman.rag.repo_id.shutil.copy2", side_effect=PermissionError("Permission denied")),
        patch("henchman.rag.repo_id.Path.mkdir"),
    ):
        result = migrate_old_index(git_root, new_index_dir)

        assert result is False
        # Should have logged at least one warning about migration failure
        assert len(mock_logger.warning.call_args_list) >= 1


def test_migrate_old_index_logs_warning_on_copy2_failure() -> None:
    """When shutil.copy2 fails, a warning should be logged."""
    git_root = Path("/fake/git/root")
    new_index_dir = Path("/fake/new/index")

    with (
        patch("henchman.rag.repo_id.logger") as mock_logger,
        patch("henchman.rag.repo_id.Path.exists", return_value=True),
        patch("henchman.rag.repo_id.shutil.copytree"),
        patch("henchman.rag.repo_id.shutil.copy2", side_effect=OSError("Disk full")),
        patch("henchman.rag.repo_id.Path.mkdir"),
    ):
        result = migrate_old_index(git_root, new_index_dir)

        assert result is True  # copytree succeeded (migrated=True), copy2 failed
        # Should have logged at least one warning about copy2/manifest failure
        assert len(mock_logger.warning.call_args_list) >= 1


def test_migrate_old_index_graceful_degradation_no_crash() -> None:
    """Migration returns False on failure (no crash), and caller can distinguish."""
    git_root = Path("/fake/git/root")
    new_index_dir = Path("/fake/new/index")

    with (
        patch("henchman.rag.repo_id.logger") as mock_logger,
        patch("henchman.rag.repo_id.Path.exists", return_value=True),
        patch("henchman.rag.repo_id.shutil.copytree", side_effect=PermissionError("Permission denied")),
        patch("henchman.rag.repo_id.shutil.copy2", side_effect=PermissionError("Permission denied")),
        patch("henchman.rag.repo_id.Path.mkdir"),
    ):
        result = migrate_old_index(git_root, new_index_dir)
        assert result is False
        assert len(mock_logger.warning.call_args_list) >= 1


def test_migrate_old_index_no_warning_when_no_old_index() -> None:
    """When no old index exists, no migration is attempted and no warning is logged."""
    git_root = Path("/fake/git/root")
    new_index_dir = Path("/fake/new/index")

    with (
        patch("henchman.rag.repo_id.logger") as mock_logger,
        patch("henchman.rag.repo_id.Path.exists", return_value=False),
        patch("henchman.rag.repo_id.Path.mkdir"),
    ):
        result = migrate_old_index(git_root, new_index_dir)
        assert result is False
        mock_logger.warning.assert_not_called()
