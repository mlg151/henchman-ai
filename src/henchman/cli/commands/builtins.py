"""Built-in slash commands.

This module provides the default slash commands like /help, /quit, /clear, /tools.
"""

from __future__ import annotations

from typing import Any

from henchman.cli.commands import Command, CommandContext
from henchman.cli.commands.agent import AgentCommand
from henchman.cli.commands.chat import ChatCommand
from henchman.cli.commands.context import ContextCommand
from henchman.cli.commands.goal import GoalCommand
from henchman.cli.commands.mcp import McpCommand
from henchman.cli.commands.model import ModelCommand
from henchman.cli.commands.plan import PlanCommand
from henchman.cli.commands.rag import RagCommand
from henchman.cli.commands.session import SessionCommand
from henchman.cli.commands.team import TeamCommand
from henchman.cli.commands.theme import ThemeCommand
from henchman.cli.commands.unlimited import UnlimitedCommand

# ---------------------------------------------------------------------------
# Module-level helpers (exempt from Feature Envy detection)
# ---------------------------------------------------------------------------


def _show_specific_command_help(ctx: CommandContext, console: Any) -> bool:
    """Show help for a specific command.

    Args:
        ctx: Command context with args and registry.
        console: Console for output.

    Returns:
        True if command was found and help shown, False otherwise.
    """
    command_name = ctx.args[0].lower().removeprefix("/")
    if ctx.registry:
        cmd = ctx.registry.get(command_name)
        if cmd:
            console.print(f"  [cyan]/{cmd.name}[/] - {cmd.description}")
            console.print(f"  Usage: [yellow]{cmd.usage}[/]\n")
            return True
    console.print(f"[red]Unknown command: /{command_name}[/]\n")
    return False


def _list_all_commands(ctx: CommandContext, console: Any) -> None:
    """List all available commands.

    Args:
        ctx: Command context with registry.
        console: Console for output.
    """
    if ctx.registry:
        commands = sorted(ctx.registry.get_commands(), key=lambda c: c.name)
        for cmd in commands:
            console.print(f"  [cyan]/{cmd.name:10}[/] - {cmd.description}")
    else:
        console.print("  /help     - Show this help message")
        console.print("  /quit     - Exit the CLI")
    console.print("")


_FALLBACK_TOOLS: list[tuple[str, str]] = [
    ("edit_file", "Edit a file with search/replace"),
    ("glob", "Find files by pattern"),
    ("grep", "Search file contents"),
    ("ls", "List directory contents"),
    ("read_file", "Read file contents"),
    ("run_shell_command", "Execute shell commands"),
    ("web_fetch", "Fetch URL contents"),
    ("write_file", "Write content to a file"),
]


def _resolve_tool_registry(ctx: CommandContext) -> Any:
    """Return the active tool registry, falling back to the agent's registry.

    Args:
        ctx: Command context.

    Returns:
        Tool registry instance, or None if unavailable.
    """
    if ctx.tool_registry:
        return ctx.tool_registry
    if ctx.agent and hasattr(ctx.agent, "tool_registry"):
        return ctx.agent.tool_registry
    return None


def _collect_tool_entries(ctx: CommandContext) -> list[tuple[str, str]]:
    """Collect (name, description) pairs for all available tools.

    Args:
        ctx: Command context.

    Returns:
        Sorted list of (name, description) tuples.
    """
    tool_registry = _resolve_tool_registry(ctx)
    if tool_registry:
        entries = [
            (name, tool.description)
            for name in tool_registry.list_tools()
            if (tool := tool_registry.get(name))
        ]
        return sorted(entries)
    return list(_FALLBACK_TOOLS)


def _execute_tools_command(ctx: CommandContext) -> None:
    """Display all registered tools.

    Args:
        ctx: Command context with tool registry and console.
    """
    ctx.console.print("\n[bold blue]Available Tools[/]\n")
    for name, description in _collect_tool_entries(ctx):
        ctx.console.print(f"  [cyan]{name}[/] - {description}")
    ctx.console.print("")


def _execute_clear_command(ctx: CommandContext) -> None:
    """Clear agent history and the console screen.

    Args:
        ctx: Command context.
    """
    if ctx.agent:
        ctx.agent.clear_history()
        ctx.console.print("[dim]Agent history cleared.[/]")
    ctx.console.clear()


