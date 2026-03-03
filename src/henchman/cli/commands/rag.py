"""RAG system management command.

This module provides the /rag command for managing the RAG index.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from henchman.cli.commands import BaseCommand, CommandContext

if TYPE_CHECKING:
    from henchman.rag.system import RagSystem


class RagCommand(BaseCommand):
    """/rag command for RAG index management."""

    _help_command_name = "RAG Index"
    _help_lines = [
        "  /rag status     - Show index statistics",
        "  /rag reindex    - Force full reindex of all files",
        "  /rag clear      - Clear current project's index",
        "  /rag clear-all  - Clear ALL RAG indices",
        "  /rag cleanup    - Clean up old project-based indices",
    ]

    @property
    def name(self) -> str:
        """Command name.

        Returns:
            Command name string.
        """
        return "rag"

    @property
    def description(self) -> str:
        """Command description.

        Returns:
            Description string.
        """
        return "Manage RAG (semantic search) index"

    @property
    def usage(self) -> str:
        """Command usage.

        Returns:
            Usage string.
        """
        return "/rag <status|reindex|clear|clear-all|cleanup>"

    async def execute(self, ctx: CommandContext) -> None:
        """Execute the rag command.

        Args:
            ctx: Command context.
        """
        if not ctx.args:
            await self._show_help(ctx)
            return

        subcommand = ctx.args[0].lower()
        if subcommand == "status":
            await self._status(ctx)
        elif subcommand == "reindex":
            await self._reindex(ctx)
        elif subcommand == "clear":
            await self._clear(ctx)
        elif subcommand == "clear-all":
            await self._clear_all(ctx)
        elif subcommand == "cleanup":
            await self._cleanup(ctx)
        else:
            await self._show_help(ctx)

    def _get_rag_system(self, ctx: CommandContext) -> RagSystem | None:
        """Get the RAG system from context.

        Args:
            ctx: Command context.

        Returns:
            RagSystem if available, None otherwise.
        """
        # The RAG system is stored on the repl object
        repl = getattr(ctx, "repl", None)
        if repl is None:
            return None
        return getattr(repl, "rag_system", None)

    async def _status(self, ctx: CommandContext) -> None:
        """Show RAG index status."""
        rag_system = self._get_rag_system(ctx)

        if rag_system is None:
            ctx.console.print(
                "[yellow]RAG not available. "
                "Make sure you're in a git repository and RAG is enabled.[/]",
            )
            return

        stats = rag_system.get_stats()
        ctx.console.print("\n[bold blue]RAG Index Status[/]\n")
        ctx.console.print(f"  Git root: {rag_system.git_root}")
        ctx.console.print(f"  Index directory: {rag_system.index_dir}")
        ctx.console.print(f"  Embedding model: {rag_system.settings.embedding_model}")
        ctx.console.print(f"  Chunk size: {rag_system.settings.chunk_size} tokens")
        ctx.console.print(f"  Files indexed: {stats.files_unchanged}")
        ctx.console.print(f"  Total chunks: {stats.total_chunks}")
        ctx.console.print("")

    async def _reindex(self, ctx: CommandContext) -> None:
        """Force full reindex."""
        rag_system = self._get_rag_system(ctx)

        if rag_system is None:
            ctx.console.print(
                "[yellow]RAG not available. "
                "Make sure you're in a git repository and RAG is enabled.[/]",
            )
            return

        if getattr(rag_system, "is_indexing", False):
            ctx.console.print("[yellow]RAG indexing is already in progress in the background.[/]")
            return

        ctx.console.print("[dim]Forcing full reindex...[/]")
        stats = rag_system.index(console=ctx.console, force=True)
        if stats:
            ctx.console.print(
                f"[green]Reindex complete: {stats.files_added} files, "
                f"{stats.total_chunks} chunks[/]",
            )

    async def _clear(self, ctx: CommandContext) -> None:
        """Clear the RAG index."""
        rag_system = self._get_rag_system(ctx)

        if rag_system is None:
            ctx.console.print(
                "[yellow]RAG not available. "
                "Make sure you're in a git repository and RAG is enabled.[/]",
            )
            return

        rag_system.clear()
        ctx.console.print("[green]Current project's RAG index cleared[/]")

    async def _clear_all(self, ctx: CommandContext) -> None:
        """Clear ALL RAG indices from the cache directory."""
        from henchman.rag.repo_id import get_rag_cache_dir

        cache_dir = get_rag_cache_dir()

        if not cache_dir.exists():
            ctx.console.print("[yellow]No RAG cache directory found[/]")
            return

        # Ask for confirmation using simple input
        ctx.console.print("[yellow]Warning: This will delete ALL RAG indices![/]")
        ctx.console.print("Type 'yes' to confirm: ", end="")
        try:
            confirm = input()
        except (EOFError, KeyboardInterrupt):
            confirm = ""

        if confirm.lower() in ("yes", "y"):
            try:
                shutil.rmtree(cache_dir)
                ctx.console.print(f"[green]Cleared all RAG indices from {cache_dir}[/]")
            except Exception as e:
                ctx.console.print(f"[red]Error clearing indices: {e}[/]")
        else:
            ctx.console.print("[dim]Operation cancelled[/]")

    async def _cleanup(self, ctx: CommandContext) -> None:
        """Clean up old project-based RAG indices."""
        from henchman.rag.system import find_git_root

        # Find git root if we're in a repository
        git_root = find_git_root()
        if not git_root:
            ctx.console.print("[yellow]Not in a git repository[/]")
            return

        old_index_dir = git_root / ".henchman" / "rag_index"
        old_manifest = git_root / ".henchman" / "rag_manifest.json"

        removed = []

        if old_index_dir.exists():
            try:
                shutil.rmtree(old_index_dir)
                removed.append(f"Index directory: {old_index_dir}")
            except Exception as e:
                ctx.console.print(f"[yellow]Error removing {old_index_dir}: {e}[/]")

        if old_manifest.exists():
            try:
                old_manifest.unlink()
                removed.append(f"Manifest file: {old_manifest}")
            except Exception as e:
                ctx.console.print(f"[yellow]Error removing {old_manifest}: {e}[/]")

        if removed:
            ctx.console.print("[green]Cleaned up old project-based RAG indices:[/]")
            for item in removed:
                ctx.console.print(f"  • {item}")
        else:
            ctx.console.print("[dim]No old project-based RAG indices found[/]")
