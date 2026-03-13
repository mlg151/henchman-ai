"""Slash command system for the CLI.

This module provides command parsing, registration, and execution.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

from henchman.utils.registry import Registry

if TYPE_CHECKING:
    from rich.console import Console

    from henchman.cli.repl import Repl
    from henchman.config import Settings
    from henchman.core import Agent
    from henchman.core.session import Session
    from henchman.mcp.manager import McpManager
    from henchman.tools.registry import ToolRegistry


def parse_command(input_text: str) -> tuple[str, list[str]] | None:
    """Parse a slash command from input text.

    Args:
        input_text: User input string.

    Returns:
        Tuple of (command_name, args) or None if not a command.
    """
    if not input_text.startswith("/"):
        return None

    stripped = input_text[1:].strip()
    if not stripped:
        return None

    parts = stripped.split()
    return parts[0], parts[1:]


@dataclass
class CommandContext:
    """Context passed to command execution.

    Attributes:
        console: Rich Console for output.
        args: Command arguments.
        settings: Application settings.
        agent: Agent instance if available.
        tool_registry: ToolRegistry instance if available.
        session: Current Session if available.
        repl: REPL instance if available.
        registry: CommandRegistry instance if available.
    """

    console: Console
    args: list[str] = field(default_factory=list)
    settings: Settings | None = None
    agent: Agent | None = None
    tool_registry: ToolRegistry | None = None
    session: Session | None = None
    repl: Repl | None = None
    session_manager: object | None = None
    project_hash: str | None = None
    mcp_manager: McpManager | None = None
    registry: CommandRegistry | None = None


class Command(ABC):
    """Abstract base class for slash commands."""

    @property
    @abstractmethod
    def name(self: Command) -> str:
        """Command name (without slash).

        Returns:
            Command name string.
        """

    @property
    @abstractmethod
    def description(self: Command) -> str:
        """Short description of the command.

        Returns:
            Description string.
        """

    @property
    @abstractmethod
    def usage(self: Command) -> str:
        """Usage string showing command syntax.

        Returns:
            Usage string.
        """

    @abstractmethod
    async def execute(self: Command, ctx: CommandContext) -> None:
        """Execute the command.

        Args:
            ctx: Command context with console and arguments.

        Returns:
            None
        """


class BaseCommand(Command):
    """Base class for commands with standardized help display.

    This class eliminates duplicate _show_help methods by providing
    a standard implementation that uses class attributes.
    """

    # Subclasses must override these
    _help_command_name: str = ""
    _help_lines: ClassVar[list[str]] = []

    async def _show_help(self: BaseCommand, ctx: CommandContext) -> None:
        """Show help for this command.

        Args:
            ctx: Command context.
        """
        if not self._help_command_name or not self._help_lines:
            msg = f"{self.__class__.__name__} must define _help_command_name and _help_lines"
            raise NotImplementedError(
                msg,
            )
        show_command_help(ctx, self._help_command_name, self._help_lines)


class CommandRegistry(Registry["Command"]):
    """Registry for slash commands."""

    def __init__(self: CommandRegistry) -> None:
        """Initialize a command registry with duplicate prevention enabled."""
        super().__init__(prevent_duplicates=True)

    def register(self: CommandRegistry, command: Command) -> None:  # type: ignore[override]
        """Register a command.

        Args:
            command: Command to register.

        Raises:
            ValueError: If a command with the same name is already registered.

        Returns:
            None
        """
        try:
            # Duplicate checking is now handled by the base class
            super().register(command.name, command)
        except ValueError as e:
            # Convert generic "Item" error to "Command" error for backward compatibility
            if "Item" in str(e) and "already registered" in str(e):
                name = command.name
                raise ValueError(f"Command '{name}' is already registered") from e
            raise

    def get_commands(self: CommandRegistry) -> list[Command]:
        """Get all registered commands sorted alphabetically by name.

        Returns:
            List of registered command objects, sorted by command name.
        """
        return self.get_sorted_items(key=lambda cmd: cmd.name)

    async def execute(self: CommandRegistry, name: str, ctx: CommandContext) -> None:
        """Execute a command by name.

        Args:
            name: Command name.
            ctx: Command context.

        Raises:
            KeyError: If command not found.

        Returns:
            None
        """
        cmd = self.get(name)
        if cmd is None:
            msg = f"Unknown command: {name}"
            raise KeyError(msg)
        await cmd.execute(ctx)


def show_command_help(
    ctx: CommandContext,
    command_name: str,
    help_lines: list[str],
) -> None:
    """Display formatted help for a command.

    This helper function standardizes the display of command help
    to eliminate duplicate code across command classes.

    Args:
        ctx: Command context with console.
        command_name: Name of the command for the header.
        help_lines: List of help lines to display.

    Returns:
        None
    """
    ctx.console.print(f"\n[bold blue]{command_name} Commands[/]\n")
    for line in help_lines:
        ctx.console.print(line)
    ctx.console.print("")
