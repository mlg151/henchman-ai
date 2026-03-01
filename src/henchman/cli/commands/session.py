"""Enhanced session management command.

This module provides the /session command for advanced session operations
including branching, merging, templates, and export/import.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

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


@dataclass
class CommandOperationContext:
    """Context for command operations to reduce feature envy."""
    console: Any  # Rich console object
    args: list[str]
    session_manager: "SessionManager | None" = None
    project_hash: str | None = None


@dataclass
class SessionDisplayContext:
    """Context for session display operations."""
    meta: "SessionMetadata"
    session: "Session | None" = None
    params: SessionListParams | None = None


class SessionDisplayFormatter:
    """Formats session information for display to reduce feature envy."""
    
    @staticmethod
    def format_session_display(context: SessionDisplayContext) -> str:
        """Format a session for display.

        Args:
            context: Session display context.

        Returns:
            Formatted display string.
        """
        if context.params is None:
            context.params = SessionListParams()

        meta = context.meta
        session = context.session
        params = context.params

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

    @staticmethod
    def format_session_details(meta: "SessionMetadata", session: "Session | None" = None) -> str:
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


class SessionCommandHelper:
    """Helper class for session command operations to reduce class size and feature envy."""

    def __init__(self, command: "SessionCommand"):
        self.command = command
        self.formatter = SessionDisplayFormatter()

    def _get_manager(self, op_context: CommandOperationContext) -> "SessionManager | None":
        """Get session manager from context with error handling.

        Args:
            op_context: Command operation context.

        Returns:
            SessionManager or None if not available.
        """
        manager: SessionManager | None = op_context.session_manager
        if manager is None:
            op_context.console.print("[red]Session manager not available[/]")
        return manager

    def _ensure_args(self, op_context: CommandOperationContext, min_args: int, usage: str) -> bool:
        """Ensure minimum number of arguments.

        Args:
            op_context: Command operation context.
            min_args: Minimum number of arguments required.
            usage: Usage string to show if validation fails.

        Returns:
            True if arguments are valid, False otherwise.
        """
        if len(op_context.args) < min_args:
            op_context.console.print(f"[yellow]Usage: {usage}[/]")
            return False
        return True

    def _parse_merge_arguments(self, op_context: CommandOperationContext) -> tuple[list[str], str, str | None]:
        """Parse merge command arguments.

        Args:
            op_context: Command operation context.

        Returns:
            Tuple of (session_ids, strategy, tag).
        """
        session_ids = [
            op_context.args[self.command._MERGE_ID1_IDX],
            op_context.args[self.command._MERGE_ID2_IDX]
        ]
        strategy = "smart"
        tag = None

        # Parse optional arguments
        if len(op_context.args) > self.command._MERGE_STRATEGY_IDX:
            if op_context.args[self.command._MERGE_STRATEGY_IDX] in ("union", "intersection", "smart"):
                strategy = op_context.args[self.command._MERGE_STRATEGY_IDX]
                if len(op_context.args) > self.command._MERGE_TAG_IDX:
                    tag = op_context.args[self.command._MERGE_TAG_IDX]
            else:
                tag = op_context.args[self.command._MERGE_STRATEGY_IDX]

        return session_ids, strategy, tag

    async def _execute_branch(self, op_context: CommandOperationContext, manager: "SessionManager") -> None:
        """Execute branch operation.

        Args:
            op_context: Command operation context.
            manager: Session manager.
        """
        if not self._ensure_args(
            op_context, 
            DEFAULT_MIN_ARGS_FOR_BRANCH, 
            "/session branch <id> <point> [tag]"
        ):
            return

        session_id = op_context.args[self.command._BRANCH_ID_IDX]
        try:
            branch_point = int(op_context.args[self.command._BRANCH_POINT_IDX])
        except ValueError:
            op_context.console.print("[red]Branch point must be an integer[/]")
            return

        tag = op_context.args[self.command._BRANCH_TAG_IDX] if len(op_context.args) > self.command._BRANCH_TAG_IDX else None

        try:
            branch = manager.branch_session(session_id, branch_point, tag)
            manager.save(branch)
            op_context.console.print(f"[green]✓[/] Created branch: {branch.id}")
            if branch.tag:
                op_context.console.print(f"[dim]Tag: {branch.tag}[/]")
            op_context.console.print(f"[dim]Branch point: {branch_point}, Parent: {session_id}[/]")
        except (FileNotFoundError, ValueError) as e:
            op_context.console.print(f"[red]Error: {e}[/]")

    async def _execute_merge(self, op_context: CommandOperationContext, manager: "SessionManager") -> None:
        """Execute merge operation.

        Args:
            op_context: Command operation context.
            manager: Session manager.
        """
        if not self._ensure_args(
            op_context, 
            DEFAULT_MIN_ARGS_FOR_MERGE, 
            "/session merge <id1> <id2> [strategy] [tag]"
        ):
            return

        session_ids, strategy, tag = self._parse_merge_arguments(op_context)

        try:
            merged = manager.merge_sessions(session_ids, strategy, tag)
            manager.save(merged)
            op_context.console.print(f"[green]✓[/] Created merged session: {merged.id}")
            if merged.tag:
                op_context.console.print(f"[dim]Tag: {merged.tag}[/]")
            op_context.console.print(f"[dim]Strategy: {strategy}, Sources: {', '.join(session_ids)}[/]")
            op_context.console.print(f"[dim]Messages: {len(merged.messages)}[/]")
        except (FileNotFoundError, ValueError) as e:
            op_context.console.print(f"[red]Error: {e}[/]")

    async def _execute_template_save(self, op_context: CommandOperationContext, manager: "SessionManager") -> None:
        """Execute template save operation.

        Args:
            op_context: Command operation context.
            manager: Session manager.
        """
        if not self._ensure_args(
            op_context, 
            DEFAULT_MIN_ARGS_FOR_TEMPLATE_SAVE, 
            "/session template save <id> <name>"
        ):
            return

        session_id = op_context.args[self.command._TEMPLATE_SESSION_ID_IDX]
        name = op_context.args[self.command._TEMPLATE_NAME_IDX]
        description = op_context.args[self.command._TEMPLATE_DESC_IDX] if len(op_context.args) > self.command._TEMPLATE_DESC_IDX else ""

        try:
            template = manager.save_template(session_id, name, description)
            op_context.console.print(f"[green]✓[/] Saved template: {template['name']}")
            op_context.console.print(f"[dim]ID: {template['id']}[/]")
            if description:
                op_context.console.print(f"[dim]Description: {description}[/]")
        except (FileNotFoundError, ValueError) as e:
            op_context.console.print(f"[red]Error: {e}[/]")

    async def _execute_template_create(self, op_context: CommandOperationContext, manager: "SessionManager") -> None:
        """Execute template create operation.

        Args:
            op_context: Command operation context.
            manager: Session manager.
        """
        if not self._ensure_args(
            op_context, 
            DEFAULT_MIN_ARGS_FOR_TEMPLATE_CREATE, 
            "/session template create <template_id> [tag]"
        ):
            return

        template_id = op_context.args[self.command._TEMPLATE_ID_IDX]
        tag = op_context.args[self.command._TEMPLATE_TAG_IDX] if len(op_context.args) > self.command._TEMPLATE_TAG_IDX else None

        try:
            session = manager.create_from_template(template_id, tag=tag)
            manager.save(session)
            op_context.console.print(f"[green]✓[/] Created session from template: {session.id}")
            if session.tag:
                op_context.console.print(f"[dim]Tag: {session.tag}[/]")
            op_context.console.print(f"[dim]Template: {template_id}[/]")
        except (FileNotFoundError, ValueError) as e:
            op_context.console.print(f"[red]Error: {e}[/]")

    async def _execute_template_list(self, op_context: CommandOperationContext, manager: "SessionManager") -> None:
        """Execute template list operation.

        Args:
            op_context: Command operation context.
            manager: Session manager.
        """
        templates = manager.list_templates()

        if not templates:
            op_context.console.print("[dim]No templates available[/]")
            return

        op_context.console.print("\n[bold blue]Available Templates[/]\n")
        for template in templates:
            op_context.console.print(f"  [cyan]{template['name']}[/]")
            op_context.console.print(f"    ID: {template['id']}")
            if template.get('description'):
                op_context.console.print(f"    Description: {template['description']}")
            if template.get('parameters'):
                params = ', '.join(template['parameters'].keys())
                op_context.console.print(f"    Parameters: {params}")
            op_context.console.print(f"    Created: {template.get('created_at', 'unknown')}")
            op_context.console.print("")

    async def _execute_template_delete(self, op_context: CommandOperationContext, manager: "SessionManager") -> None:
        """Execute template delete operation.

        Args:
            op_context: Command operation context.
            manager: Session manager.
        """
        if not self._ensure_args(
            op_context, 
            DEFAULT_MIN_ARGS_FOR_TEMPLATE_DELETE, 
            "/session template delete <template_id>"
        ):
            return

        template_id = op_context.args[self.command._TEMPLATE_ID_IDX]

        try:
            manager.delete_template(template_id)
            op_context.console.print(f"[green]✓[/] Deleted template: {template_id}")
        except FileNotFoundError as e:
            op_context.console.print(f"[red]Error: {e}[/]")

    async def _execute_export(self, op_context: CommandOperationContext, manager: "SessionManager") -> None:
        """Execute export operation.

        Args:
            op_context: Command operation context.
            manager: Session manager.
        """
        if not self._ensure_args(
            op_context, 
            DEFAULT_MIN_ARGS_FOR_EXPORT, 
            "/session export <id> [format]"
        ):
            return

        session_id = op_context.args[self.command._EXPORT_ID_IDX]
        format = op_context.args[self.command._EXPORT_FORMAT_IDX] if len(op_context.args) > self.command._EXPORT_FORMAT_IDX else "json"

        try:
            exported = manager.export_session(session_id, format)

            ext = "json" if format == "json" else "md"
            output_file = Path.cwd() / f"session_{session_id}.{ext}"
            output_file.write_text(exported)

            op_context.console.print(f"[green]✓[/] Exported session to: {output_file}")
            op_context.console.print(f"[dim]Format: {format}, Size: {len(exported)} bytes[/]")
        except (FileNotFoundError, ValueError) as e:
            op_context.console.print(f"[red]Error: {e}[/]")

    async def _execute_import(self, op_context: CommandOperationContext, manager: "SessionManager") -> None:
        """Execute import operation.

        Args:
            op_context: Command operation context.
            manager: Session manager.
        """
        if not self._ensure_args(
            op_context, 
            DEFAULT_MIN_ARGS_FOR_IMPORT, 
            "/session import <file> [format]"
        ):
            return

        file_path = Path(op_context.args[self.command._IMPORT_FILE_IDX])
        if not file_path.exists():
            op_context.console.print(f"[red]File not found: {file_path}[/]")
            return

        format = op_context.args[self.command._IMPORT_FORMAT_IDX] if len(op_context.args) > self.command._IMPORT_FORMAT_IDX else "json"
        tag = op_context.args[self.command._IMPORT_TAG_IDX] if len(op_context.args) > self.command._IMPORT_TAG_IDX else None

        try:
            data = file_path.read_text()
            session = manager.import_session(data, format, tag)
            manager.save(session)

            op_context.console.print(f"[green]✓[/] Imported session: {session.id}")
            if session.tag:
                op_context.console.print(f"[dim]Tag: {session.tag}[/]")
            op_context.console.print(f"[dim]Format: {format}, Messages: {len(session.messages)}[/]")
        except (ValueError, json.JSONDecodeError) as e:
            op_context.console.print(f"[red]Error importing session: {e}[/]")


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

    def _create_operation_context(self, ctx: CommandContext) -> CommandOperationContext:
        """Create operation context from command context.

        Args:
            ctx: Command context.

        Returns:
            Command operation context.
        """
        return CommandOperationContext(
            console=ctx.console,
            args=ctx.args,
            session_manager=getattr(ctx, "session_manager", None),
            project_hash=getattr(ctx, "project_hash", None)
        )

    async def _execute_with_manager(
        self, 
        ctx: CommandContext, 
        executor: Callable[[CommandOperationContext, "SessionManager"], Any]
    ) -> None:
        """Execute operation with manager validation.

        Args:
            ctx: Command context.
            executor: Function to execute with (op_context, manager) parameters.
        """
        op_context = self._create_operation_context(ctx)
        manager = self.helper._get_manager(op_context)
        if manager is not None:
            await executor(op_context, manager)

    async def _branch(self, ctx: CommandContext) -> None:
        """Branch from an existing session."""
        await self._execute_with_manager(ctx, self.helper._execute_branch)

    async def _merge(self, ctx: CommandContext) -> None:
        """Merge multiple sessions."""
        await self._execute_with_manager(ctx, self.helper._execute_merge)

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
        op_context = self._create_operation_context(ctx)
        manager = self.helper._get_manager(op_context)
        if manager is None:
            return

        if not self.helper._ensure_args(
            op_context, 
            DEFAULT_MIN_ARGS_FOR_TEMPLATE, 
            "/session template <save|create|list|delete> [args]"
        ):
            return

        action = op_context.args[self._TEMPLATE_ACTION_IDX].lower()
        dispatch = {
            "save": self.helper._execute_template_save,
            "create": self.helper._execute_template_create,
            "list": self.helper._execute_template_list,
            "delete": self.helper._execute_template_delete,
        }

        handler = dispatch.get(action)
        if handler:
            await handler(op_context, manager)
        else:
            op_context.console.print("[yellow]Usage: /session template <save|create|list|delete>[/]")

    async def _export(self, ctx: CommandContext) -> None:
        """Export a session."""
        await self._execute_with_manager(ctx, self.helper._execute_export)

    async def _import(self, ctx: CommandContext) -> None:
        """Import a session."""
        await self._execute_with_manager(ctx, self.helper._execute_import)

    async def _list(self, ctx: CommandContext) -> None:
        """List sessions with enhanced information."""
        op_context = self._create_operation_context(ctx)
        manager = self.helper._get_manager(op_context)
        if manager is None:
            return

        sessions = manager.list_sessions(op_context.project_hash)

        if not sessions:
            op_context.console.print("[dim]No saved sessions[/]")
            return

        op_context.console.print("\n[bold blue]Saved Sessions[/]\n")
        self._display_sessions_list(op_context, manager, sessions)

    def _display_sessions_list(
        self,
        op_context: CommandOperationContext,
        manager: "SessionManager",
        sessions: list["SessionMetadata"]
    ) -> None:
        """Display list of sessions with enhanced information.

        Args:
            op_context: Command operation context.
            manager: Session manager.
            sessions: List of session metadata.
        """
        params = SessionListParams(
            max_id_display_len=self._ID_DISPLAY_LEN,
            max_date_display_len=self._DATE_DISPLAY_LEN
        )

        for meta in sessions:
            self._display_session_entry(op_context, manager, meta, params)

    def _display_session_entry(
        self,
        op_context: CommandOperationContext,
        manager: "SessionManager",
        meta: "SessionMetadata",
        params: SessionListParams
    ) -> None:
        """Display a single session entry.

        Args:
            op_context: Command operation context.
            manager: Session manager.
            meta: Session metadata.
            params: Display parameters.
        """
        try:
            session = manager.load(meta.id)
            self._display_enhanced_session_info(op_context, meta, session, params)
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            self._display_basic_session_info(op_context, meta, params)

    def _display_enhanced_session_info(
        self,
        op_context: CommandOperationContext,
        meta: "SessionMetadata",
        session: "Session",
        params: SessionListParams
    ) -> None:
        """Display enhanced session information.

        Args:
            op_context: Command operation context.
            meta: Session metadata.
            session: Full session object.
            params: Display parameters.
        """
        display_context = SessionDisplayContext(meta=meta, session=session, params=params)
        display_line = self.helper.formatter.format_session_display(display_context)
        op_context.console.print(display_line)

        details = self.helper.formatter.format_session_details(meta, session)
        op_context.console.print(details)
        op_context.console.print("")

    def _display_basic_session_info(
        self,
        op_context: CommandOperationContext,
        meta: "SessionMetadata",
        params: SessionListParams
    ) -> None:
        """Display basic session information when enhanced info fails.

        Args:
            op_context: Command operation context.
            meta: Session metadata.
            params: Display parameters.
        """
        display_context = SessionDisplayContext(meta=meta, session=None, params=params)
        display_line = self.helper.formatter.format_session_display(display_context)
        op_context.console.print(display_line)
