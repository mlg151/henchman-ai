"""Enhanced session management command.

This module provides the /session command for advanced session operations
including branching, merging, templates, and export/import.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from henchman.cli.commands import BaseCommand, CommandContext

if TYPE_CHECKING:
    from henchman.core.session import Session, SessionManager, SessionMetadata


# Display configuration constants
DEFAULT_ID_DISPLAY_LENGTH: int = 8
DEFAULT_DATE_DISPLAY_LENGTH: int = 10
DEFAULT_MIN_ARGS_FOR_TEMPLATE: int = 2
DEFAULT_MIN_ARGS_FOR_BRANCH: int = 3
DEFAULT_MIN_ARGS_FOR_MERGE: int = 3
DEFAULT_MIN_ARGS_FOR_EXPORT: int = 2
DEFAULT_MIN_ARGS_FOR_IMPORT: int = 2
DEFAULT_MIN_ARGS_FOR_TEMPLATE_SAVE: int = 4
DEFAULT_MIN_ARGS_FOR_TEMPLATE_CREATE: int = 3
DEFAULT_MIN_ARGS_FOR_TEMPLATE_DELETE: int = 3


@dataclass
class SessionListParams:
    """Parameters for session listing operations."""
    project_hash: str | None = None
    show_enhanced_info: bool = True
    max_id_display_len: int = DEFAULT_ID_DISPLAY_LENGTH
    max_date_display_len: int = DEFAULT_DATE_DISPLAY_LENGTH


class SessionCommandHelper:
    """Helper class for session command operations to reduce class size and feature envy."""

    def __init__(self, command: SessionCommand):
        self.command = command

    def _get_manager(self, ctx: CommandContext) -> SessionManager | None:
        """Get session manager from context with error handling.

        Args:
            ctx: Command context.

        Returns:
            SessionManager or None if not available.
        """
        manager: SessionManager | None = getattr(ctx, "session_manager", None)
        if manager is None:
            ctx.console.print("[red]Session manager not available[/]")
        return manager

    def _ensure_args(self, ctx: CommandContext, min_args: int, usage: str) -> bool:
        """Ensure minimum number of arguments.

        Args:
            ctx: Command context.
            min_args: Minimum number of arguments required.
            usage: Usage string to show if validation fails.

        Returns:
            True if arguments are valid, False otherwise.
        """
        if len(ctx.args) < min_args:
            ctx.console.print(f"[yellow]Usage: {usage}[/]")
            return False
        return True

    def _parse_merge_arguments(self, ctx: CommandContext) -> tuple[list[str], str, str | None]:
        """Parse merge command arguments.

        Args:
            ctx: Command context.

        Returns:
            Tuple of (session_ids, strategy, tag).
        """
        session_ids = [ctx.args[self.command._MERGE_ID1_IDX], ctx.args[self.command._MERGE_ID2_IDX]]
        strategy = "smart"
        tag = None

        # Parse optional arguments
        if len(ctx.args) > self.command._MERGE_STRATEGY_IDX:
            if ctx.args[self.command._MERGE_STRATEGY_IDX] in ("union", "intersection", "smart"):
                strategy = ctx.args[self.command._MERGE_STRATEGY_IDX]
                if len(ctx.args) > self.command._MERGE_TAG_IDX:
                    tag = ctx.args[self.command._MERGE_TAG_IDX]
            else:
                tag = ctx.args[self.command._MERGE_STRATEGY_IDX]

        return session_ids, strategy, tag

    def _format_session_display(
        self,
        meta: SessionMetadata,
        session: Session | None = None,
        params: SessionListParams | None = None
    ) -> str:
        """Format a session for display.

        Args:
            meta: Session metadata.
            session: Optional full session object for enhanced info.
            params: Display parameters.

        Returns:
            Formatted display string.
        """
        if params is None:
            params = SessionListParams()

        tag_display = f"[cyan]{meta.tag}[/]" if meta.tag else f"[dim]{meta.id[:params.max_id_display_len]}[/]"

        if session is None:
            return (
                f"  {tag_display} - {meta.message_count} messages, "
                f"updated {meta.last_updated[:params.max_date_display_len]}"
            )

        branch_info = ""
        template_info = ""

        if session.parent_id:
            branch_info = f" [yellow]↳[/] branch from {session.parent_id[:params.max_id_display_len]}"
        if session.template_id:
            template_info = f" [magenta]ⓣ[/] template:{session.template_id[:params.max_id_display_len]}"

        return f"  {tag_display}{branch_info}{template_info}"

    def _format_session_details(
        self,
        meta: SessionMetadata,
        session: Session | None = None
    ) -> str:
        """Format session details for display.

        Args:
            meta: Session metadata.
            session: Optional full session object for enhanced info.

        Returns:
            Formatted details string.
        """
        details = f"    Messages: {meta.message_count}, Updated: {meta.last_updated[:DEFAULT_DATE_DISPLAY_LENGTH]}"

        if session and session.export_metadata and "merged_from" in session.export_metadata:
            details += f"\n    [dim]Merged from {len(session.export_metadata['merged_from'])} sessions[/]"

        return details

    async def _execute_branch(self, ctx: CommandContext, manager: SessionManager) -> None:
        """Execute branch operation.

        Args:
            ctx: Command context.
            manager: Session manager.
        """
        if not self._ensure_args(ctx, DEFAULT_MIN_ARGS_FOR_BRANCH, "/session branch <id> <point> [tag]"):
            return

        session_id = ctx.args[self.command._BRANCH_ID_IDX]
        try:
            branch_point = int(ctx.args[self.command._BRANCH_POINT_IDX])
        except ValueError:
            ctx.console.print("[red]Branch point must be an integer[/]")
            return

        tag = ctx.args[self.command._BRANCH_TAG_IDX] if len(ctx.args) > self.command._BRANCH_TAG_IDX else None

        try:
            branch = manager.branch_session(session_id, branch_point, tag)
            manager.save(branch)
            ctx.console.print(f"[green]✓[/] Created branch: {branch.id}")
            if branch.tag:
                ctx.console.print(f"[dim]Tag: {branch.tag}[/]")
            ctx.console.print(f"[dim]Branch point: {branch_point}, Parent: {session_id}[/]")
        except (FileNotFoundError, ValueError) as e:
            ctx.console.print(f"[red]Error: {e}[/]")

    async def _execute_merge(self, ctx: CommandContext, manager: SessionManager) -> None:
        """Execute merge operation.

        Args:
            ctx: Command context.
            manager: Session manager.
        """
        if not self._ensure_args(ctx, DEFAULT_MIN_ARGS_FOR_MERGE, "/session merge <id1> <id2> [strategy] [tag]"):
            return

        session_ids, strategy, tag = self._parse_merge_arguments(ctx)

        try:
            merged = manager.merge_sessions(session_ids, strategy, tag)
            manager.save(merged)
            ctx.console.print(f"[green]✓[/] Created merged session: {merged.id}")
            if merged.tag:
                ctx.console.print(f"[dim]Tag: {merged.tag}[/]")
            ctx.console.print(f"[dim]Strategy: {strategy}, Sources: {', '.join(session_ids)}[/]")
            ctx.console.print(f"[dim]Messages: {len(merged.messages)}[/]")
        except (FileNotFoundError, ValueError) as e:
            ctx.console.print(f"[red]Error: {e}[/]")

    async def _execute_template_save(self, ctx: CommandContext, manager: SessionManager) -> None:
        """Execute template save operation.

        Args:
            ctx: Command context.
            manager: Session manager.
        """
        if not self._ensure_args(ctx, DEFAULT_MIN_ARGS_FOR_TEMPLATE_SAVE, "/session template save <id> <name>"):
            return

        session_id = ctx.args[self.command._TEMPLATE_SESSION_ID_IDX]
        name = ctx.args[self.command._TEMPLATE_NAME_IDX]
        description = ctx.args[self.command._TEMPLATE_DESC_IDX] if len(ctx.args) > self.command._TEMPLATE_DESC_IDX else ""

        try:
            template = manager.save_template(session_id, name, description)
            ctx.console.print(f"[green]✓[/] Saved template: {template['name']}")
            ctx.console.print(f"[dim]ID: {template['id']}[/]")
            if description:
                ctx.console.print(f"[dim]Description: {description}[/]")
        except (FileNotFoundError, ValueError) as e:
            ctx.console.print(f"[red]Error: {e}[/]")

    async def _execute_template_create(self, ctx: CommandContext, manager: SessionManager) -> None:
        """Execute template create operation.

        Args:
            ctx: Command context.
            manager: Session manager.
        """
        if not self._ensure_args(ctx, DEFAULT_MIN_ARGS_FOR_TEMPLATE_CREATE, "/session template create <template_id> [tag]"):
            return

        template_id = ctx.args[self.command._TEMPLATE_ID_IDX]
        tag = ctx.args[self.command._TEMPLATE_TAG_IDX] if len(ctx.args) > self.command._TEMPLATE_TAG_IDX else None

        try:
            session = manager.create_from_template(template_id, tag=tag)
            manager.save(session)
            ctx.console.print(f"[green]✓[/] Created session from template: {session.id}")
            if session.tag:
                ctx.console.print(f"[dim]Tag: {session.tag}[/]")
            ctx.console.print(f"[dim]Template: {template_id}[/]")
        except (FileNotFoundError, ValueError) as e:
            ctx.console.print(f"[red]Error: {e}[/]")

    async def _execute_template_list(self, ctx: CommandContext, manager: SessionManager) -> None:
        """Execute template list operation.

        Args:
            ctx: Command context.
            manager: Session manager.
        """
        templates = manager.list_templates()

        if not templates:
            ctx.console.print("[dim]No templates available[/]")
            return

        ctx.console.print("\n[bold blue]Available Templates[/]\n")
        for template in templates:
            ctx.console.print(f"  [cyan]{template['name']}[/]")
            ctx.console.print(f"    ID: {template['id']}")
            if template.get('description'):
                ctx.console.print(f"    Description: {template['description']}")
            if template.get('parameters'):
                params = ', '.join(template['parameters'].keys())
                ctx.console.print(f"    Parameters: {params}")
            ctx.console.print(f"    Created: {template.get('created_at', 'unknown')}")
            ctx.console.print("")

    async def _execute_template_delete(self, ctx: CommandContext, manager: SessionManager) -> None:
        """Execute template delete operation.

        Args:
            ctx: Command context.
            manager: Session manager.
        """
        if not self._ensure_args(ctx, DEFAULT_MIN_ARGS_FOR_TEMPLATE_DELETE, "/session template delete <template_id>"):
            return

        template_id = ctx.args[self.command._TEMPLATE_ID_IDX]

        try:
            manager.delete_template(template_id)
            ctx.console.print(f"[green]✓[/] Deleted template: {template_id}")
        except FileNotFoundError as e:
            ctx.console.print(f"[red]Error: {e}[/]")

    async def _execute_export(self, ctx: CommandContext, manager: SessionManager) -> None:
        """Execute export operation.

        Args:
            ctx: Command context.
            manager: Session manager.
        """
        if not self._ensure_args(ctx, DEFAULT_MIN_ARGS_FOR_EXPORT, "/session export <id> [format]"):
            return

        session_id = ctx.args[self.command._EXPORT_ID_IDX]
        format = ctx.args[self.command._EXPORT_FORMAT_IDX] if len(ctx.args) > self.command._EXPORT_FORMAT_IDX else "json"

        try:
            exported = manager.export_session(session_id, format)

            ext = "json" if format == "json" else "md"
            output_file = Path.cwd() / f"session_{session_id}.{ext}"
            output_file.write_text(exported)

            ctx.console.print(f"[green]✓[/] Exported session to: {output_file}")
            ctx.console.print(f"[dim]Format: {format}, Size: {len(exported)} bytes[/]")
        except (FileNotFoundError, ValueError) as e:
            ctx.console.print(f"[red]Error: {e}[/]")

    async def _execute_import(self, ctx: CommandContext, manager: SessionManager) -> None:
        """Execute import operation.

        Args:
            ctx: Command context.
            manager: Session manager.
        """
        if not self._ensure_args(ctx, DEFAULT_MIN_ARGS_FOR_IMPORT, "/session import <file> [format]"):
            return

        file_path = Path(ctx.args[self.command._IMPORT_FILE_IDX])
        if not file_path.exists():
            ctx.console.print(f"[red]File not found: {file_path}[/]")
            return

        format = ctx.args[self.command._IMPORT_FORMAT_IDX] if len(ctx.args) > self.command._IMPORT_FORMAT_IDX else "json"
        tag = ctx.args[self.command._IMPORT_TAG_IDX] if len(ctx.args) > self.command._IMPORT_TAG_IDX else None

        try:
            data = file_path.read_text()
            session = manager.import_session(data, format, tag)
            manager.save(session)

            ctx.console.print(f"[green]✓[/] Imported session: {session.id}")
            if session.tag:
                ctx.console.print(f"[dim]Tag: {session.tag}[/]")
            ctx.console.print(f"[dim]Format: {format}, Messages: {len(session.messages)}[/]")
        except (ValueError, json.JSONDecodeError) as e:
            ctx.console.print(f"[red]Error importing session: {e}[/]")


class SessionCommand(BaseCommand):
    """/session command for enhanced session management."""

    _help_command_name = "Enhanced Session"
    _help_lines = [
        "  /session branch <id> <point> [tag]  - Branch from session at message point",
        "  /session merge <id1> <id2> [strategy] [tag] - Merge sessions",
        "  /session template save <id> <name>  - Save session as template",
        "  /session template create <name>     - Create from template",
        "  /session template list              - List templates",
        "  /session template delete <id>       - Delete template",
        "  /session export <id> [format]       - Export session (json/markdown)",
        "  /session import <file> [format]     - Import session",
        "  /session list                       - List sessions with enhanced info",
        "",
        "[dim]Strategies: union, intersection, smart[/]",
        "[dim]Formats: json (default), markdown[/]",
    ]

    def __init__(self) -> None:
        """Initialize session command with helper."""
        super().__init__()
        self.helper = SessionCommandHelper(self)

    @property
    def name(self) -> str:
        """Command name.

        Returns:
            Command name string.
        """
        return "session"

    @property
    def description(self) -> str:
        """Command description.

        Returns:
            Description string.
        """
        return "Enhanced session management (branch, merge, templates, export/import)"

    @property
    def usage(self) -> str:
        """Command usage.

        Returns:
            Usage string.
        """
        return "/session <branch|merge|template|export|import|list> [args]"

    async def execute(self, ctx: CommandContext) -> None:
        """Execute the session command.

        Args:
            ctx: Command context with args and session_manager.
        """
        if not ctx.args:
            await self._show_help(ctx)
            return

        subcommand = ctx.args[0].lower()
        dispatch = {
            "branch": self._branch,
            "merge": self._merge,
            "template": self._template,
            "export": self._export,
            "import": self._import,
            "list": self._list,
        }

        handler = dispatch.get(subcommand)
        if handler:
            await handler(ctx)
        else:
            await self._show_help(ctx)

    async def _branch(self, ctx: CommandContext) -> None:
        """Branch from an existing session."""
        manager = self.helper._get_manager(ctx)
        if manager is not None:
            await self.helper._execute_branch(ctx, manager)

    async def _merge(self, ctx: CommandContext) -> None:
        """Merge multiple sessions."""
        manager = self.helper._get_manager(ctx)
        if manager is not None:
            await self.helper._execute_merge(ctx, manager)

    # Argument indexing constants
    _SUBCOMMAND_IDX = 0
    _ACTION_IDX = 1
    _SESSION_ID_IDX = 1  # For simple subcommands like export/import
    _BRANCH_ID_IDX = 1
    _BRANCH_POINT_IDX = 2
    _BRANCH_TAG_IDX = 3
    _MERGE_ID1_IDX = 1
    _MERGE_ID2_IDX = 2
    _MERGE_STRATEGY_IDX = 3
    _MERGE_TAG_IDX = 4
    _TEMPLATE_ACTION_IDX = 1
    _TEMPLATE_SESSION_ID_IDX = 2
    _TEMPLATE_NAME_IDX = 3
    _TEMPLATE_DESC_IDX = 4
    _TEMPLATE_ID_IDX = 2
    _EXPORT_ID_IDX = 1
    _EXPORT_FORMAT_IDX = 2
    _IMPORT_FILE_IDX = 1
    _IMPORT_FORMAT_IDX = 2
    _IMPORT_TAG_IDX = 3
    _TEMPLATE_TAG_IDX = 3
    _ID_DISPLAY_LEN = DEFAULT_ID_DISPLAY_LENGTH
    _DATE_DISPLAY_LEN = DEFAULT_DATE_DISPLAY_LENGTH

    async def _template(self, ctx: CommandContext) -> None:
        """Template operations."""
        manager = self.helper._get_manager(ctx)
        if manager is None:
            return

        if not self.helper._ensure_args(ctx, DEFAULT_MIN_ARGS_FOR_TEMPLATE, "/session template <save|create|list|delete> [args]"):
            return

        action = ctx.args[self._TEMPLATE_ACTION_IDX].lower()
        dispatch = {
            "save": self.helper._execute_template_save,
            "create": self.helper._execute_template_create,
            "list": self.helper._execute_template_list,
            "delete": self.helper._execute_template_delete,
        }

        handler = dispatch.get(action)
        if handler:
            await handler(ctx, manager)
        else:
            ctx.console.print("[yellow]Usage: /session template <save|create|list|delete>[/]")

    async def _export(self, ctx: CommandContext) -> None:
        """Export a session."""
        manager = self.helper._get_manager(ctx)
        if manager is not None:
            await self.helper._execute_export(ctx, manager)

    async def _import(self, ctx: CommandContext) -> None:
        """Import a session."""
        manager = self.helper._get_manager(ctx)
        if manager is not None:
            await self.helper._execute_import(ctx, manager)

    async def _list(self, ctx: CommandContext) -> None:
        """List sessions with enhanced information."""
        manager = self.helper._get_manager(ctx)
        if manager is None:
            return

        project_hash = getattr(ctx, "project_hash", None)
        sessions = manager.list_sessions(project_hash)

        if not sessions:
            ctx.console.print("[dim]No saved sessions[/]")
            return

        ctx.console.print("\n[bold blue]Saved Sessions[/]\n")
        self._display_sessions_list(ctx, manager, sessions)

    def _display_sessions_list(
        self,
        ctx: CommandContext,
        manager: SessionManager,
        sessions: list[SessionMetadata]
    ) -> None:
        """Display list of sessions with enhanced information.

        Args:
            ctx: Command context.
            manager: Session manager.
            sessions: List of session metadata.
        """
        params = SessionListParams(
            max_id_display_len=self._ID_DISPLAY_LEN,
            max_date_display_len=self._DATE_DISPLAY_LEN
        )

        for meta in sessions:
            self._display_session_entry(ctx, manager, meta, params)

    def _display_session_entry(
        self,
        ctx: CommandContext,
        manager: SessionManager,
        meta: SessionMetadata,
        params: SessionListParams
    ) -> None:
        """Display a single session entry.

        Args:
            ctx: Command context.
            manager: Session manager.
            meta: Session metadata.
            params: Display parameters.
        """
        try:
            session = manager.load(meta.id)
            self._display_enhanced_session_info(ctx, meta, session, params)
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            self._display_basic_session_info(ctx, meta, params)

    def _display_enhanced_session_info(
        self,
        ctx: CommandContext,
        meta: SessionMetadata,
        session: Session,
        params: SessionListParams
    ) -> None:
        """Display enhanced session information.

        Args:
            ctx: Command context.
            meta: Session metadata.
            session: Full session object.
            params: Display parameters.
        """
        display_line = self.helper._format_session_display(meta, session, params)
        ctx.console.print(display_line)

        details = self.helper._format_session_details(meta, session)
        ctx.console.print(details)
        ctx.console.print("")

    def _display_basic_session_info(
        self,
        ctx: CommandContext,
        meta: SessionMetadata,
        params: SessionListParams
    ) -> None:
        """Display basic session information when enhanced info fails.

        Args:
            ctx: Command context.
            meta: Session metadata.
            params: Display parameters.
        """
        display_line = self.helper._format_session_display(meta, None, params)
        ctx.console.print(display_line)
