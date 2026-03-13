"""Tool management for the REPL."""

from typing import TYPE_CHECKING

from henchman.tools.base import ConfirmationRequest
from henchman.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from henchman.config.schema import Settings

DEFAULT_SHELL_TIMEOUT = 3600


class ToolManager:
    """Manages tool registration and configuration for the REPL.

    This class handles:
    - Registering built-in tools
    - Managing tool confirmation
    - Configuring tool settings
    """

    def __init__(self: "ToolManager", settings: "Settings | None" = None) -> None:
        """Initialize the tool manager.

        Args:
            settings: Application settings for tool configuration.
        """
        self.settings = settings
        self.registry = ToolRegistry()
        self.auto_approve = False
        self._confirmation_handler: Callable[[ConfirmationRequest], Awaitable[bool]] | None = (
            None
        )

    def register_builtin_tools(self: "ToolManager") -> None:
        """Register all built-in tools with the registry.

        Returns:
            None
        """
        shell_timeout = (
            self.settings.tools.shell_timeout if self.settings else DEFAULT_SHELL_TIMEOUT
        )
        for tool in self._create_builtin_tools(shell_timeout):
            self.registry.register(tool)

    @staticmethod
    def _create_builtin_tools(shell_timeout: int) -> list:  # type: ignore[type-arg]
        """Instantiate every built-in tool and return them as a list.

        Args:
            shell_timeout: Timeout in seconds to pass to ShellTool.

        Returns:
            List of instantiated tool objects.
        """
        from henchman.tools.builtins import (  # noqa: PLC0415
            AskUserTool,
            CodeFormatTool,
            CoverageMapTool,
            DeadCodeTool,
            DeepResearchTool,
            DelegateTaskTool,
            DiffViewTool,
            EditFileTool,
            EnvInspectTool,
            FileOverviewTool,
            GitOpsTool,
            GlobTool,
            GrepTool,
            ImportGraphTool,
            KgQueryTool,
            KgUpdateTool,
            LintCheckTool,
            LsTool,
            PatchApplyTool,
            PatternSearchTool,
            PipInspectTool,
            PytestRunTool,
            PythonAstTool,
            PythonExecTool,
            ReadFileTool,
            ResearchNotesTool,
            ShellTool,
            SymbolTraceTool,
            TestGenTool,
            TracebackParseTool,
            WebFetchTool,
            WebSearchTool,
            WriteFileTool,
        )

        return [
            AskUserTool(),
            CodeFormatTool(),
            CoverageMapTool(),
            DeadCodeTool(),
            DeepResearchTool(),
            DelegateTaskTool(),
            DiffViewTool(),
            EditFileTool(),
            EnvInspectTool(),
            FileOverviewTool(),
            GitOpsTool(),
            GlobTool(),
            GrepTool(),
            ImportGraphTool(),
            KgQueryTool(),
            KgUpdateTool(),
            LintCheckTool(),
            LsTool(),
            PatchApplyTool(),
            PatternSearchTool(),
            PipInspectTool(),
            PythonAstTool(),
            PythonExecTool(),
            PytestRunTool(),
            ReadFileTool(),
            ResearchNotesTool(),
            ShellTool(default_timeout=shell_timeout),
            SymbolTraceTool(),
            TestGenTool(),
            TracebackParseTool(),
            WebFetchTool(),
            WebSearchTool(),
            WriteFileTool(),
        ]

    async def handle_confirmation(
        self: "ToolManager",
        request: ConfirmationRequest,
    ) -> bool:
        """Handle a tool confirmation request.

        Args:
            request: The confirmation request data.

        Returns:
            True if approved, False otherwise.
        """
        if self.auto_approve:
            return True
        if self._confirmation_handler:
            return await self._confirmation_handler(request)
        return False

    def set_confirmation_handler(
        self: "ToolManager",
        handler: "Callable[[ConfirmationRequest], Awaitable[bool]] | None" = None,
    ) -> None:
        """Set the confirmation handler on the registry.

        Args:
            handler: Optional custom confirmation handler. If None, uses the default handler.

        Returns:
            None
        """
        if handler:
            self._confirmation_handler = handler
        self.registry.set_confirmation_handler(self.handle_confirmation)

    def set_auto_approve(self: "ToolManager", *, auto_approve: bool) -> None:
        """Set auto-approve mode for tools.

        Args:
            auto_approve: If True, all tools are auto-approved.

        Returns:
            None
        """
        self.auto_approve = auto_approve

    def set_plan_mode(self: "ToolManager", *, plan_mode: bool) -> None:
        """Set plan mode on the registry.

        Args:
            plan_mode: If True, tools are in plan mode (read-only).

        Returns:
            None
        """
        self.registry.set_plan_mode(enabled=plan_mode)
