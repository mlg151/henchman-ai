"""Tool registry for managing and executing tools."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from henchman.tools.base import ConfirmationRequest, Tool, ToolKind, ToolResult
from henchman.tools.formatting import PythonAutoFormatter
from henchman.tools.security import sanitize_error_message
from henchman.utils.retry import RetryConfig, retry_async

if TYPE_CHECKING:
    from henchman.providers.base import ToolDeclaration

# Type alias for confirmation handler
ConfirmationHandler = Callable[[ConfirmationRequest], Awaitable[bool]]
TeamToolResolver = Callable[[str], list[str] | None]

# Maximum characters for tool output before truncation
MAX_TOOL_OUTPUT = 50000
MAX_DISCOVERED_TOOLS = 5


@dataclass
class BatchResult:
    """Result of a batch tool execution.

    Attributes:
        results: Mapping of ``"{index}:{tool_name}"`` keys to ToolResult values.
            The index-prefixed key guarantees uniqueness even when the same tool
            is called multiple times.  Iterate ``results.values()`` for ordered
            results, or use ``results[f"{i}:{name}"]`` for positional lookup.
        successful: Number of successful executions.
        failed: Number of failed executions.
    """

    results: dict[str, ToolResult]
    successful: int
    failed: int


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

    def __init__(
        self: ToolRegistry,
        retry_config: RetryConfig | None = None,
    ) -> None:
        """Initialize an empty tool registry.

        Args:
            retry_config: Optional retry configuration for network tools.
                         If None, uses defaults (3 retries, 1s base delay).
        """
        self._tools: dict[str, Tool] = {}
        self._local_confirmation_handler: ConfirmationHandler | None = None
        self._policy_parent: ToolRegistry | None = None
        self._auto_approve_policies: set[str] = set()
        self._plan_mode: bool = False
        self._retry_config = retry_config or RetryConfig()
        self._discovery_tool: Tool | None = None
        self._discovered_tools: list[str] = []
        self._team_tool_resolver: TeamToolResolver | None = None
        self._formatter = PythonAutoFormatter()

    @property
    def _effective_formatter(self) -> PythonAutoFormatter:
        """Serialize workspace mutations and formatting across scoped registries."""
        if self._policy_parent is not None:
            return self._policy_parent._effective_formatter
        return self._formatter

    def bind_team_tool_resolver(self, resolver: TeamToolResolver | None) -> None:
        """Bind read-only team metadata to this registry, independent of search instances."""
        self._team_tool_resolver = resolver

    def find_team_tool_roles(self, name: str) -> list[str] | None:
        """Return scoped role metadata, or None when team discovery is unavailable."""
        if self._team_tool_resolver is None or self.get("delegate_task") is None:
            return None
        return self._team_tool_resolver(name)

    def enable_tool_discovery(self, tool: Tool) -> None:
        """Enable schema discovery when a bound search tool is registered."""
        self._discovery_tool = tool

    @property
    def supports_tool_discovery(self) -> bool:
        """Whether this registry currently has enabled tool-search support."""
        tool = self.get("tool_search")
        return self._discovery_tool is not None and tool is self._discovery_tool

    def prioritize_tools(self, names: list[str]) -> None:
        """Replace schema priorities with up to five unique registered names."""
        priorities: list[str] = []
        for name in names:
            if self.get(name) is not None and name not in priorities:
                priorities.append(name)
                if len(priorities) == MAX_DISCOVERED_TOOLS:
                    break
        self._discovered_tools = priorities

    @property
    def discovered_tools(self) -> list[str]:
        """Return current priority names without exposing mutable registry state."""
        return [name for name in self._discovered_tools if self.get(name) is not None]

    def inherit_policies_from(self, parent: ToolRegistry) -> None:
        """Follow the parent's current confirmation and read-only restrictions.

        Scope-local auto-approval remains explicit. A local read-only restriction
        also remains effective when the parent returns to execution mode.
        """
        self._policy_parent = parent

    @property
    def _confirmation_handler(self) -> ConfirmationHandler | None:
        """Resolve current confirmation policy rather than a cached handler."""
        if self._policy_parent is not None:
            return self._policy_parent._confirmation_handler
        return self._local_confirmation_handler

    @property
    def _effective_plan_mode(self) -> bool:
        """Honor read-only restrictions throughout the registry ancestry."""
        return self._plan_mode or (
            self._policy_parent is not None and self._policy_parent._effective_plan_mode
        )

    def set_retry_config(self: ToolRegistry, config: RetryConfig) -> None:
        """Set the retry configuration for network tools.

        Args:
            config: Retry configuration.

        Returns:
            None
        """
        self._retry_config = config

    def set_plan_mode(self: ToolRegistry, *, enabled: bool) -> None:
        """Enable or disable Plan Mode (Read-Only).

        Args:
            enabled: True to enable Plan Mode.

        Returns:
            None
        """
        self._plan_mode = enabled

    def register(self: ToolRegistry, tool: Tool) -> None:
        """Register a tool with the registry.

        Args:
            tool: The tool to register.

        Raises:
            ValueError: If a tool with the same name is already registered.

        Returns:
            None
        """
        if tool.name in self._tools:
            msg = f"Tool '{tool.name}' is already registered"
            raise ValueError(msg)
        self._tools[tool.name] = tool

    def unregister(self: ToolRegistry, name: str) -> None:
        """Remove a tool from the registry.

        Args:
            name: The name of the tool to remove.
                  Silently does nothing if tool doesn't exist.

        Returns:
            None
        """
        self._tools.pop(name, None)

    def get(self: ToolRegistry, name: str) -> Tool | None:
        """Get a tool by name.

        Args:
            name: The name of the tool to retrieve.

        Returns:
            The tool if found, None otherwise.
        """
        return self._tools.get(name)

    def __len__(self: ToolRegistry) -> int:
        """Return the number of registered tools.

        Returns:
            Number of registered tools.
        """
        return len(self.list_tools())

    def list_tools(self: ToolRegistry) -> list[str]:
        """List all registered tool names.

        Returns:
            A list of tool names.
        """
        return list(self._tools.keys())

    def get_declarations(self: ToolRegistry) -> list[ToolDeclaration]:
        """Get tool declarations for the LLM.

        Returns:
            A list of ToolDeclaration objects suitable for passing to the LLM.
        """
        return [
            tool.to_declaration()
            for name in self.list_tools()
            if (tool := self.get(name)) is not None
        ]

    def set_confirmation_handler(self: ToolRegistry, handler: ConfirmationHandler) -> None:
        """Set the handler for tool confirmation requests.

        Args:
            handler: An async function that takes a ConfirmationRequest
                    and returns True to approve, False to deny.

        Returns:
            None
        """
        self._local_confirmation_handler = handler

    def add_auto_approve_policy(self: ToolRegistry, tool_name: str) -> None:
        """Add an auto-approve policy for a tool.

        Tools with auto-approve policies skip confirmation, even if
        they would normally require it.

        Args:
            tool_name: The name of the tool to auto-approve.

        Returns:
            None
        """
        self._auto_approve_policies.add(tool_name)

    def remove_auto_approve_policy(self: ToolRegistry, tool_name: str) -> None:
        """Remove an auto-approve policy for a tool.

        Args:
            tool_name: The name of the tool to remove from auto-approve.

        Returns:
            None
        """
        self._auto_approve_policies.discard(tool_name)

    def list_auto_approve_policies(self: ToolRegistry) -> list[str]:
        """List all tools with auto-approve policies.

        Returns:
            A list of tool names that are auto-approved.
        """
        return list(self._auto_approve_policies)

    def is_auto_approved(self, name: str) -> bool:
        """Return whether this registry explicitly auto-approves a tool."""
        return name in self._auto_approve_policies

    async def authorize(self, name: str, params: dict[str, object]) -> Tool | ToolResult:
        """Return the allowed registered tool or a denial, without executing it.

        Orchestrated tools use this same check before their custom dispatch.
        """
        tool = self.get(name)
        if tool is None:
            return ToolResult(
                content=f"Error: Tool '{name}' not found",
                success=False,
                error=f"Tool '{name}' not found",
            )

        # Check Plan Mode
        if self._effective_plan_mode and tool.execution_kind(params) in (
            ToolKind.WRITE,
            ToolKind.EXECUTE,
            ToolKind.NETWORK,
        ):
            return ToolResult(
                content=f"Tool '{name}' is disabled in Plan Mode. Use /plan to toggle.",
                success=False,
                error="Tool disabled in Plan Mode",
            )

        # Check if confirmation is needed
        if not self.is_auto_approved(name):
            confirmation_request = tool.needs_confirmation(params)
            handler = self._confirmation_handler
            if confirmation_request is not None and handler:
                approved = await handler(confirmation_request)
                if not approved:
                    return ToolResult(
                        content=f"Tool execution denied by user: {name}",
                        success=False,
                        error="Execution denied by user",
                    )

        return tool

    async def execute(self: ToolRegistry, name: str, params: dict[str, object]) -> ToolResult:
        """Execute a tool by name with the given parameters.

        This method handles the full execution flow:
        1. Look up the tool
        2. Check Plan Mode restrictions
        3. Check if confirmation is needed (unless auto-approved or READ tool)
        4. Call confirmation handler if needed
        5. Execute the tool if approved (with retries for NETWORK tools)

        Args:
            name: The name of the tool to execute.
            params: The parameters to pass to the tool.

        Returns:
            A ToolResult containing the execution result or error.
        """
        tool = await self.authorize(name, params)
        if isinstance(tool, ToolResult):
            return tool

        async def execute_authorized() -> ToolResult:
            if (
                tool.execution_kind(params) == ToolKind.NETWORK
                and self._retry_config.max_retries > 0
            ):
                return await retry_async(
                    lambda: tool.execute(**params),
                    config=self._retry_config,
                )
            return await tool.execute(**params)

        # Formatting completes before verification can consume the tool result.
        try:
            result = await self._effective_formatter.run(tool, params, execute_authorized)
        except Exception as exc:
            sanitized_error = sanitize_error_message(exc)
            return ToolResult(
                content=f"Error executing tool '{name}': {sanitized_error}",
                success=False,
                error=sanitized_error,
            )

        # Truncate large outputs to prevent context overflow
        if result.content and len(result.content) > MAX_TOOL_OUTPUT:
            truncated_content = result.content[:MAX_TOOL_OUTPUT]
            truncated_content += f"\n\n[... truncated after {MAX_TOOL_OUTPUT} chars]"
            result = ToolResult(
                content=truncated_content,
                success=result.success,
                display=result.display,
                error=result.error,
            )

        return result

    async def execute_batch(
        self: ToolRegistry,
        calls: list[tuple[str, dict[str, object]]],
    ) -> BatchResult:
        """Execute multiple tools in parallel.

        Independent tool calls are executed concurrently using asyncio.gather().
        This is more efficient than sequential execution for I/O-bound operations.

        Args:
            calls: List of (tool_name, params) tuples to execute.

        Returns:
            BatchResult containing individual results and success/failure counts.

        Example:
            >>> results = await registry.execute_batch([
            ...     ("read_file", {"path": "/etc/hosts"}),
            ...     ("read_file", {"path": "/etc/passwd"}),
            ...     ("glob", {"pattern": "*.py"}),
            ... ])
            >>> print(f"Completed: {results.successful} succeeded, {results.failed} failed")
        """
        if not calls:
            return BatchResult(results={}, successful=0, failed=0)

        # Execute all tools concurrently
        tasks = [self.execute(name, params) for name, params in calls]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect results
        results: dict[str, ToolResult] = {}
        successful = 0
        failed = 0

        for i, result in enumerate(results_list):
            tool_name = calls[i][0]
            # Key is "{index}:{tool_name}" — the index prefix guarantees
            # uniqueness even when the same tool appears multiple times, and
            # avoids collisions with tool names that already contain "_N" suffixes
            # (e.g. a tool named "my_tool_0" would have collided with the old
            # "{tool_name}_{i}" scheme when i=0).
            key = f"{i}:{tool_name}"

            if isinstance(result, BaseException):
                results[key] = ToolResult(
                    content=f"Error: {result}",
                    success=False,
                    error=str(result),
                )
                failed += 1
            else:
                tool_result: ToolResult = result
                results[key] = tool_result
                if tool_result.success:
                    successful += 1
                else:
                    failed += 1

        return BatchResult(results=results, successful=successful, failed=failed)
