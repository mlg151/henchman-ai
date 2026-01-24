"""Chat session management command.

This module provides the /chat command for saving, listing, and resuming sessions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from henchman.cli.commands import Command, CommandContext

if TYPE_CHECKING:
    from henchman.core.session import SessionManager


class ChatCommand(Command):
    """/chat command for session management."""

    @property
    def name(self) -> str:
        """Command name.

        Returns:
            Command name string.
        """
        return "chat"

    @property
    def description(self) -> str:
        """Command description.

        Returns:
            Description string.
        """
        return "Manage chat sessions (save, list, resume)"

    @property
    def usage(self) -> str:
        """Command usage.

        Returns:
            Usage string.
        """
        return "/chat <save|list|resume> [tag]"

    async def execute(self, ctx: CommandContext) -> None:
        """Execute the chat command.

        Args:
            ctx: Command context with args and session_manager.
        """
        if not ctx.args:
            await self._show_help(ctx)
            return

        subcommand = ctx.args[0].lower()
        if subcommand == "save":
            await self._save(ctx)
        elif subcommand == "list":
            await self._list(ctx)
        elif subcommand == "resume":
            await self._resume(ctx)
        else:
            await self._show_help(ctx)

    async def _show_help(self, ctx: CommandContext) -> None:
        """Show help for /chat command."""
        ctx.console.print("\n[bold blue]Chat Session Commands[/]\n")
        ctx.console.print("  /chat save [tag]    - Save current session")
        ctx.console.print("  /chat list          - List saved sessions")
        ctx.console.print("  /chat resume <tag>  - Resume a saved session")
        ctx.console.print("")

    async def _save(self, ctx: CommandContext) -> None:
        """Save the current session."""
        manager: SessionManager | None = getattr(ctx, "session_manager", None)
        if manager is None:
            ctx.console.print("[red]Session manager not available[/]")
            return

        session = manager.current
        if session is None:
            ctx.console.print("[yellow]No active session to save[/]")
            return

        # Get tag from args if provided
        tag = ctx.args[1] if len(ctx.args) > 1 else None
        if tag:
            session.tag = tag

        manager.save(session)
        tag_display = f" as '{session.tag}'" if session.tag else ""
        ctx.console.print(f"[green]✓[/] Session saved{tag_display}")

    async def _list(self, ctx: CommandContext) -> None:
        """List saved sessions."""
        manager: SessionManager | None = getattr(ctx, "session_manager", None)
        if manager is None:
            ctx.console.print("[red]Session manager not available[/]")
            return

        project_hash = getattr(ctx, "project_hash", None)
        sessions = manager.list_sessions(project_hash)

        if not sessions:
            ctx.console.print("[dim]No saved sessions[/]")
            return

        ctx.console.print("\n[bold blue]Saved Sessions[/]\n")
        for meta in sessions:
            tag_display = f"[cyan]{meta.tag}[/]" if meta.tag else f"[dim]{meta.id[:8]}[/]"
            ctx.console.print(
                f"  {tag_display} - {meta.message_count} messages, "
                f"updated {meta.last_updated[:10]}"
            )
        ctx.console.print("")

    async def _resume(self, ctx: CommandContext) -> None:
        """Resume a saved session."""
        manager: SessionManager | None = getattr(ctx, "session_manager", None)
        if manager is None:
            ctx.console.print("[red]Session manager not available[/]")
            return

        if len(ctx.args) < 2:
            ctx.console.print("[yellow]Usage: /chat resume <tag>[/]")
            return

        tag = ctx.args[1]
        project_hash = getattr(ctx, "project_hash", None)

        session = manager.load_by_tag(tag, project_hash)
        if session is None:
            ctx.console.print(f"[red]Session not found: {tag}[/]")
            return

        manager.set_current(session)
        ctx.console.print(
            f"[green]✓[/] Resumed session '{tag}' ({len(session.messages)} messages)"
        )
