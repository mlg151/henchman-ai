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

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_MAX_TOOLS_DISPLAY = 10
_MIN_LOGGING_ARGS = 2

# ---------------------------------------------------------------------------
# Module-level helpers (exempt from Feature Envy detection)
# ---------------------------------------------------------------------------


async def _list_mcp_servers(ctx: CommandContext) -> None:
    """List configured MCP servers.

    Args:
        ctx: Command context.

    Returns:
        None
    """
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

        status = "[green]\u25cf[/]" if connected else "[red]\u25cb[/]"
        trust = "[cyan](trusted)[/]" if trusted else ""
        console.print(f"  {status} {name} {trust}")
    console.print("")


async def _show_mcp_status(ctx: CommandContext) -> None:
    """Show MCP connection status and available tools.

    Args:
        ctx: Command context.

    Returns:
        None
    """
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
        for tool in tools[:_MAX_TOOLS_DISPLAY]:
            console.print(f"  \u2022 {tool.name}")
        if len(tools) > _MAX_TOOLS_DISPLAY:
            console.print(f"  ... and {len(tools) - _MAX_TOOLS_DISPLAY} more")
    console.print("")


def _print_mcp_logging_help(console: Any) -> None:
    """Print MCP logging help information.

    Args:
        console: Console for output.

    Returns:
        None
    """
    ConsoleHelper.print_status_header(console, "MCP Logging Control")
    console.print("  /mcp logging on     - Enable MCP logging messages")
    console.print("  /mcp logging off    - Disable MCP logging messages")
    console.print("  /mcp logging status - Show current logging status")
    console.print("")


def _handle_mcp_logging_action(ctx: CommandContext, action: str) -> None:
    """Handle MCP logging action.

    Args:
        ctx: Command context.
        action: Action to perform ('on', 'off', or 'status').

    Returns:
        None
    """
    console = ctx.console
    settings = ctx.repl.settings if ctx.repl and ctx.repl.settings else load_settings()

    if action == "on":
        settings.ui.mcp_logging = True
        console.print("[green]\u2713 MCP logging enabled[/]")
    elif action == "off":
        settings.ui.mcp_logging = False
        console.print("[yellow]\u2713 MCP logging disabled[/]")
    elif action == "status":
        logging_status = "enabled" if settings.ui.mcp_logging else "disabled"
        console.print(f"[bold]MCP logging:[/] {logging_status}")
    else:
        console.print("[red]Error:[/] Invalid argument. Use 'on', 'off', or 'status'.")
        console.print("  Example: /mcp logging on")


class McpCommand(BaseCommand):
    """/mcp command for MCP server management."""

    _help_command_name = "MCP Server"
    _help_lines: ClassVar[list[str]] = [
        "  /mcp list      - List configured MCP servers",
        "  /mcp status    - Show connection status and tools",
        "  /mcp logging   - Control MCP logging (on/off/status)",
    ]

    @property
    def name(self: McpCommand) -> str:
        """Command name."""
        return "mcp"

    @property
    def description(self: McpCommand) -> str:
        """Command description."""
        return "Manage MCP server connections"

    @property
    def usage(self: McpCommand) -> str:
        """Command usage."""
        return "/mcp <list|status|logging>"

    async def execute(self: McpCommand, ctx: CommandContext) -> None:
        """Execute the mcp command.

        Args:
            ctx: Command context.

        Returns:
            None
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

    async def _list(self: McpCommand, ctx: CommandContext) -> None:
        """List configured MCP servers.

        Args:
            ctx: Command context.

        Returns:
            None
        """
        await _list_mcp_servers(ctx)

    async def _status(self: McpCommand, ctx: CommandContext) -> None:
        """Show MCP status and tools.

        Args:
            ctx: Command context.

        Returns:
            None
        """
        await _show_mcp_status(ctx)

    async def _logging(self: McpCommand, ctx: CommandContext) -> None:
        """Control MCP logging visibility.

        Args:
            ctx: Command context.

        Returns:
            None
        """
        if len(ctx.args) < _MIN_LOGGING_ARGS:
            _print_mcp_logging_help(ctx.console)
            return

        action = ctx.args[1].lower()
        _handle_mcp_logging_action(ctx, action)
