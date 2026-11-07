"""MCP server management command.

This module provides the /mcp command for listing and managing MCP servers.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import TYPE_CHECKING, Any, ClassVar, cast

from rich.markup import escape

from henchman.cli.commands import BaseCommand, CommandContext
from henchman.cli.console_helpers import ConsoleHelper
from henchman.cli.evidence import runtime_evidence_redactor, runtime_exception_text
from henchman.config import load_settings
from henchman.config.runtime import runtime_settings_state
from henchman.utils.evidence_redaction import PRESERVE_IDENTITY
from henchman.utils.tool_results import TOOL_RESULT_SCHEMA, tool_message_content

if TYPE_CHECKING:
    from henchman.mcp.context import McpContextCatalog, McpContextResult
    from henchman.mcp.manager import McpManager

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_MAX_TOOLS_DISPLAY = 10
_MIN_LOGGING_ARGS = 2


def _context_preview(value: Any, runtime: Any) -> str:
    """Project evidence before JSON formatting and summarize unsupported binary media."""
    block_schema = cast("list[Any]", TOOL_RESULT_SCHEMA["content_blocks"])[0]
    schema = {
        "source": {"server": None, "protocol_version": PRESERVE_IDENTITY, "connection_generation": PRESERVE_IDENTITY,
                   "catalog_generation": PRESERVE_IDENTITY, "operation": PRESERVE_IDENTITY, "identifier": None, "arguments": None},
        "entries": [{"name": None, "title": None, "description": None, "uri": None, "uriTemplate": None,
                     "mimeType": None, "size": None, "icons": None, "annotations": None, "_meta": None,
                     "arguments": [{"name": None, "title": None, "description": None, "required": PRESERVE_IDENTITY}]}],
        "payload": {
            "description": None, "_meta": None, "resultType": PRESERVE_IDENTITY,
            "ttlMs": PRESERVE_IDENTITY, "cacheScope": PRESERVE_IDENTITY,
            "contents": [{"uri": None, "mimeType": None, "text": None, "blob": None, "_meta": None}],
            "messages": [{"role": PRESERVE_IDENTITY, "content": block_schema}],
        },
    }
    data = runtime_evidence_redactor(runtime).redact(asdict(value), schema=schema)
    payload = data.get("payload")
    if isinstance(payload, dict):
        contents = payload.get("contents")
        messages = payload.get("messages")
        blocks = ([{"type": "resource", "resource": content} for content in contents]
                  if isinstance(contents, list) else [message["content"] for message in messages]
                  if isinstance(messages, list) else [])
        projected = json.loads(tool_message_content("", {
            "success": True, "error": None, "content_blocks": blocks,
            "structured_content_present": False, "metadata": None,
        }))["tool_result"]["content_blocks"]
        if isinstance(contents, list):
            payload["contents"] = [block["resource"] for block in projected]
        elif isinstance(messages, list):
            for message, block in zip(messages, projected, strict=True):
                message["content"] = block
    return json.dumps(data, ensure_ascii=True, allow_nan=False, indent=2)

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
    runtime = ctx.repl if ctx.repl is not None else ctx
    if getattr(runtime, "settings", None) is None:
        runtime.settings = load_settings()
    state = runtime_settings_state(runtime)
    settings = state.settings

    if action == "on":
        state.update({"ui": {"mcp_logging": True}})
        console.print("[green]\u2713 MCP logging enabled[/]")
    elif action == "off":
        state.update({"ui": {"mcp_logging": False}})
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
        "  /mcp refresh <server> - Refresh a connected server's tool catalog",
        "  /mcp logging   - Control MCP logging (on/off/status)",
        "  /mcp resources <server> - Explicitly refresh and preview resources",
        "  /mcp templates <server> - Explicitly refresh and preview URI templates",
        "  /mcp read <server> <uri> - Preview untrusted remote resource data",
        "  /mcp prompts <server> - Explicitly refresh and preview prompt declarations",
        "  /mcp prompt <server> <name> [JSON-object] - Preview a declared prompt",
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
        return "/mcp <list|status|refresh|logging|resources|templates|read|prompts|prompt>"

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
        elif subcommand == "refresh":
            await self._refresh(ctx)
        elif subcommand in {"resources", "templates", "read", "prompts", "prompt"}:
            await self._context(ctx, subcommand)
        else:
            await self._show_help(ctx)

    async def _context(self, ctx: CommandContext, action: str) -> None:
        """Fetch only the user-selected source; preview never edits live history."""
        manager = ctx.mcp_manager
        if manager is None:
            ctx.console.print("No MCP servers configured.")
            return
        runtime = ctx.repl if ctx.repl is not None else ctx
        result: McpContextCatalog | McpContextResult
        try:
            if action in {"resources", "templates", "prompts"}:
                if len(ctx.args) != 2:
                    raise ValueError("Expected exactly one configured server name")
                listing = {"resources": manager.list_resources, "templates": manager.list_resource_templates,
                           "prompts": manager.list_prompts}[action]
                result = await listing(ctx.args[1])
            elif action == "read":
                if len(ctx.args) != 3:
                    raise ValueError("Expected a configured server name and one resource URI")
                result = await manager.read_resource(ctx.args[1], ctx.args[2])
            else:
                if len(ctx.args) < 3:
                    raise ValueError("Expected a configured server name and a declared prompt name")
                raw = (ctx.raw_input.split(maxsplit=4)[4] if ctx.raw_input and len(ctx.raw_input.split(maxsplit=4)) == 5
                       else " ".join(ctx.args[3:]))
                if len(raw.encode("utf-8")) > 1024 * 1024:
                    raise ValueError("MCP prompt arguments exceed their byte limit")
                try:
                    arguments = json.loads(raw) if raw else {}
                except (ValueError, RecursionError):
                    raise ValueError("MCP prompt arguments must be a JSON object of strings") from None
                if not isinstance(arguments, dict) or any(not isinstance(value, str) for value in arguments.values()):
                    raise ValueError("MCP prompt arguments must be a JSON object of strings")
                result = await manager.get_prompt(ctx.args[1], ctx.args[2], arguments)
            preview = _context_preview(result, runtime)
        except Exception as error:
            ctx.console.print(f"MCP context request failed: {runtime_exception_text(runtime, error)}", markup=False)
            return
        if getattr(runtime, "_tui_adapter", None) is not None:
            # Textual command output passes through a second trusted markup
            # renderer after this console; keep remote tags literal there too.
            preview = escape(preview)
        ctx.console.print("Untrusted MCP context preview; conversation unchanged.", markup=False)
        ctx.console.print(preview, markup=False, highlight=False)

    async def _refresh(self, ctx: CommandContext) -> None:
        """Explicitly refresh one connected catalog without changing tool scopes."""
        manager = getattr(ctx, "mcp_manager", None)
        if manager is None:
            ctx.console.print("[dim]No MCP servers configured[/]")
            return
        if len(ctx.args) != 2:
            ctx.console.print("Usage: /mcp refresh <server>")
            return
        try:
            tools = await manager.refresh_server(ctx.args[1])
        except Exception as exc:
            policy = runtime_evidence_redactor(ctx.repl if ctx.repl is not None else ctx)
            detail = policy.text(str(exc))
            ctx.console.print(f"MCP catalog refresh failed: {detail}", markup=False)
            return
        ctx.console.print(f"MCP catalog refreshed: {len(tools)} tools.")

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
