"""Tests for the /rag command."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from rich.console import Console

from henchman.cli.commands import CommandContext
from henchman.cli.commands.rag import RagCommand


class TestRagCommand:
    """Tests for the RagCommand."""

    def test_name(self) -> None:
        """Command has correct name."""
        cmd = RagCommand()
        assert cmd.name == "rag"

    def test_description(self) -> None:
        """Command has description."""
        cmd = RagCommand()
        assert "rag" in cmd.description.lower() or "search" in cmd.description.lower()

    def test_usage(self) -> None:
        """Command has usage."""
        cmd = RagCommand()
        assert "/rag" in cmd.usage

    async def test_execute_no_args_shows_help(self) -> None:
        """No args shows help."""
        cmd = RagCommand()
        console = Console(force_terminal=True)
        ctx = CommandContext(console=console, args=[])

        await cmd.execute(ctx)
        # Just verifies no exception

    async def test_execute_unknown_subcommand_shows_help(self) -> None:
        """Unknown subcommand shows help."""
        cmd = RagCommand()
        console = Console(force_terminal=True)
        ctx = CommandContext(console=console, args=["unknown"])

        await cmd.execute(ctx)
        # Just verifies no exception

    async def test_status_no_rag_system(self) -> None:
        """Status without RAG system shows warning."""
        cmd = RagCommand()
        console = Console(force_terminal=True)
        ctx = CommandContext(console=console, args=["status"])

        await cmd.execute(ctx)
        # Just verifies no exception

    async def test_reindex_no_rag_system(self) -> None:
        """Reindex without RAG system shows warning."""
        cmd = RagCommand()
        console = Console(force_terminal=True)
        ctx = CommandContext(console=console, args=["reindex"])

        await cmd.execute(ctx)
        # Just verifies no exception

    async def test_clear_no_rag_system(self) -> None:
        """Clear without RAG system shows warning."""
        cmd = RagCommand()
        console = Console(force_terminal=True)
        ctx = CommandContext(console=console, args=["clear"])

        await cmd.execute(ctx)
        # Just verifies no exception

    async def test_status_with_rag_system(self) -> None:
        """Status with RAG system shows info."""
        from henchman.config.schema import RagSettings
        from henchman.rag.indexer import IndexStats

        cmd = RagCommand()
        console = Console(force_terminal=True)

        mock_rag = MagicMock()
        mock_rag.git_root = Path("/test/repo")
        mock_rag.settings = RagSettings()
        mock_rag.get_stats.return_value = IndexStats(
            files_unchanged=10,
            total_chunks=50,
        )

        mock_repl = MagicMock()
        mock_repl.rag_system = mock_rag

        ctx = CommandContext(console=console, args=["status"])
        ctx.repl = mock_repl  # type: ignore[attr-defined]

        await cmd.execute(ctx)
        mock_rag.get_stats.assert_called_once()

    async def test_reindex_with_rag_system(self) -> None:
        """Reindex with RAG system reindexes."""
        from henchman.rag.indexer import IndexStats

        cmd = RagCommand()
        console = Console(force_terminal=True)

        mock_rag_system = MagicMock()
        mock_rag_system.index.return_value = IndexStats(
            files_added=5,
            total_chunks=25,
        )
        mock_rag_system.is_indexing = False
        mock_repl = MagicMock()
        mock_repl.rag_system = mock_rag_system

        ctx = CommandContext(console=console, args=["reindex"])
        ctx.repl = mock_repl  # type: ignore[attr-defined]

        await cmd.execute(ctx)
        mock_repl.rag_system.index.assert_called_once_with(console=console, force=True)

    async def test_clear_with_rag_system(self) -> None:
        """Clear with RAG system clears index."""
        cmd = RagCommand()
        console = Console(force_terminal=True)

        mock_rag = MagicMock()

        mock_repl = MagicMock()
        mock_repl.rag_system = mock_rag

        ctx = CommandContext(console=console, args=["clear"])
        ctx.repl = mock_repl  # type: ignore[attr-defined]

        await cmd.execute(ctx)
        mock_rag.clear.assert_called_once()


class TestRagClearAll:
    """Tests for /rag clear-all command."""

    async def test_clear_all_no_cache_dir(self) -> None:
        """clear-all when no cache directory exists."""
        cmd = RagCommand()
        console = Console(force_terminal=True)
        ctx = CommandContext(console=console, args=["clear-all"])

        with patch("henchman.rag.repo_id.get_rag_cache_dir") as mock_get_cache:
            mock_get_cache.return_value = Path("/nonexistent/path")
            await cmd.execute(ctx)
            # Just verifies no exception

    async def test_clear_all_confirmed(self) -> None:
        """clear-all with confirmation deletes cache."""
        cmd = RagCommand()
        console = Console(force_terminal=True)
        ctx = CommandContext(console=console, args=["clear-all"])

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "rag_cache"
            cache_dir.mkdir()
            (cache_dir / "test.txt").write_text("test")

            with (
                patch(
                    "henchman.rag.repo_id.get_rag_cache_dir",
                    return_value=cache_dir,
                ),
                patch("builtins.input", return_value="yes"),
            ):
                await cmd.execute(ctx)
                assert not cache_dir.exists()

    async def test_clear_all_cancelled(self) -> None:
        """clear-all cancelled by user."""
        cmd = RagCommand()
        console = Console(force_terminal=True)
        ctx = CommandContext(console=console, args=["clear-all"])

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "rag_cache"
            cache_dir.mkdir()
            (cache_dir / "test.txt").write_text("test")

            with (
                patch(
                    "henchman.rag.repo_id.get_rag_cache_dir",
                    return_value=cache_dir,
                ),
                patch("builtins.input", return_value="no"),
            ):
                await cmd.execute(ctx)
                assert cache_dir.exists()

    async def test_clear_all_keyboard_interrupt(self) -> None:
        """clear-all handles KeyboardInterrupt."""
        cmd = RagCommand()
        console = Console(force_terminal=True)
        ctx = CommandContext(console=console, args=["clear-all"])

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "rag_cache"
            cache_dir.mkdir()

            with (
                patch(
                    "henchman.rag.repo_id.get_rag_cache_dir",
                    return_value=cache_dir,
                ),
                patch("builtins.input", side_effect=KeyboardInterrupt),
            ):
                await cmd.execute(ctx)
                assert cache_dir.exists()

    async def test_clear_all_error_handling(self) -> None:
        """clear-all handles deletion errors."""
        cmd = RagCommand()
        console = Console(force_terminal=True)
        ctx = CommandContext(console=console, args=["clear-all"])

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "rag_cache"
            cache_dir.mkdir()

            with (
                patch(
                    "henchman.rag.repo_id.get_rag_cache_dir",
                    return_value=cache_dir,
                ),
                patch("builtins.input", return_value="yes"),
                patch("shutil.rmtree", side_effect=PermissionError("denied")),
            ):
                await cmd.execute(ctx)
                # Should handle error gracefully


class TestRagCleanup:
    """Tests for /rag cleanup command."""

    async def test_cleanup_not_in_git_repo(self) -> None:
        """cleanup when not in a git repository."""
        cmd = RagCommand()
        console = Console(force_terminal=True)
        ctx = CommandContext(console=console, args=["cleanup"])

        with patch("henchman.rag.system.find_git_root", return_value=None):
            await cmd.execute(ctx)
            # Just verifies no exception

    async def test_cleanup_with_old_indices(self) -> None:
        """cleanup removes old project-based indices."""
        cmd = RagCommand()
        console = Console(force_terminal=True)
        ctx = CommandContext(console=console, args=["cleanup"])

        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            henchman_dir = git_root / ".henchman"
            henchman_dir.mkdir()
            old_index = henchman_dir / "rag_index"
            old_index.mkdir()
            (old_index / "test.txt").write_text("test")
            old_manifest = henchman_dir / "rag_manifest.json"
            old_manifest.write_text("{}")

            with patch(
                "henchman.rag.system.find_git_root",
                return_value=git_root,
            ):
                await cmd.execute(ctx)
                assert not old_index.exists()
                assert not old_manifest.exists()

    async def test_cleanup_no_old_indices(self) -> None:
        """cleanup when no old indices exist."""
        cmd = RagCommand()
        console = Console(force_terminal=True)
        ctx = CommandContext(console=console, args=["cleanup"])

        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)

            with patch(
                "henchman.rag.system.find_git_root",
                return_value=git_root,
            ):
                await cmd.execute(ctx)
                # Just verifies no exception

    async def test_cleanup_handles_removal_errors(self) -> None:
        """cleanup handles errors removing old indices."""
        cmd = RagCommand()
        console = Console(force_terminal=True)
        ctx = CommandContext(console=console, args=["cleanup"])

        with tempfile.TemporaryDirectory() as tmpdir:
            git_root = Path(tmpdir)
            henchman_dir = git_root / ".henchman"
            henchman_dir.mkdir()
            old_index = henchman_dir / "rag_index"
            old_index.mkdir()

            with (
                patch(
                    "henchman.rag.system.find_git_root",
                    return_value=git_root,
                ),
                patch("shutil.rmtree", side_effect=PermissionError("denied")),
            ):
                await cmd.execute(ctx)
                # Should handle error gracefully
