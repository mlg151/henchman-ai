"""Built-in slash commands.

This module provides the default slash commands like /help, /quit, /clear, /tools.
"""

from __future__ import annotations

from henchman.cli.commands import Command, CommandContext
from henchman.cli.commands.agent import AgentCommand
from henchman.cli.commands.chat import ChatCommand
from henchman.cli.commands.context import ContextCommand
from henchman.cli.commands.mcp import McpCommand
from henchman.cli.commands.model import ModelCommand
from henchman.cli.commands.plan import PlanCommand
from henchman.cli.commands.rag import RagCommand
from henchman.cli.commands.session import SessionCommand
from henchman.cli.commands.team import TeamCommand
from henchman.cli.commands.theme import ThemeCommand
from henchman.cli.commands.unlimited import UnlimitedCommand


class HelpCommand(Command):
    """Show help information about available commands."""

    @property
    def name(self) -> str:
        """Command name.

        Returns:
            Command name string.
        """
        return "help"

    @property
    def description(self) -> str:
        """Command description.

        Returns:
            Description string.
        """
        return "Show help and available commands"

    @property
    def usage(self) -> str:
        """Command usage.

        Returns:
            Usage string.
        """
        return "/help [command]"

    async def execute(self, ctx: CommandContext) -> None:
        """Execute the help command.

        Args:
            ctx: Command context.
        """
        ctx.console.print("\n[bold blue]Henchman-AI Commands[/]\n")
        ctx.console.print("  /help     - Show this help message")
        ctx.console.print("  /agent    - List or interact with specialist agents")
        ctx.console.print("  /team     - Show team status or reset agents")
        ctx.console.print("  /plan     - Toggle Plan Mode (Read-Only)")
        ctx.console.print("  /rag      - Manage semantic search index")
        ctx.console.print("  /chat     - Manage chat sessions (save, list, resume)")
        ctx.console.print("  /session  - Enhanced session management (branch, merge, templates)")
        ctx.console.print("  /mcp      - Manage MCP server connections")
        ctx.console.print("  /model    - Show or change model/provider")
        ctx.console.print("  /theme    - Manage UI themes (list, set, preview)")
        ctx.console.print("  /context  - Manage intelligent context settings")
        ctx.console.print("  /quit     - Exit the CLI")
        ctx.console.print("  /clear    - Clear the screen")
        ctx.console.print("  /tools    - List available tools")
        ctx.console.print("")


class QuitCommand(Command):
    """Exit the CLI."""

    @property
    def name(self) -> str:
        """Command name.

        Returns:
            Command name string.
        """
        return "quit"

    @property
    def description(self) -> str:
        """Command description.

        Returns:
            Description string.
        """
        return "Exit the CLI"

    @property
    def usage(self) -> str:
        """Command usage.

        Returns:
            Usage string.
        """
        return "/quit"

    async def execute(self, ctx: CommandContext) -> None:
        """Execute the quit command.

        Args:
            ctx: Command context.

        Raises:
            SystemExit: Always raised to exit the CLI.
        """
        ctx.console.print("[dim]Goodbye![/]")
        raise SystemExit(0)


class ClearCommand(Command):
    """Clear the terminal screen."""

    @property
    def name(self) -> str:
        """Command name.

        Returns:
            Command name string.
        """
        return "clear"

    @property
    def description(self) -> str:
        """Command description.

        Returns:
            Description string.
        """
        return "Clear the screen"

    @property
    def usage(self) -> str:
        """Command usage.

        Returns:
            Usage string.
        """
        return "/clear"

    async def execute(self, ctx: CommandContext) -> None:
        """Execute the clear command.

        Args:
            ctx: Command context.
        """
        ctx.console.clear()


class ToolsCommand(Command):
    """List available tools."""

    @property
    def name(self) -> str:
        """Command name.

        Returns:
            Command name string.
        """
        return "tools"

    @property
    def description(self) -> str:
        """Command description.

        Returns:
            Description string.
        """
        return "List available tools"

    @property
    def usage(self) -> str:
        """Command usage.

        Returns:
            Usage string.
        """
        return "/tools"

    async def execute(self, ctx: CommandContext) -> None:
        """Execute the tools command.

        Args:
            ctx: Command context.
        """
        ctx.console.print("\n[bold blue]Available Tools[/]\n")
        # Get tools from registry if available
        if ctx.tool_registry:
            # Get all registered tools
            tool_names = ctx.tool_registry.list_tools()
            tools = []
            for name in tool_names:
                tool = ctx.tool_registry.get(name)
                if tool:
                    tools.append((name, tool.description))
        else:
            # Fallback to hardcoded list for backward compatibility
            tools = [
                ("read_file", "Read file contents"),
                ("write_file", "Write content to a file"),
                ("edit_file", "Edit a file with search/replace"),
                ("ls", "List directory contents"),
                ("glob", "Find files by pattern"),
                ("grep", "Search file contents"),
                ("run_shell_command", "Execute shell commands"),
                ("web_fetch", "Fetch URL contents"),
            ]
        # Sort tools alphabetically by name
        tools.sort(key=lambda x: x[0])
        for name, description in tools:
            ctx.console.print(f"  [cyan]{name}[/] - {description}")
        ctx.console.print("")


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
        PlanCommand(),
        RagCommand(),
        ThemeCommand(),
        UnlimitedCommand(),
        ContextCommand(),
    ]
