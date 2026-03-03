"""MCP server management command.

This module provides the /mcp command for listing and managing MCP servers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from henchman.cli.commands import BaseCommand, CommandContext
from henchman.cli.console_helpers import ConsoleHelper
from henchman.config import load_settings

if TYPE_CHECKING:
    from henchman.mcp.manager import McpManager


class McpCommand(BaseCommand):
    """/mcp command for MCP server management."""

    _MAX_TOOLS_DISPLAY = 10
    _MIN_LOGGING_ARGS = 2

    _help_command_name = "MCP Server"
    _help_lines: ClassVar[list[str]] = [
        "  /mcp list      - List configured MCP servers",
        "  /mcp status    - Show connection status and tools",
        "  /mcp logging   - Control MCP logging (on/off/status)",
    ]

    @property
    def name(self) -> str:
        """Command name.

        Returns:
            Command name string.
        """
        return "mcp"

    @property
    def description(self) -> str:
        """Command description.

        Returns:
            Description string.
        """
        return "Manage MCP server connections"

    @property
    def usage(self) -> str:
        """Command usage.

        Returns:
            Usage string.
        """
        return "/mcp <list|status|logging>"

    async def execute(self, ctx: CommandContext) -> None:
        """Execute the mcp command.

        Args:
            ctx: Command context.
        """
        if not ctx.args:
            await self._show_help(ctx)
            return

        subcommand = ctx.args[0].lower()
        if subcommand == "list":
            await self._list(ctx)
        elif subcommand == "status":
            await self._status(ctx)
        elif subcommand == "logging":
            await self._logging(ctx)
        else:
            await self._show_help(ctx)

    async def _list(self, ctx: CommandContext) -> None:
        """List configured MCP servers."""
        console = ctx.console
        manager: McpManager | None = getattr(ctx, "mcp_manager", None)
        if manager is None:
            console.print("[dim]No MCP servers configured[/]")
            return

        names = manager.get_server_names()
        if not names:
            console.print("[dim]No MCP servers configured[/]")
            return

        console.print("\n[bold blue]MCP Servers[/]\n")
        for name in names:
            trusted = manager.is_trusted(name)
            client = manager.clients.get(name)
            connected = client.is_connected if client else False

            status = "[green]●[/]" if connected else "[red]○[/]"
            trust = "[cyan](trusted)[/]" if trusted else ""
            console.print(f"  {status} {name} {trust}")
        console.print("")

    async def _status(self, ctx: CommandContext) -> None:
        """Show MCP status and tools."""
        console = ctx.console
        manager: McpManager | None = getattr(ctx, "mcp_manager", None)
        if manager is None:
            console.print("[dim]No MCP servers configured[/]")
            return

        names = manager.get_server_names()
        connected = sum(1 for c in manager.clients.values() if c.is_connected)
        tools = manager.get_all_tools()

        console.print(f"\n[bold]Servers:[/] {connected}/{len(names)} connected")
        console.print(f"[bold]Tools:[/] {len(tools)} available")

        if tools:
            console.print("\n[bold blue]Available Tools[/]\n")
            for tool in tools[:self._MAX_TOOLS_DISPLAY]:  # Show first 10
                console.print(f"  • {tool.name}")
            if len(tools) > self._MAX_TOOLS_DISPLAY:
                console.print(f"  ... and {len(tools) - self._MAX_TOOLS_DISPLAY} more")
        console.print("")

    async def _logging(self, ctx: CommandContext) -> None:
        """Control MCP logging visibility.

        Args:
            ctx: Command context.
        """
        if len(ctx.args) < self._MIN_LOGGING_ARGS:
            self._print_logging_help(ctx.console)
            return

        action = ctx.args[1].lower()
        self._handle_logging_action(ctx, action)

    def _print_logging_help(self, console: Any) -> None:
        """Print MCP logging help information.

        Args:
            console: Console for output.
        """
        ConsoleHelper.print_status_header(console, "MCP Logging Control")
        console.print("  /mcp logging on     - Enable MCP logging messages")
        console.print("  /mcp logging off    - Disable MCP logging messages")
        console.print("  /mcp logging status - Show current logging status")
        console.print("")

    def _handle_logging_action(self, ctx: CommandContext, action: str) -> None:
        """Handle MCP logging action.

        Args:
            ctx: Command context.
            action: Action to perform ('on', 'off', or 'status').
        """
        console = ctx.console
        # Get settings from REPL context if available, otherwise load fresh
        settings = ctx.repl.settings if ctx.repl and ctx.repl.settings else load_settings()

        if action == "on":
            settings.ui.mcp_logging = True
            console.print("[green]✓ MCP logging enabled[/]")
        elif action == "off":
            settings.ui.mcp_logging = False
            console.print("[yellow]✓ MCP logging disabled[/]")
        elif action == "status":
            status = "enabled" if settings.ui.mcp_logging else "disabled"
            console.print(f"[bold]MCP logging:[/] {status}")
        else:
            console.print("[red]Error:[/] Invalid argument. Use 'on', 'off', or 'status'.")
            console.print("  Example: /mcp logging on")