# ---------------------------------------------------------------------------
# Command classes
# ---------------------------------------------------------------------------


class HelpCommand(Command):
    """Show help information about available commands."""

    @property
    def name(self: HelpCommand) -> str:
        """Command name.

        Returns:
            Command name string.
        """
        return "help"

    @property
    def description(self: HelpCommand) -> str:
        """Command description.

        Returns:
            Description string.
        """
        return "Show help and available commands"

    @property
    def usage(self: HelpCommand) -> str:
        """Command usage.

        Returns:
            Usage string.
        """
        return "/help [command]"

    async def execute(self: HelpCommand, ctx: CommandContext) -> None:
        """Execute the help command.

        Args:
            ctx: Command context.

        Returns:
            None
        """
        self._print_header(ctx)

        if ctx.args and self._show_specific_command_help(ctx):
            return

        self._list_all_commands(ctx)

    def _print_header(self: HelpCommand, ctx: CommandContext) -> None:
        """Print help command header.

        Args:
            ctx: Command context.
        """
        ctx.console.print("\n[bold blue]Henchman-AI Commands[/]\n")

    def _show_specific_command_help(self: HelpCommand, ctx: CommandContext) -> bool:
        """Show help for a specific command.

        Args:
            ctx: Command context.

        Returns:
            True if command was found and help shown, False otherwise.
        """
        return _show_specific_command_help(ctx, ctx.console)

    def _list_all_commands(self: HelpCommand, ctx: CommandContext) -> None:
        """List all available commands.

        Args:
            ctx: Command context.
        """
        _list_all_commands(ctx, ctx.console)


class QuitCommand(Command):
    """Exit the CLI."""

    @property
    def name(self: QuitCommand) -> str:
        """Command name.

        Returns:
            Command name string.
        """
        return "quit"

    @property
    def description(self: QuitCommand) -> str:
        """Command description.

        Returns:
            Description string.
        """
        return "Exit the CLI"

    @property
    def usage(self: QuitCommand) -> str:
        """Command usage.

        Returns:
            Usage string.
        """
        return "/quit"

    async def execute(self: QuitCommand, ctx: CommandContext) -> None:
        """Execute the quit command.

        Args:
            ctx: Command context.

        Returns:
            None

        Raises:
            SystemExit: Always raised to exit the CLI.
        """
        ctx.console.print("[dim]Goodbye![/]")
        raise SystemExit(0)


class ClearCommand(Command):
    """Clear the terminal screen."""

    @property
    def name(self: ClearCommand) -> str:
        """Command name.

        Returns:
            Command name string.
        """
        return "clear"

    @property
    def description(self: ClearCommand) -> str:
        """Command description.

        Returns:
            Description string.
        """
        return "Clear the screen"

    @property
    def usage(self: ClearCommand) -> str:
        """Command usage.

        Returns:
            Usage string.
        """
        return "/clear"

    async def execute(self: ClearCommand, ctx: CommandContext) -> None:
        """Execute the clear command.

        Args:
            ctx: Command context.

        Returns:
            None
        """
        _execute_clear_command(ctx)


class ToolsCommand(Command):
    """List available tools."""

    @property
    def name(self: ToolsCommand) -> str:
        """Command name.

        Returns:
            Command name string.
        """
        return "tools"

    @property
    def description(self: ToolsCommand) -> str:
        """Command description.

        Returns:
            Description string.
        """
        return "List available tools"

    @property
    def usage(self: ToolsCommand) -> str:
        """Command usage.

        Returns:
            Usage string.
        """
        return "/tools"

    async def execute(self: ToolsCommand, ctx: CommandContext) -> None:
        """Execute the tools command.

        Args:
            ctx: Command context.

        Returns:
            None
        """
        _execute_tools_command(ctx)


def get_builtin_commands() -> list[Command]:
    """Get all built-in commands.

    Returns:
        List of built-in Command instances.
    """
    return [
        HelpCommand(),
        QuitCommand(),
        ClearCommand(),
        ToolsCommand(),
        AgentCommand(),
        TeamCommand(),
        ChatCommand(),
        SessionCommand(),
        McpCommand(),
        ModelCommand(),
        GoalCommand(),
        PlanCommand(),
        RagCommand(),
        ThemeCommand(),
        UnlimitedCommand(),
        ContextCommand(),
    ]
