"""MCP server management command.

This module provides the /mcp command for listing and managing MCP servers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from henchman.cli.commands import Command, CommandContext

if TYPE_CHECKING:
    from henchman.mcp.manager import McpManager


class McpCommand(Command):
    """/mcp command for MCP server management."""

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
        return "/mcp <list|status>"

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
        else:
            await self._show_help(ctx)

    async def _show_help(self, ctx: CommandContext) -> None:
        """Show help for /mcp command."""
        ctx.console.print("\n[bold blue]MCP Server Commands[/]\n")
        ctx.console.print("  /mcp list    - List configured MCP servers")
        ctx.console.print("  /mcp status  - Show connection status and tools")
        ctx.console.print("")

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
