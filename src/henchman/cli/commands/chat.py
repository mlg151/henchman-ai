"""Chat session management command.

This module provides the /chat command for saving, listing, and resuming sessions.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from henchman.cli.commands import BaseCommand, CommandContext
from henchman.providers.base import Message, ToolCall

if TYPE_CHECKING:
    from henchman.core.session import SessionManager


class ChatCommand(BaseCommand):
    """/chat command for session management."""

    _help_command_name = "Chat Session"
    _help_lines = [
        "  /chat save [tag]       - Save current session",
        "  /chat list             - List saved sessions",
        "  /chat resume <tag|id>  - Resume a saved session",
    ]

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
                f"  {tag_display} - {meta.message_count} messages, updated {meta.last_updated[:10]}"
            )
        ctx.console.print("")

    async def _resume(self, ctx: CommandContext) -> None:
        """Resume a saved session."""
        manager: SessionManager | None = getattr(ctx, "session_manager", None)
        if manager is None:
            ctx.console.print("[red]Session manager not available[/]")
            return

        if len(ctx.args) < 2:
            ctx.console.print("[yellow]Usage: /chat resume <tag|id>[/]")
            return

        tag_or_id = ctx.args[1]
        project_hash = getattr(ctx, "project_hash", None)

        # Try loading by tag first
        session = manager.load_by_tag(tag_or_id, project_hash)

        # If that fails, try loading by ID
        if session is None:
            with contextlib.suppress(ValueError, FileNotFoundError):
                session = manager.load(tag_or_id)

        if session is None:
            ctx.console.print(f"[red]Session not found: {tag_or_id}[/]")
            return

        # Use repl.set_session if available to handle all sync logic
        if ctx.repl and hasattr(ctx.repl, "set_session"):
            ctx.repl.set_session(session)
        else:
            # Fallback for when REPL isn't available (e.g. some tests)
            manager.set_current(session)

            # Restore session messages to agent history
            if ctx.agent is not None:
                # Clear agent history (keeping system prompt)
                ctx.agent.clear_history()

                # Convert SessionMessage objects to Message objects
                for session_msg in session.messages:
                    # Convert tool_calls from dicts to ToolCall objects if present
                    tool_calls = None
                    if session_msg.tool_calls:
                        tool_calls = [
                            ToolCall(
                                id=tc.get("id", ""),
                                name=tc.get("name", ""),
                                arguments=tc.get("arguments", {}),
                            )
                            for tc in session_msg.tool_calls
                        ]

                    msg = Message(
                        role=session_msg.role,
                        content=session_msg.content,
                        tool_calls=tool_calls,
                        tool_call_id=session_msg.tool_call_id,
                    )
                    ctx.agent.messages.append(msg)

        ctx.console.print(
            f"[green]✓[/] Resumed session '{tag_or_id}' ({len(session.messages)} messages)"
        )
