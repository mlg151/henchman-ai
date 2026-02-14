"""Tool management for the REPL."""

from typing import TYPE_CHECKING

from henchman.tools.base import ConfirmationRequest
from henchman.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from collections.abc import Awaitable
    from typing import Callable

    from henchman.config.schema import Settings


class ToolManager:
    """Manages tool registration and configuration for the REPL.

    This class handles:
    - Registering built-in tools
    - Managing tool confirmation
    - Configuring tool settings
    """

    def __init__(self, settings: "Settings | None" = None) -> None:
        """Initialize the tool manager.

        Args:
            settings: Application settings for tool configuration.
        """
        self.settings = settings
        self.registry = ToolRegistry()
        self.auto_approve = False
        self._confirmation_handler: Callable[[ConfirmationRequest], Awaitable[bool]] | None = None

    def register_builtin_tools(self) -> None:
        """Register all built-in tools with the registry."""
        from henchman.tools.builtins import (
            AskUserTool,
            DuckDuckGoSearchTool,
            EditFileTool,
            GlobTool,
            GrepTool,
            KgQueryTool,
            KgUpdateTool,
            LsTool,
            ReadFileTool,
            ShellTool,
            WebFetchTool,
            WriteFileTool,
        )

        tools = [
            AskUserTool(),
            ReadFileTool(),
            WriteFileTool(),
            EditFileTool(),
            LsTool(),
            GlobTool(),
            GrepTool(),
            ShellTool(
                default_timeout=(
                    self.settings.tools.shell_timeout if self.settings else 3600
                )
            ),
            WebFetchTool(),
            DuckDuckGoSearchTool(),
            KgQueryTool(),
            KgUpdateTool(),
        ]
        for tool in tools:
            self.registry.register(tool)

    async def handle_confirmation(self, request: ConfirmationRequest) -> bool:
        """Handle a tool confirmation request.

        Args:
            request: The confirmation request data.

        Returns:
            True if approved, False otherwise.
        """
        # Auto-approve if configured
        if self.auto_approve:
            return True
        
        # Use custom confirmation handler if provided
        if self._confirmation_handler:
            return await self._confirmation_handler(request)
        
        # Default behavior: require confirmation
        # In the actual REPL, this would show a prompt to the user
        return False

    def set_confirmation_handler(
        self, 
        handler: "Callable[[ConfirmationRequest], Awaitable[bool]] | None" = None
    ) -> None:
        """Set the confirmation handler on the registry.

        Args:
            handler: Optional custom confirmation handler. If None, uses the default handler.
        """
        if handler:
            self._confirmation_handler = handler
        self.registry.set_confirmation_handler(self.handle_confirmation)

    def set_auto_approve(self, auto_approve: bool) -> None:
        """Set auto-approve mode for tools.

        Args:
            auto_approve: If True, all tools are auto-approved.
        """
        self.auto_approve = auto_approve

    def set_plan_mode(self, plan_mode: bool) -> None:
        """Set plan mode on the registry.

        Args:
            plan_mode: If True, tools are in plan mode (read-only).
        """
        self.registry.set_plan_mode(plan_mode)