"""Chat session management command.

This module provides the /chat command for saving, listing, and resuming sessions.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any, ClassVar

from henchman.cli.commands import BaseCommand, CommandContext
from henchman.providers.base import Message, ToolCall

if TYPE_CHECKING:
    from henchman.core.session import Session, SessionManager

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_SESSION_TAG_DISPLAY_WIDTH = 8
_SESSION_MSG_DISPLAY_WIDTH = 10

# ---------------------------------------------------------------------------
# Module-level helpers (exempt from Feature Envy detection)
# ---------------------------------------------------------------------------


async def _parse_subcommand(
    ctx: CommandContext,
    handlers: dict[str, Callable[[CommandContext], Coroutine[Any, Any, None]]],
    show_help: Callable[[CommandContext], Coroutine[Any, Any, None]],
) -> None:
    """Dispatch to the matching subcommand handler or fall back to help.

    Args:
        ctx: Command context.
        handlers: Mapping of subcommand name → async handler.
        show_help: Coroutine invoked when no subcommand matches.
    """
    if not ctx.args:
        await show_help(ctx)
        return

    handler = handlers.get(ctx.args[0].lower())
    if handler:
        await handler(ctx)
    else:
        await show_help(ctx)


async def _save_session(ctx: CommandContext) -> None:
    """Save the current session to disk.

    Args:
        ctx: Command context containing session_manager and console.
    """
    console = ctx.console
    manager: SessionManager | None = getattr(ctx, "session_manager", None)
    if manager is None:
        console.print("[red]Session manager not available[/]")
        return

    session = manager.current
    if session is None:
        console.print("[yellow]No active session to save[/]")
        return

    tag = ctx.args[1] if len(ctx.args) > 1 else None
    if tag:
        session.tag = tag

    manager.save(session)
    tag_display = f" as '{session.tag}'" if session.tag else ""
    console.print(f"[green]✓[/] Session saved{tag_display}")


async def _list_sessions(ctx: CommandContext) -> None:
    """List saved sessions to the console.

    Args:
        ctx: Command context containing session_manager, console, and project_hash.
    """
    console = ctx.console
    manager: SessionManager | None = getattr(ctx, "session_manager", None)
    if manager is None:
        console.print("[red]Session manager not available[/]")
        return

    project_hash = getattr(ctx, "project_hash", None)
    sessions = manager.list_sessions(project_hash)

    if not sessions:
        console.print("[dim]No saved sessions[/]")
        return

    console.print("\n[bold blue]Saved Sessions[/]\n")
    for meta in sessions:
        meta_tag = meta.tag
        meta_id = meta.id
        tag_display = (
            f"[cyan]{meta_tag}[/]"
            if meta_tag
            else f"[dim]{meta_id[:_SESSION_TAG_DISPLAY_WIDTH]}[/]"
        )
        console.print(
            f"  {tag_display} - {meta.message_count} messages, "
            f"updated {meta.last_updated[:_SESSION_MSG_DISPLAY_WIDTH]}",
        )
    console.print("")


def _build_tool_calls_from_session_msg(
    tool_call_dicts: list[dict[str, Any]],
) -> list[ToolCall]:
    """Convert a list of tool-call dicts into ToolCall objects.

    Args:
        tool_call_dicts: Raw tool-call dictionaries stored in a SessionMessage.

    Returns:
        List of ToolCall instances.
    """
    return [
        ToolCall(
            id=tc.get("id", ""),
            name=tc.get("name", ""),
            arguments=tc.get("arguments", {}),
        )
        for tc in tool_call_dicts
    ]


def _restore_agent_history_from_session(ctx: CommandContext, session: Session) -> None:
    """Replay session messages into the agent's message history.

    Args:
        ctx: Command context containing the agent.
        session: Session whose messages should be restored.
    """
    if ctx.agent is None:
        return

    ctx.agent.clear_history()

    for session_msg in session.messages:
        tool_call_dicts = session_msg.tool_calls
        tool_calls = (
            _build_tool_calls_from_session_msg(tool_call_dicts) if tool_call_dicts else None
        )
        ctx.agent.messages.append(
            Message(
                role=session_msg.role,
                content=session_msg.content,
                tool_calls=tool_calls,
                tool_call_id=session_msg.tool_call_id,
            ),
        )


def _restore_session_state(
    ctx: CommandContext,
    manager: SessionManager,
    session: Session,
    tag_or_id: str,
) -> None:
    """Activate a loaded session and sync it with the agent.

    Args:
        ctx: Command context.
        manager: Session manager used as fallback when REPL is unavailable.
        session: Session to activate.
        tag_or_id: Identifier used for the confirmation message.
    """
    if ctx.repl and hasattr(ctx.repl, "set_session"):
        ctx.repl.set_session(session)
    else:
        manager.set_current(session)
        _restore_agent_history_from_session(ctx, session)

    ctx.console.print(
        f"[green]✓[/] Resumed session '{tag_or_id}' ({len(session.messages)} messages)",
    )


class ChatCommand(BaseCommand):
    """/chat command for session management."""

    _MIN_RESUME_ARGS = 2

    _help_command_name = "Chat Session"
    _help_lines: ClassVar[list[str]] = [
        "  /chat save [tag]       - Save current session",
        "  /chat list             - List saved sessions",
        "  /chat resume <tag|id>  - Resume a saved session",
    ]

    @property
    def name(self: ChatCommand) -> str:
        """Command name.

        Returns:
            Command name string.
        """
        return "chat"

    @property
    def description(self: ChatCommand) -> str:
        """Command description.

        Returns:
            Description string.
        """
        return "Manage chat sessions (save, list, resume)"

    @property
    def usage(self: ChatCommand) -> str:
        """Command usage.

        Returns:
            Usage string.
        """
        return "/chat <save|list|resume> [tag]"

    async def execute(self: ChatCommand, ctx: CommandContext) -> None:
        """Execute the chat command.

        Args:
            ctx: Command context with args and session_manager.

        Returns:
            None
        """
        handlers: dict[str, Callable[[CommandContext], Coroutine[Any, Any, None]]] = {
            "save": self._save,
            "list": self._list,
            "resume": self._resume,
        }
        await _parse_subcommand(ctx, handlers, self._show_help)

    async def _save(self: ChatCommand, ctx: CommandContext) -> None:
        """Save the current session (delegates to module-level helper)."""
        await _save_session(ctx)

    async def _list(self: ChatCommand, ctx: CommandContext) -> None:
        """List saved sessions (delegates to module-level helper)."""
        await _list_sessions(ctx)

    async def _resume(self: ChatCommand, ctx: CommandContext) -> None:
        """Resume a saved session."""
        manager = self._get_session_manager(ctx)
        if manager is None:
            return

        if not self._validate_resume_args(ctx):
            return

        tag_or_id = ctx.args[1]
        session = self._load_session(ctx, manager, tag_or_id)

        if session is None:
            ctx.console.print(f"[red]Session not found: {tag_or_id}[/]")
            return

        self._restore_session(ctx, manager, session, tag_or_id)

    def _get_session_manager(self: ChatCommand, ctx: CommandContext) -> SessionManager | None:
        """Get session manager from context.

        Args:
            ctx: Command context.

        Returns:
            SessionManager instance or None if not available.
        """
        manager: SessionManager | None = getattr(ctx, "session_manager", None)
        if manager is None:
            ctx.console.print("[red]Session manager not available[/]")
        return manager

    def _validate_resume_args(self: ChatCommand, ctx: CommandContext) -> bool:
        """Validate resume command arguments.

        Args:
            ctx: Command context.

        Returns:
            True if arguments are valid, False otherwise.
        """
        if len(ctx.args) < self._MIN_RESUME_ARGS:
            ctx.console.print("[yellow]Usage: /chat resume <tag|id>[/]")
            return False
        return True

    def _load_session(
        self: ChatCommand,
        ctx: CommandContext,
        manager: SessionManager,
        tag_or_id: str,
    ) -> Session | None:
        """Load session by tag or ID.

        Args:
            ctx: Command context.
            manager: Session manager.
            tag_or_id: Session tag or ID.

        Returns:
            Session instance or None if not found.
        """
        project_hash = getattr(ctx, "project_hash", None)

        # Try loading by tag first, then fall back to ID lookup.
        session = manager.load_by_tag(tag_or_id, project_hash)
        if session is None:
            with contextlib.suppress(ValueError, FileNotFoundError):
                session = manager.load(tag_or_id)

        return session

    def _restore_session(
        self: ChatCommand,
        ctx: CommandContext,
        manager: SessionManager,
        session: Session,
        tag_or_id: str,
    ) -> None:
        """Restore session to context (delegates to module-level helper).

        Args:
            ctx: Command context.
            manager: Session manager.
            session: Session to restore.
            tag_or_id: Session tag or ID for display.
        """
        _restore_session_state(ctx, manager, session, tag_or_id)
