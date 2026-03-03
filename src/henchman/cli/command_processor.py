"""Command processor for REPL.

This module handles slash command parsing and execution.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from henchman.cli.commands import CommandContext, CommandRegistry, parse_command
from henchman.cli.commands.builtins import get_builtin_commands

if TYPE_CHECKING:
    from henchman.cli.output_handler import OutputHandler
    from henchman.cli.repl import Repl
    from henchman.cli.session_manager import ReplSessionManager
    from henchman.cli.tool_manager import ToolManager
    from henchman.core.agent import Agent
    from henchman.mcp.manager import McpManager
    from henchman.providers.base import ModelProvider


class CommandProcessor:
    """Handles slash command parsing and execution for the REPL.

    Responsibilities:
    - Parse slash commands
    - Execute registered commands
    - Handle special commands (quit, clear)
    - Provide command context
    """

    def __init__(
        self,
        output_handler: OutputHandler,
        tool_manager: ToolManager,
        session_manager: ReplSessionManager,
        provider: ModelProvider,
        mcp_manager: McpManager | None = None,
    ) -> None:
        """Initialize the command processor.

        Args:
            output_handler: Output handler for displaying results.
            tool_manager: Tool manager for tool registry.
            session_manager: Session manager for session information.
            provider: Model provider for agent context.
            mcp_manager: MCP manager for MCP commands.
        """
        self.output_handler = output_handler
        self.tool_manager = tool_manager
        self.session_manager = session_manager
        self.provider = provider
        self.mcp_manager = mcp_manager

        # Initialize command registry
        self.command_registry = CommandRegistry()
        for cmd in get_builtin_commands():
            self.command_registry.register(cmd)

    async def handle_command(self, input_text: str, agent: Agent, repl: Repl) -> bool:
        """Handle a slash command.

        Args:
            input_text: The command input (with leading /).
            agent: The agent for command context.
            repl: The REPL instance for command context.

        Returns:
            True to continue running, False to exit.
        """
        parsed = parse_command(input_text)
        if parsed is None:
            return True

        cmd_name, args = parsed

        # Special handling for /quit
        if cmd_name == "quit":
            return False

        # Special handling for /clear - clear agent history
        if cmd_name == "clear":
            agent.clear_history()
            self.output_handler.success("History cleared")
            return True

        # Try to execute the command
        cmd = self.command_registry.get(cmd_name)
        if cmd is None:
            self.output_handler.error(f"Unknown command: /{cmd_name}")
            self.output_handler.muted("Type /help for available commands")
            return True

        ctx = CommandContext(
            console=self.output_handler.renderer.console,
            args=args,
            agent=agent,
            tool_registry=self.tool_manager.registry,
            session=self.session_manager.current,
            repl=repl,
            registry=self.command_registry,
        )
        # Add session_manager and project_hash for /chat command
        # Handle both ReplSessionManager and any wrapper that has a session_manager attribute
        if hasattr(self.session_manager, "session_manager"):
            ctx.session_manager = self.session_manager.session_manager
        else:
            ctx.session_manager = self.session_manager
        # Add MCP manager for /mcp command
        ctx.mcp_manager = self.mcp_manager
        ctx.project_hash = self.session_manager.compute_project_hash(Path.cwd())

        try:
            await cmd.execute(ctx)
        except Exception as e:  # noqa: BLE001
            self.output_handler.error(f"Error executing command /{cmd_name}: {e}")
            import traceback  # noqa: PLC0415
            self.output_handler.muted(f"Details: {traceback.format_exc()}")
        return True

    def get_command_registry(self) -> CommandRegistry:
        """Get the command registry.

        Returns:
            The command registry.
        """
        return self.command_registry
