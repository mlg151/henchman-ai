"""Tool management for the REPL."""

from typing import TYPE_CHECKING

from henchman.tools.base import ConfirmationRequest
from henchman.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from henchman.config.schema import Settings

DEFAULT_SHELL_TIMEOUT = 3600


class ToolManager:
    """Manages tool registration and configuration for the REPL.

    This class handles:
    - Registering built-in tools
    - Managing tool confirmation
    - Configuring tool settings
    """

    def __init__(
        self: "ToolManager",
        settings: "Settings | None" = None,
        *,
        question_handler: "Callable[[str], Awaitable[str | None]] | None" = None,
    ) -> None:
        """Initialize the tool manager.

        Args:
            settings: Application settings for tool configuration.
            question_handler: Optional UI channel for real user answers.
        """
        self.settings = settings
        self._question_handler = question_handler
        self.registry = ToolRegistry()
        self.auto_approve = False
        self._confirmation_handler: Callable[[ConfirmationRequest], Awaitable[bool]] | None = None
        self._project_root: Path | None = None
        self._session_manager: object | None = None
        self._mcp_manager: object | None = None

    def register_builtin_tools(self: "ToolManager") -> None:
        """Register all built-in tools with the registry.

        Returns:
            None
        """
        shell_timeout = (
            self.settings.tools.shell_timeout if self.settings else DEFAULT_SHELL_TIMEOUT
        )
        tools = self._create_builtin_tools(shell_timeout, self._question_handler)
        for tool in tools:
            # Bind runtime dependencies to tools that support it
            if hasattr(tool, "bind_runtime"):
                tool.bind_runtime(
                    project_root=self._project_root,
                    tool_registry=self.registry,
                    session_manager=self._session_manager,
                    mcp_manager=self._mcp_manager,
                )
            self.registry.register(tool)

    def bind_runtime(
        self: "ToolManager",
        *,
        project_root: "Path",
        session_manager: "object | None" = None,
        mcp_manager: "object | None" = None,
    ) -> None:
        """Bind runtime dependencies to the tool manager.

        Stores runtime references (project root, session manager, MCP manager)
        that can be used by tool instances during execution.

        Args:
            project_root: Root directory of the current project.
            session_manager: Optional session manager for persistence.
            mcp_manager: Optional MCP manager for external tool servers.

        Returns:
            None
        """
        self._project_root = project_root
        self._session_manager = session_manager
        self._mcp_manager = mcp_manager

    @staticmethod
    def _create_builtin_tools(
        shell_timeout: int,
        question_handler: "Callable[[str], Awaitable[str | None]] | None" = None,
    ) -> list:  # type: ignore[type-arg]
        """Instantiate every built-in tool and return them as a list.

        Args:
            shell_timeout: Timeout in seconds to pass to ShellTool.
            question_handler: Optional UI channel for real user answers.

        Returns:
            List of instantiated tool objects.
        """
        from henchman.tools.builtins import (
            AskUserTool,
            CodeFormatTool,
            CoverageMapTool,
            DeadCodeTool,
            DeepResearchTool,
            DelegateTaskTool,
            DiffViewTool,
            EditFileTool,
            EnterPlanModeTool,
            EnterWorktreeTool,
            EnvInspectTool,
            ExitPlanModeTool,
            ExitWorktreeTool,
            FileOverviewTool,
            GitOpsTool,
            GlobTool,
            GoalStatusTool,
            GrepTool,
            ImportGraphTool,
            KgQueryTool,
            KgUpdateTool,
            LintCheckTool,
            LSPTool,
            LsTool,
            McpAuthTool,
            MCPTool,
            PatchApplyTool,
            PatternSearchTool,
            PipInspectTool,
            PytestRunTool,
            PythonAstTool,
            PythonExecTool,
            ReadFileTool,
            REPLTool,
            ResearchNotesTool,
            ScheduleCronTool,
            SendMessageTool,
            SendUserFileTool,
            ShellTool,
            SkillTool,
            SleepTool,
            SymbolTraceTool,
            TaskCreateTool,
            TaskGetTool,
            TaskListTool,
            TaskOutputTool,
            TaskStopTool,
            TaskUpdateTool,
            TeamCreateTool,
            TeamDeleteTool,
            TestGenTool,
            ToolSearchTool,
            TracebackParseTool,
            TungstenTool,
            VerifyPlanExecutionTool,
            WebFetchTool,
            WebSearchTool,
            WorkflowTool,
            WriteFileTool,
        )

        return [
            AskUserTool(question_handler=question_handler),
            CodeFormatTool(),
            CoverageMapTool(),
            DeadCodeTool(),
            DeepResearchTool(),
            DelegateTaskTool(),
            DiffViewTool(),
            EditFileTool(),
            EnterPlanModeTool(),
            EnterWorktreeTool(),
            EnvInspectTool(),
            ExitPlanModeTool(),
            ExitWorktreeTool(),
            FileOverviewTool(),
            GitOpsTool(),
            GlobTool(),
            GoalStatusTool(),
            GrepTool(),
            ImportGraphTool(),
            KgQueryTool(),
            KgUpdateTool(),
            LSPTool(),
            LintCheckTool(),
            LsTool(),
            MCPTool(),
            McpAuthTool(),
            PatchApplyTool(),
            PatternSearchTool(),
            PipInspectTool(),
            PythonAstTool(),
            PythonExecTool(),
            PytestRunTool(),
            REPLTool(),
            ReadFileTool(),
            ResearchNotesTool(),
            ScheduleCronTool(),
            SendMessageTool(),
            SendUserFileTool(),
            ShellTool(default_timeout=shell_timeout),
            SkillTool(),
            SleepTool(),
            SymbolTraceTool(),
            TaskCreateTool(),
            TaskGetTool(),
            TaskListTool(),
            TaskOutputTool(),
            TaskStopTool(),
            TaskUpdateTool(),
            TeamCreateTool(),
            TeamDeleteTool(),
            TestGenTool(),
            ToolSearchTool(),
            TracebackParseTool(),
            TungstenTool(),
            VerifyPlanExecutionTool(),
            WebFetchTool(),
            WebSearchTool(),
            WorkflowTool(),
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
