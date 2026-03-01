"""Enhanced session management command.

This module provides the /session command for advanced session operations
including branching, merging, templates, and export/import.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

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
class DisplayInfo:
    """Parameters for formatting optional session information."""

    condition: str | None
    icon: str
    label: str
    value: str | None
    max_id_len: int

    def format_optional_info(self) -> str:
        """Format optional session information for display.

        Returns:
            Formatted info string or empty string.
        """
        if self.condition and self.value:
            truncated_value = self.value[: self.max_id_len] if self.max_id_len > 0 else self.value
            return f" {self.icon} {self.label}{truncated_value}"
        return ""


@dataclass
class AttributeDisplayInfo:
    """Parameters for formatting session attribute information."""

    condition: str | None
    icon: str
    label: str
    max_id_len: int

    def format_attribute_info(self) -> str:
        """Format session attribute information for display.

        Returns:
            Formatted info string or empty string.
        """
        if self.condition:
            display_info = DisplayInfo(
                condition=self.condition,
                icon=self.icon,
                label=self.label,
                value=self.condition,
                max_id_len=self.max_id_len,
            )
            return display_info.format_optional_info()
        return ""


@dataclass
class MessageStyle:
    """Style configuration for formatted messages."""

    prefix: str
    style: str


# Message style constants
ERROR_MESSAGE_STYLE: MessageStyle = MessageStyle(prefix="Error:", style="red")
USAGE_MESSAGE_STYLE: MessageStyle = MessageStyle(prefix="Usage:", style="yellow")


@dataclass
class CommandOperationContext:
    """Context for command operations to reduce feature envy."""

    console: Console
    args: list[str]
    session_manager: SessionManager | None = None
    project_hash: str | None = None

    def print_success(self, message: str) -> None:
        """Print a success message."""
        self.console.print(f"[green]✓[/] {message}")

    def print_error(self, message: str) -> None:
        """Print an error message."""
        self._print_prefixed_message(message, ERROR_MESSAGE_STYLE)

    def print_info(self, message: str) -> None:
        """Print an info message."""
        self._print_formatted_message(message, "dim")

    def print_usage(self, usage: str) -> None:
        """Print usage information."""
        self._print_prefixed_message(usage, USAGE_MESSAGE_STYLE)

    def _print_formatted_message(self, message: str, style: str) -> None:
        """Print a message with the given style.

        Args:
            message: The message to print.
            style: The Rich style to apply.
        """
        self.console.print(f"[{style}]{message}[/]")

    def _print_prefixed_message(self, message: str, msg_style: MessageStyle) -> None:
        """Print a message with a prefix and style.

        Args:
            message: The message to print.
            msg_style: Message style configuration.
        """
        self._print_formatted_message(f"{msg_style.prefix} {message}", msg_style.style)

    def get_arg(self, index: int, default: str | None = None) -> str | None:
        """Get argument at index or default if out of bounds."""
        if index < len(self.args):
            return self.args[index]
        return default

    def get_arg_or_empty(self, index: int) -> str:
        """Get argument at index or empty string if out of bounds.

        Args:
            index: Argument index.

        Returns:
            Argument value or empty string.
        """
        if index < len(self.args):
            return self.args[index]
        return ""

    def has_min_args(self, min_args: int) -> bool:
        """Check if context has minimum number of arguments.

        Args:
            min_args: Minimum number of arguments required.

        Returns:
            True if minimum arguments are present, False otherwise.
        """
        return len(self.args) >= min_args


@dataclass
class SessionDisplayContext:
    """Context for session display operations."""

    meta: SessionMetadata
    session: Session | None = None
    params: SessionListParams | None = None


@dataclass
class SessionFieldDisplayParams:
    """Parameters for formatting session field information to reduce primitive obsession."""

    field_name: str
    icon: str
    label: str
    max_id_len: int


@dataclass
class SessionAttributeParams:
    """Parameters for formatting session attributes to reduce primitive obsession."""

    condition: str | None
    icon: str
    label: str
    max_id_len: int


class SessionCommandExecutor(ABC):
    """Abstract base class for session command executors."""

    def __init__(self, op_context: CommandOperationContext) -> None:
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
        # Extract values from context to reduce feature envy
        meta = context.meta
        session = context.session
        params = context.params or SessionListParams()

        max_id_len = params.max_id_display_len
        max_date_len = params.max_date_display_len

        tag_display = SessionDisplayFormatter._format_tag_display(meta, max_id_len)

        if session is None:
            return SessionDisplayFormatter._format_basic_session_info(
                tag_display, meta, max_date_len
            )

        branch_info = SessionDisplayFormatter._format_branch_info(session, max_id_len)
        template_info = SessionDisplayFormatter._format_template_info(session, max_id_len)

        return f"  {tag_display}{branch_info}{template_info}"

    @staticmethod
    def _format_tag_display(meta: SessionMetadata, max_id_len: int) -> str:
        """Format the tag/ID display for a session.

        Args:
            meta: Session metadata.
            max_id_len: Maximum ID display length.

        Returns:
            Formatted tag display string.
        """
        if meta.tag:
            return f"[cyan]{meta.tag}[/]"
        else:
            truncated_id = meta.id[:max_id_len] if max_id_len > 0 else meta.id
            return f"[dim]{truncated_id}[/]"

    @staticmethod
    def _format_basic_session_info(
        tag_display: str, meta: SessionMetadata, max_date_len: int
    ) -> str:
        """Format basic session information.

        Args:
            tag_display: Formatted tag display.
            meta: Session metadata.
            max_date_len: Maximum date display length.

        Returns:
            Formatted basic info string.
        """
        truncated_date = meta.last_updated[:max_date_len] if max_date_len > 0 else meta.last_updated
        return f"  {tag_display} - {meta.message_count} messages, updated {truncated_date}"

    @staticmethod
    def _format_session_field_info(
        session: Session, params: SessionFieldDisplayParams
    ) -> str:
        """Format session field information for display.

        Args:
            session: The session object.
            params: Display parameters for the field.

        Returns:
            Formatted field info string or empty string.
        """
        condition = getattr(session, params.field_name, None)
        attr_info = AttributeDisplayInfo(
            condition=condition,
            icon=params.icon,
            label=params.label,
            max_id_len=params.max_id_len
        )
        return attr_info.format_attribute_info()

    @staticmethod
    def _format_field_info(
        session: Session,
        field_name: str,
        icon: str,
        label: str,
        max_id_len: int
    ) -> str:
        """Format field information for display.

        Args:
            session: The session object.
            field_name: Name of the field to check.
            icon: Icon to display.
            label: Label text.
            max_id_len: Maximum ID display length.

        Returns:
            Formatted field info string.
        """
        params = SessionFieldDisplayParams(
            field_name=field_name,
            icon=icon,
            label=label,
            max_id_len=max_id_len,
        )
        return SessionDisplayFormatter._format_session_field_info(session, params)

    @staticmethod
    def _format_branch_info(session: Session, max_id_len: int) -> str:
        """Format branch information for display.

        Args:
            session: The session object.
            max_id_len: Maximum ID display length.

        Returns:
            Formatted branch info string.
        """
        return SessionDisplayFormatter._format_field_info(
            session=session,
            field_name="parent_id",
            icon="[yellow]↳[/]",
            label="branch from",
            max_id_len=max_id_len,
        )

    @staticmethod
    def _format_template_info(session: Session, max_id_len: int) -> str:
        """Format template information for display.

        Args:
            session: The session object.
            max_id_len: Maximum ID display length.

        Returns:
            Formatted template info string.
        """
        return SessionDisplayFormatter._format_field_info(
            session=session,
            field_name="template_id",
            icon="[magenta]ⓣ[/]",
            label="template:",
            max_id_len=max_id_len,
        )

    @staticmethod
    def _format_session_attribute_info(params: SessionAttributeParams) -> str:
        """Format a session attribute for display.

        Args:
            params: Display parameters for the attribute.

        Returns:
            Formatted attribute info string or empty string.
        """
        attr_info = AttributeDisplayInfo(
            condition=params.condition,
            icon=params.icon,
            label=params.label,
            max_id_len=params.max_id_len
        )
        return attr_info.format_attribute_info()

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

    def __init__(self, command: SessionCommand) -> None:
        """Initialize the session command helper.

        Args:
            command: The parent session command.
        """
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

        # Map subcommands to their executor classes
        executor_map: dict[str, type[SessionCommandExecutor]] = {
            "branch": BranchExecutor,
            "merge": MergeExecutor,
            "export": ExportExecutor,
            "import": ImportExecutor,
        }

        executor_class = executor_map.get(subcommand)
        if executor_class:
            await self._execute_with_executor_class(ctx, executor_class)
        elif subcommand == "template":
            await self._template(ctx)
        elif subcommand == "list":
            await self._list(ctx)
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

    async def _execute_with_executor_class(
        self, ctx: CommandContext, executor_class: type[SessionCommandExecutor]
    ) -> None:
        """Execute a command with the given executor class.

        Args:
            ctx: Command context.
            executor_class: The executor class to instantiate.
        """
        op_context = self._create_operation_context(ctx)
        await self.helper._execute_with_executor(op_context, executor_class)

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
