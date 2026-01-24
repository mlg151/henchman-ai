"""Tool registry for managing and executing tools."""

from collections.abc import Awaitable, Callable

from henchman.providers.base import ToolDeclaration
from henchman.tools.base import ConfirmationRequest, Tool, ToolResult

# Type alias for confirmation handler
ConfirmationHandler = Callable[[ConfirmationRequest], Awaitable[bool]]


class ToolRegistry:
    """Registry for managing tools and their execution.

    The ToolRegistry maintains a collection of tools that can be invoked
    by the LLM. It handles tool registration, declaration generation for
    the LLM, and execution with optional confirmation policies.

    Example:
        >>> registry = ToolRegistry()
        >>> registry.register(ReadFileTool())
        >>> declarations = registry.get_declarations()
        >>> result = await registry.execute("read_file", {"path": "/etc/hosts"})
    """

    def __init__(self) -> None:
        """Initialize an empty tool registry."""
        self._tools: dict[str, Tool] = {}
        self._confirmation_handler: ConfirmationHandler | None = None
        self._auto_approve_policies: set[str] = set()
        self._plan_mode: bool = False

    def set_plan_mode(self, enabled: bool) -> None:
        """Enable or disable Plan Mode (Read-Only).

        Args:
            enabled: True to enable Plan Mode.
        """
        self._plan_mode = enabled

    def register(self, tool: Tool) -> None:
        """Register a tool with the registry.

        Args:
            tool: The tool to register.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        if tool.name in self._tools:
            msg = f"Tool '{tool.name}' is already registered"
            raise ValueError(msg)
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """Remove a tool from the registry.

        Args:
            name: The name of the tool to remove.
                  Silently does nothing if tool doesn't exist.
        """
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        """Get a tool by name.

        Args:
            name: The name of the tool to retrieve.

        Returns:
            The tool if found, None otherwise.
        """
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """List all registered tool names.

        Returns:
            A list of tool names.
        """
        return list(self._tools.keys())

    def get_declarations(self) -> list[ToolDeclaration]:
        """Get tool declarations for the LLM.

        Returns:
            A list of ToolDeclaration objects suitable for passing to the LLM.
        """
        return [tool.to_declaration() for tool in self._tools.values()]

    def set_confirmation_handler(self, handler: ConfirmationHandler) -> None:
        """Set the handler for tool confirmation requests.

        Args:
            handler: An async function that takes a ConfirmationRequest
                    and returns True to approve, False to deny.
        """
        self._confirmation_handler = handler

    def add_auto_approve_policy(self, tool_name: str) -> None:
        """Add an auto-approve policy for a tool.

        Tools with auto-approve policies skip confirmation, even if
        they would normally require it.

        Args:
            tool_name: The name of the tool to auto-approve.
        """
        self._auto_approve_policies.add(tool_name)

    def remove_auto_approve_policy(self, tool_name: str) -> None:
        """Remove an auto-approve policy for a tool.

        Args:
            tool_name: The name of the tool to remove from auto-approve.
        """
        self._auto_approve_policies.discard(tool_name)

    def list_auto_approve_policies(self) -> list[str]:
        """List all tools with auto-approve policies.

        Returns:
            A list of tool names that are auto-approved.
        """
        return list(self._auto_approve_policies)

    async def execute(self, name: str, params: dict[str, object]) -> ToolResult:
        """Execute a tool by name with the given parameters.

        This method handles the full execution flow:
        1. Look up the tool
        2. Check Plan Mode restrictions
        3. Check if confirmation is needed (unless auto-approved or READ tool)
        4. Call confirmation handler if needed
        5. Execute the tool if approved

        Args:
            name: The name of the tool to execute.
            params: The parameters to pass to the tool.

        Returns:
            A ToolResult containing the execution result or error.
        """
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(
                content=f"Error: Tool '{name}' not found",
                success=False,
                error=f"Tool '{name}' not found",
            )

        # Check Plan Mode
        from henchman.tools.base import ToolKind
        if self._plan_mode and tool.kind in (ToolKind.WRITE, ToolKind.EXECUTE, ToolKind.NETWORK):
             return ToolResult(
                content=f"Tool '{name}' is disabled in Plan Mode. Use /plan to toggle.",
                success=False,
                error="Tool disabled in Plan Mode",
            )

        # Check if confirmation is needed
        if name not in self._auto_approve_policies:
            confirmation_request = tool.needs_confirmation(params)
            if confirmation_request is not None and self._confirmation_handler:
                approved = await self._confirmation_handler(confirmation_request)
                if not approved:
                    return ToolResult(
                        content=f"Tool execution denied by user: {name}",
                        success=False,
                        error="Execution denied by user",
                    )

        # Execute the tool
        return await tool.execute(**params)
