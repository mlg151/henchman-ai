"""Enhanced session management command.

This module provides the /session command for advanced session operations
including branching, merging, templates, and export/import.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

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
    session_manager: SessionManager | None = None
    project_hash: str | None = None

    def print_success(self, message: str) -> None:
        """Print a success message."""
        self.console.print(f"[green]✓[/] {message}")

    def print_error(self, message: str) -> None:
        """Print an error message."""
        self.console.print(f"[red]Error: {message}[/]")

    def print_info(self, message: str) -> None:
        """Print an info message."""
        self.console.print(f"[dim]{message}[/]")

    def print_usage(self, usage: str) -> None:
        """Print usage information."""
        self.console.print(f"[yellow]Usage: {usage}[/]")

    def get_arg(self, index: int, default: str | None = None) -> str | None:
        """Get argument at index or default if out of bounds."""
        if index < len(self.args):
            return self.args[index]
        return default

    def get_arg_or_empty(self, index: int) -> str:
        """Get argument at index or empty string if out of bounds."""
        if index < len(self.args):
            return self.args[index]
        return ""

    def has_min_args(self, min_args: int) -> bool:
        """Check if context has minimum number of arguments."""
        return len(self.args) >= min_args


@dataclass
class SessionDisplayContext:
    """Context for session display operations."""

    meta: SessionMetadata
    session: Session | None = None
    params: SessionListParams | None = None


class SessionCommandExecutor(ABC):
    """Abstract base class for session command executors."""

    def __init__(self, op_context: CommandOperationContext):
        self.op_context = op_context

    @abstractmethod
    async def execute(self, manager: SessionManager) -> None:
        """Execute the command with the given manager."""
        pass

    def _ensure_args(self, min_args: int, usage: str) -> bool:
        """Ensure minimum number of arguments.

        Args:
            min_args: Minimum number of arguments required.
            usage: Usage string to show if validation fails.

        Returns:
            True if arguments are valid, False otherwise.
        """
        if not self.op_context.has_min_args(min_args):
            self.op_context.print_usage(usage)
            return False
        return True


class BranchExecutor(SessionCommandExecutor):
    """Executor for branch operations."""

    async def execute(self, manager: SessionManager) -> None:
        """Execute branch operation."""
        if not self._ensure_args(DEFAULT_MIN_ARGS_FOR_BRANCH, "/session branch <id> <point> [tag]"):
            return

        session_id = self.op_context.get_arg(1)
        branch_point_str = self.op_context.get_arg(2)
        tag = self.op_context.get_arg(3)

        if not session_id or not branch_point_str:
            self.op_context.print_usage("/session branch <id> <point> [tag]")
            return

        try:
            branch_point = int(branch_point_str)
        except ValueError:
            self.op_context.print_error("Branch point must be an integer")
            return

        try:
            branch = manager.branch_session(session_id, branch_point, tag)
            manager.save(branch)
            self.op_context.print_success(f"Created branch: {branch.id}")
            if branch.tag:
                self.op_context.print_info(f"Tag: {branch.tag}")
            self.op_context.print_info(f"Branch point: {branch_point}, Parent: {session_id}")
        except (FileNotFoundError, ValueError) as e:
            self.op_context.print_error(str(e))


class MergeExecutor(SessionCommandExecutor):
    """Executor for merge operations."""

    def _parse_merge_arguments(self) -> tuple[list[str], str, str | None]:
        """Parse merge command arguments.

        Returns:
            Tuple of (session_ids, strategy, tag).
        """
        session_id1 = self.op_context.get_arg(1)
        session_id2 = self.op_context.get_arg(2)

        if not session_id1 or not session_id2:
            return [], "smart", None

        session_ids = [session_id1, session_id2]
        strategy = "smart"
        tag = None

        # Parse optional arguments
        strategy_arg = self.op_context.get_arg(3)
        tag_arg = self.op_context.get_arg(4)

        if strategy_arg in ("union", "intersection", "smart"):
            strategy = strategy_arg
            if tag_arg:
                tag = tag_arg
        elif strategy_arg:
            tag = strategy_arg

        return session_ids, strategy, tag

    async def execute(self, manager: SessionManager) -> None:
        """Execute merge operation."""
        if not self._ensure_args(
            DEFAULT_MIN_ARGS_FOR_MERGE, "/session merge <id1> <id2> [strategy] [tag]"
        ):
            return

        session_ids, strategy, tag = self._parse_merge_arguments()

        try:
            merged = manager.merge_sessions(session_ids, strategy, tag)
            manager.save(merged)
            self.op_context.print_success(f"Created merged session: {merged.id}")
            if merged.tag:
                self.op_context.print_info(f"Tag: {merged.tag}")
            self.op_context.print_info(f"Strategy: {strategy}, Sources: {', '.join(session_ids)}")
            self.op_context.print_info(f"Messages: {len(merged.messages)}")
        except (FileNotFoundError, ValueError) as e:
            self.op_context.print_error(str(e))


class TemplateSaveExecutor(SessionCommandExecutor):
    """Executor for template save operations."""

    async def execute(self, manager: SessionManager) -> None:
        """Execute template save operation."""
        if not self._ensure_args(
            DEFAULT_MIN_ARGS_FOR_TEMPLATE_SAVE, "/session template save <id> <name>"
        ):
            return

        session_id = self.op_context.get_arg(2)
        name = self.op_context.get_arg(3)
        description = self.op_context.get_arg_or_empty(4)

        if not session_id or not name:
            self.op_context.print_usage("/session template save <id> <name>")
            return

        try:
            template = manager.save_template(session_id, name, description)
            self.op_context.print_success(f"Saved template: {template['name']}")
            self.op_context.print_info(f"ID: {template['id']}")
            if description:
                self.op_context.print_info(f"Description: {description}")
        except (FileNotFoundError, ValueError) as e:
            self.op_context.print_error(str(e))


class TemplateCreateExecutor(SessionCommandExecutor):
    """Executor for template create operations."""

    async def execute(self, manager: SessionManager) -> None:
        """Execute template create operation."""
        if not self._ensure_args(
            DEFAULT_MIN_ARGS_FOR_TEMPLATE_CREATE, "/session template create <template_id> [tag]"
        ):
            return

        template_id = self.op_context.get_arg(2)
        tag = self.op_context.get_arg(3)

        if not template_id:
            self.op_context.print_usage("/session template create <template_id> [tag]")
            return

        try:
            session = manager.create_from_template(template_id, tag=tag)
            manager.save(session)
            self.op_context.print_success(f"Created session from template: {session.id}")
            if session.tag:
                self.op_context.print_info(f"Tag: {session.tag}")
            self.op_context.print_info(f"Template: {template_id}")
        except (FileNotFoundError, ValueError) as e:
            self.op_context.print_error(str(e))


class TemplateListExecutor(SessionCommandExecutor):
    """Executor for template list operations."""

    async def execute(self, manager: SessionManager) -> None:
        """Execute template list operation."""
        templates = manager.list_templates()

        if not templates:
            self.op_context.print_info("No templates available")
            return

        self.op_context.console.print("\n[bold blue]Available Templates[/]\n")
        for template in templates:
            self.op_context.console.print(f"  [cyan]{template['name']}[/]")
            self.op_context.console.print(f"    ID: {template['id']}")
            if template.get("description"):
                self.op_context.console.print(f"    Description: {template['description']}")
            if template.get("parameters"):
                params = ", ".join(template["parameters"].keys())
                self.op_context.console.print(f"    Parameters: {params}")
            self.op_context.console.print(f"    Created: {template.get('created_at', 'unknown')}")
            self.op_context.console.print("")


class TemplateDeleteExecutor(SessionCommandExecutor):
    """Executor for template delete operations."""

    async def execute(self, manager: SessionManager) -> None:
        """Execute template delete operation."""
        if not self._ensure_args(
            DEFAULT_MIN_ARGS_FOR_TEMPLATE_DELETE, "/session template delete <template_id>"
        ):
            return

        template_id = self.op_context.get_arg(2)

        if not template_id:
            self.op_context.print_usage("/session template delete <template_id>")
            return

        try:
            manager.delete_template(template_id)
            self.op_context.print_success(f"Deleted template: {template_id}")
        except FileNotFoundError as e:
            self.op_context.print_error(str(e))


class ExportExecutor(SessionCommandExecutor):
    """Executor for export operations."""

    async def execute(self, manager: SessionManager) -> None:
        """Execute export operation."""
        if not self._ensure_args(DEFAULT_MIN_ARGS_FOR_EXPORT, "/session export <id> [format]"):
            return

        session_id = self.op_context.get_arg(1)
        format_arg = self.op_context.get_arg(2, "json")
        format = format_arg if format_arg else "json"

        if not session_id:
            self.op_context.print_usage("/session export <id> [format]")
            return

        try:
            exported = manager.export_session(session_id, format)

            ext = "json" if format == "json" else "md"
            output_file = Path.cwd() / f"session_{session_id}.{ext}"
            output_file.write_text(exported)

            self.op_context.print_success(f"Exported session to: {output_file}")
            self.op_context.print_info(f"Format: {format}, Size: {len(exported)} bytes")
        except (FileNotFoundError, ValueError) as e:
            self.op_context.print_error(str(e))


class ImportExecutor(SessionCommandExecutor):
    """Executor for import operations."""

    async def execute(self, manager: SessionManager) -> None:
        """Execute import operation."""
        if not self._ensure_args(DEFAULT_MIN_ARGS_FOR_IMPORT, "/session import <file> [format]"):
            return

        file_path_str = self.op_context.get_arg(1)
        format_arg = self.op_context.get_arg(2, "json")
        format = format_arg if format_arg else "json"
        tag = self.op_context.get_arg(3)

        if not file_path_str:
            self.op_context.print_usage("/session import <file> [format]")
            return

        file_path = Path(file_path_str)
        if not file_path.exists():
            self.op_context.print_error(f"File not found: {file_path}")
            return

        try:
            data = file_path.read_text()
            session = manager.import_session(data, format, tag)
            manager.save(session)

            self.op_context.print_success(f"Imported session: {session.id}")
            if session.tag:
                self.op_context.print_info(f"Tag: {session.tag}")
            self.op_context.print_info(f"Format: {format}, Messages: {len(session.messages)}")
        except (ValueError, json.JSONDecodeError) as e:
            self.op_context.print_error(f"Error importing session: {e}")


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

        tag_display = (
            f"[cyan]{meta.tag}[/]"
            if meta.tag
            else f"[dim]{meta.id[: params.max_id_display_len]}[/]"
        )

        if session is None:
            return (
                f"  {tag_display} - {meta.message_count} messages, "
                f"updated {meta.last_updated[: params.max_date_display_len]}"
            )

        branch_info = ""
        template_info = ""

        if session.parent_id:
            branch_info = (
                f" [yellow]↳[/] branch from {session.parent_id[: params.max_id_display_len]}"
            )
        if session.template_id:
            template_info = (
                f" [magenta]ⓣ[/] template:{session.template_id[: params.max_id_display_len]}"
            )

        return f"  {tag_display}{branch_info}{template_info}"

    @staticmethod
    def format_session_details(meta: SessionMetadata, session: Session | None = None) -> str:
        """Format session details for display.

        Args:
            meta: Session metadata.
            session: Optional full session object for enhanced info.

        Returns:
            Formatted details string.
        """
        details = f"    Messages: {meta.message_count}, Updated: {meta.last_updated[:DEFAULT_DATE_DISPLAY_LENGTH]}"

        if session and session.export_metadata and "merged_from" in session.export_metadata:
            details += (
                f"\n    [dim]Merged from {len(session.export_metadata['merged_from'])} sessions[/]"
            )

        return details


class SessionCommandHelper:
    """Helper class for session command operations to reduce class size and feature envy."""

    def __init__(self, command: SessionCommand):
        self.command = command
        self.formatter = SessionDisplayFormatter()

    def _get_manager(self, op_context: CommandOperationContext) -> SessionManager | None:
        """Get session manager from context with error handling.

        Args:
            op_context: Command operation context.

        Returns:
            SessionManager or None if not available.
        """
        manager: SessionManager | None = op_context.session_manager
        if manager is None:
            op_context.print_error("Session manager not available")
        return manager

    async def _execute_with_executor(
        self, op_context: CommandOperationContext, executor_class: type[SessionCommandExecutor]
    ) -> None:
        """Execute operation with executor pattern.

        Args:
            op_context: Command operation context.
            executor_class: Executor class to instantiate.
        """
        manager = self._get_manager(op_context)
        if manager is not None:
            executor = executor_class(op_context)
            await executor.execute(manager)


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
            project_hash=getattr(ctx, "project_hash", None),
        )

    async def _branch(self, ctx: CommandContext) -> None:
        """Branch from an existing session."""
        op_context = self._create_operation_context(ctx)
        await self.helper._execute_with_executor(op_context, BranchExecutor)

    async def _merge(self, ctx: CommandContext) -> None:
        """Merge multiple sessions."""
        op_context = self._create_operation_context(ctx)
        await self.helper._execute_with_executor(op_context, MergeExecutor)

    async def _template(self, ctx: CommandContext) -> None:
        """Template operations."""
        op_context = self._create_operation_context(ctx)

        if not op_context.has_min_args(DEFAULT_MIN_ARGS_FOR_TEMPLATE):
            op_context.print_usage("/session template <save|create|list|delete> [args]")
            return

        action_arg = op_context.get_arg(1, "")
        action = action_arg.lower() if action_arg else ""
        executor_map: dict[str, type[SessionCommandExecutor]] = {
            "save": TemplateSaveExecutor,
            "create": TemplateCreateExecutor,
            "list": TemplateListExecutor,
            "delete": TemplateDeleteExecutor,
        }

        executor_class = executor_map.get(action)
        if executor_class:
            await self.helper._execute_with_executor(op_context, executor_class)
        else:
            op_context.print_usage("/session template <save|create|list|delete>")

    async def _export(self, ctx: CommandContext) -> None:
        """Export a session."""
        op_context = self._create_operation_context(ctx)
        await self.helper._execute_with_executor(op_context, ExportExecutor)

    async def _import(self, ctx: CommandContext) -> None:
        """Import a session."""
        op_context = self._create_operation_context(ctx)
        await self.helper._execute_with_executor(op_context, ImportExecutor)

    async def _list(self, ctx: CommandContext) -> None:
        """List sessions with enhanced information."""
        op_context = self._create_operation_context(ctx)
        manager = self.helper._get_manager(op_context)
        if manager is None:
            return

        sessions = manager.list_sessions(op_context.project_hash)

        if not sessions:
            op_context.print_info("No saved sessions")
            return

        op_context.console.print("\n[bold blue]Saved Sessions[/]\n")
        self._display_sessions_list(op_context, manager, sessions)

    def _display_sessions_list(
        self,
        op_context: CommandOperationContext,
        manager: SessionManager,
        sessions: list[SessionMetadata],
    ) -> None:
        """Display list of sessions with enhanced information.

        Args:
            op_context: Command operation context.
            manager: Session manager.
            sessions: List of session metadata.
        """
        params = SessionListParams(
            max_id_display_len=DEFAULT_ID_DISPLAY_LENGTH,
            max_date_display_len=DEFAULT_DATE_DISPLAY_LENGTH,
        )

        for meta in sessions:
            self._display_session_entry(op_context, manager, meta, params)

    def _display_session_entry(
        self,
        op_context: CommandOperationContext,
        manager: SessionManager,
        meta: SessionMetadata,
        params: SessionListParams,
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
        meta: SessionMetadata,
        session: Session,
        params: SessionListParams,
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
        meta: SessionMetadata,
        params: SessionListParams,
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
