"""Slash command system for the CLI.

This module provides command parsing, registration, and execution.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

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


class Command(ABC):
    """Abstract base class for slash commands."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Command name (without slash).

        Returns:
            Command name string.
        """

    @property
    @abstractmethod
    def description(self) -> str:
        """Short description of the command.

        Returns:
            Description string.
        """

    @property
    @abstractmethod
    def usage(self) -> str:
        """Usage string showing command syntax.

        Returns:
            Usage string.
        """

    @abstractmethod
    async def execute(self, ctx: CommandContext) -> None:
        """Execute the command.

        Args:
            ctx: Command context with console and arguments.
        """


class CommandRegistry:
    """Registry for slash commands."""

    def __init__(self) -> None:
        """Initialize an empty command registry."""
        self._commands: dict[str, Command] = {}

    def register(self, command: Command) -> None:
        """Register a command.

        Args:
            command: Command to register.
        """
        self._commands[command.name] = command

    def get(self, name: str) -> Command | None:
        """Get a command by name.

        Args:
            name: Command name.

        Returns:
            Command or None if not found.
        """
        return self._commands.get(name)

    def get_commands(self) -> list[Command]:
        """Get all registered commands.

        Returns:
            List of registered command objects.
        """
        return list(self._commands.values())

    def list_commands(self) -> list[str]:
        """List all registered command names.

        Returns:
            List of command names.
        """
        return list(self._commands.keys())

    async def execute(self, name: str, ctx: CommandContext) -> None:
        """Execute a command by name.

        Args:
            name: Command name.
            ctx: Command context.

        Raises:
            KeyError: If command not found.
        """
        cmd = self.get(name)
        if cmd is None:
            raise KeyError(f"Unknown command: {name}")
        await cmd.execute(ctx)


def show_command_help(ctx: CommandContext, command_name: str, help_lines: list[str]) -> None:
    """Display formatted help for a command.

    This helper function standardizes the display of command help
    to eliminate duplicate code across command classes.

    Args:
        ctx: Command context with console.
        command_name: Name of the command for the header.
        help_lines: List of help lines to display.
    """
    ctx.console.print(f"\n[bold blue]{command_name} Commands[/]\n")
    for line in help_lines:
        ctx.console.print(line)
    ctx.console.print("")
