"""MCP server management command.

This module provides the /mcp command for listing and managing MCP servers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from henchman.cli.commands import BaseCommand, CommandContext
from henchman.config import load_settings

if TYPE_CHECKING:
    from henchman.mcp.manager import McpManager


class McpCommand(BaseCommand):
    """/mcp command for MCP server management."""

    _help_command_name = "MCP Server"
    _help_lines = [
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
        manager: McpManager | None = getattr(ctx, "mcp_manager", None)
        if manager is None:
            ctx.console.print("[dim]No MCP servers configured[/]")
            return

        names = manager.get_server_names()
        if not names:
            ctx.console.print("[dim]No MCP servers configured[/]")
            return

        ctx.console.print("\n[bold blue]MCP Servers[/]\n")
        for name in names:
            trusted = manager.is_trusted(name)
            client = manager.clients.get(name)
            connected = client.is_connected if client else False

            status = "[green]●[/]" if connected else "[red]○[/]"
            trust = "[cyan](trusted)[/]" if trusted else ""
            ctx.console.print(f"  {status} {name} {trust}")
        ctx.console.print("")

    async def _status(self, ctx: CommandContext) -> None:
        """Show MCP status and tools."""
        manager: McpManager | None = getattr(ctx, "mcp_manager", None)
        if manager is None:
            ctx.console.print("[dim]No MCP servers configured[/]")
            return

        names = manager.get_server_names()
        connected = sum(1 for c in manager.clients.values() if c.is_connected)
        tools = manager.get_all_tools()

        ctx.console.print(f"\n[bold]Servers:[/] {connected}/{len(names)} connected")
        ctx.console.print(f"[bold]Tools:[/] {len(tools)} available")

        if tools:
            ctx.console.print("\n[bold blue]Available Tools[/]\n")
            for tool in tools[:10]:  # Show first 10
                ctx.console.print(f"  • {tool.name}")
            if len(tools) > 10:
                ctx.console.print(f"  ... and {len(tools) - 10} more")
        ctx.console.print("")

    async def _logging(self, ctx: CommandContext) -> None:
        """Control MCP logging visibility.

        Args:
            ctx: Command context.
        """
        if len(ctx.args) < 2:
            self._print_logging_help(ctx.console)
            return

        action = ctx.args[1].lower()
        self._handle_logging_action(ctx, action)

    def _print_logging_help(self, console: Any) -> None:
        """Print MCP logging help information.

        Args:
            console: Console for output.
        """
        console.print("\n[bold blue]MCP Logging Control[/]\n")
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
        # Get settings from REPL context if available, otherwise load fresh
        settings = ctx.repl.settings if ctx.repl and ctx.repl.settings else load_settings()

        if action == "on":
            settings.ui.mcp_logging = True
            ctx.console.print("[green]✓ MCP logging enabled[/]")
        elif action == "off":
            settings.ui.mcp_logging = False
            ctx.console.print("[yellow]✓ MCP logging disabled[/]")
        elif action == "status":
            status = "enabled" if settings.ui.mcp_logging else "disabled"
            ctx.console.print(f"[bold]MCP logging:[/] {status}")
        else:
            ctx.console.print("[red]Error:[/] Invalid argument. Use 'on', 'off', or 'status'.")
            ctx.console.print("  Example: /mcp logging on")
