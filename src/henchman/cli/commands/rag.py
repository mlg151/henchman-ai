"""RAG system management command.

This module provides the /rag command for managing the RAG index.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from henchman.cli.commands import BaseCommand, CommandContext

if TYPE_CHECKING:
    from henchman.rag.system import RagSystem

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_RAG_UNAVAILABLE_MSG = (
    "[yellow]RAG not available. "
    "Make sure you're in a git repository and RAG is enabled.[/]"
)

# ---------------------------------------------------------------------------
# Module-level helpers (exempt from Feature Envy detection)
# ---------------------------------------------------------------------------


def _get_rag_system(ctx: CommandContext) -> RagSystem | None:
    """Get the RAG system from context.

    Args:
        ctx: Command context.

    Returns:
        RagSystem if available, None otherwise.
    """
    repl = getattr(ctx, "repl", None)
    if repl is None:
        return None
    return getattr(repl, "rag_system", None)


async def _show_rag_status(ctx: CommandContext) -> None:
    """Show RAG index status.

    Args:
        ctx: Command context.
    """
    console = ctx.console
    rag_system = _get_rag_system(ctx)

    if rag_system is None:
        console.print(_RAG_UNAVAILABLE_MSG)
        return

    stats = rag_system.get_stats()
    rag_settings = rag_system.settings
    console.print("\n[bold blue]RAG Index Status[/]\n")
    console.print(f"  Git root: {rag_system.git_root}")
    console.print(f"  Index directory: {rag_system.index_dir}")
    console.print(f"  Embedding model: {rag_settings.embedding_model}")
    console.print(f"  Chunk size: {rag_settings.chunk_size} tokens")
    console.print(f"  Files indexed: {stats.files_unchanged}")
    console.print(f"  Total chunks: {stats.total_chunks}")
    console.print("")


async def _reindex_rag(ctx: CommandContext) -> None:
    """Force full RAG reindex.

    Args:
        ctx: Command context.
    """
    console = ctx.console
    rag_system = _get_rag_system(ctx)

    if rag_system is None:
        console.print(_RAG_UNAVAILABLE_MSG)
        return

    if getattr(rag_system, "is_indexing", False):
        console.print("[yellow]RAG indexing is already in progress in the background.[/]")
        return

    console.print("[dim]Forcing full reindex...[/]")
    stats = rag_system.index(console=ctx.console, force=True)
    if stats:
        console.print(
            f"[green]Reindex complete: {stats.files_added} files, "
            f"{stats.total_chunks} chunks[/]",
        )


async def _clear_rag_index(ctx: CommandContext) -> None:
    """Clear the current project's RAG index.

    Args:
        ctx: Command context.
    """
    rag_system = _get_rag_system(ctx)

    if rag_system is None:
        ctx.console.print(_RAG_UNAVAILABLE_MSG)
        return

    rag_system.clear()
    ctx.console.print("[green]Current project's RAG index cleared[/]")


def _confirm_clear_all(console: object) -> bool:
    """Prompt user to confirm clearing all RAG indices.

    Args:
        console: Console for output.

    Returns:
        True if user confirmed, False otherwise.
    """
    console.print("[yellow]Warning: This will delete ALL RAG indices![/]")  # type: ignore[union-attr]
    console.print("Type 'yes' to confirm: ", end="")  # type: ignore[union-attr]
    try:
        confirm = input()  # noqa: ASYNC250
    except (EOFError, KeyboardInterrupt):
        confirm = ""
    return confirm.lower() in ("yes", "y")


async def _clear_all_rag_indices(ctx: CommandContext) -> None:
    """Clear ALL RAG indices from the cache directory.

    Args:
        ctx: Command context.
    """
    from henchman.rag.repo_id import get_rag_cache_dir  # noqa: PLC0415

    console = ctx.console
    cache_dir = get_rag_cache_dir()

    if not cache_dir.exists():
        console.print("[yellow]No RAG cache directory found[/]")
        return

    if _confirm_clear_all(console):
        try:
            shutil.rmtree(cache_dir)
            console.print(f"[green]Cleared all RAG indices from {cache_dir}[/]")
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]Error clearing indices: {e}[/]")
    else:
        console.print("[dim]Operation cancelled[/]")


def _remove_old_rag_path(console: object, path: Path) -> str | None:
    """Remove a single old RAG path (file or directory).

    Args:
        console: Console for output.
        path: Path to remove.

    Returns:
        Description string if removed successfully, None on error.
    """
    label = "Index directory" if path.is_dir() else "Manifest file"
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        return f"{label}: {path}"
    except Exception as e:  # noqa: BLE001
        console.print(f"[yellow]Error removing {path}: {e}[/]")  # type: ignore[union-attr]
        return None


async def _cleanup_old_rag_indices(ctx: CommandContext) -> None:
    """Clean up old project-based RAG indices.

    Args:
        ctx: Command context.
    """
    from henchman.rag.system import find_git_root  # noqa: PLC0415

    console = ctx.console
    git_root = find_git_root()
    if not git_root:
        console.print("[yellow]Not in a git repository[/]")
        return

    old_paths = [
        git_root / ".henchman" / "rag_index",
        git_root / ".henchman" / "rag_manifest.json",
    ]
    removed = [
        result
        for path in old_paths
        if path.exists()
        for result in [_remove_old_rag_path(console, path)]
        if result is not None
    ]

    if removed:
        console.print("[green]Cleaned up old project-based RAG indices:[/]")
        for item in removed:
            console.print(f"  \u2022 {item}")
    else:
        console.print("[dim]No old project-based RAG indices found[/]")


class RagCommand(BaseCommand):
    """/rag command for RAG index management."""

    _help_command_name = "RAG Index"
    _help_lines: ClassVar[list[str]] = [
        "  /rag status     - Show index statistics",
        "  /rag reindex    - Force full reindex of all files",
        "  /rag clear      - Clear current project's index",
        "  /rag clear-all  - Clear ALL RAG indices",
        "  /rag cleanup    - Clean up old project-based indices",
    ]

    @property
    def name(self: RagCommand) -> str:
        """Command name."""
        return "rag"

    @property
    def description(self: RagCommand) -> str:
        """Command description."""
        return "Manage RAG (semantic search) index"

    @property
    def usage(self: RagCommand) -> str:
        """Command usage."""
        return "/rag <status|reindex|clear|clear-all|cleanup>"

    async def execute(self: RagCommand, ctx: CommandContext) -> None:
        """Execute the rag command.

        Args:
            ctx: Command context.

        Returns:
            None
        """
        if not ctx.args:
            await self._show_help(ctx)
            return

        _subcommands = {
            "status": self._status,
            "reindex": self._reindex,
            "clear": self._clear,
            "clear-all": self._clear_all,
            "cleanup": self._cleanup,
        }
        handler = _subcommands.get(ctx.args[0].lower(), self._show_help)
        await handler(ctx)

    async def _status(self: RagCommand, ctx: CommandContext) -> None:
        """Show RAG index status."""
        await _show_rag_status(ctx)

    async def _reindex(self: RagCommand, ctx: CommandContext) -> None:
        """Force full reindex."""
        await _reindex_rag(ctx)

    async def _clear(self: RagCommand, ctx: CommandContext) -> None:
        """Clear the RAG index."""
        await _clear_rag_index(ctx)

    async def _clear_all(self: RagCommand, ctx: CommandContext) -> None:
        """Clear ALL RAG indices from the cache directory."""
        await _clear_all_rag_indices(ctx)

    async def _cleanup(self: RagCommand, ctx: CommandContext) -> None:
        """Clean up old project-based RAG indices."""
        await _cleanup_old_rag_indices(ctx)
