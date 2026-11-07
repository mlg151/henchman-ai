"""Tool registry for managing and executing tools."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from itertools import count
from typing import TYPE_CHECKING

from henchman.tools.access_policy import (
    ToolAccessPolicy,
    current_access_policies,
    use_access_policies,
)
from henchman.tools.base import ConfirmationRequest, Tool, ToolKind, ToolResult
from henchman.tools.formatting import PythonAutoFormatter
from henchman.tools.policy import (
    ApprovalGrantStore,
    GrantKey,
    PolicyDecision,
    evaluate_effective_policy,
    grant_key_for,
    invocation_scope_digest,
)
from henchman.tools.security import sanitize_error_message
from henchman.utils.retry import RetryConfig, retry_async

if TYPE_CHECKING:
    from henchman.providers.base import ToolDeclaration

# Type alias for confirmation handler
ConfirmationHandler = Callable[[ConfirmationRequest], Awaitable[bool]]
TeamToolResolver = Callable[[str], list[str] | None]
ExecutionGuard = Callable[[Tool, dict[str, object]], ToolResult | None]

# Maximum characters for tool output before truncation
MAX_TOOL_OUTPUT = 50000
MAX_DISCOVERED_TOOLS = 5
_TOOL_REGISTRATIONS = count(1)


@dataclass(frozen=True)
class _Authorization:
    """One invocation's authority captured before asynchronous work."""

    tool: Tool
    key: GrantKey
    grants: ApprovalGrantStore
    grant_generation: int
    confirmation: ConfirmationRequest | None
    policy_generation: tuple[tuple[int, int], ...]


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
        self._tool_registrations: dict[str, int] = {}
        self._local_confirmation_handler: ConfirmationHandler | None = None
        self._policy_parent: ToolRegistry | None = None
        self._policy_generation = 0
        self._access_policies: tuple[ToolAccessPolicy, ...] = ()
        self._auto_approve_policies: set[str] = set()
        self._plan_mode: bool = False
        self._grants = ApprovalGrantStore()
        self._retry_config = retry_config or RetryConfig()
        self._discovery_tool: Tool | None = None
        self._discovered_tools: list[str] = []
        self._team_tool_resolver: TeamToolResolver | None = None
        self._execution_guard: ExecutionGuard | None = None
        self._formatter = PythonAutoFormatter()

    def bind_execution_guard(self, guard: ExecutionGuard | None) -> None:
        """Bind a repeatable preflight that may defer, never approve, execution.

        Checks repeat after awaited approval and immediately before dispatch;
        guards must not execute tools or consume one-use state themselves.
        """
        if self._execution_guard is not guard:
            self._policy_generation += 1
        self._execution_guard = guard

    def set_access_policy(self, policy: ToolAccessPolicy) -> None:
        """Bind trusted runtime restrictions; local changes never widen ancestors."""
        policies = (policy,) if policy.restricted else ()
        if self._access_policies != policies:
            self._policy_generation += 1
        self._access_policies = policies

    def restrict_access_policy(self, policy: ToolAccessPolicy) -> None:
        """Intersect constructor/integration settings with every existing boundary."""
        if policy.restricted and policy not in self._access_policies:
            self._access_policies = (*self._access_policies, policy)
            self._policy_generation += 1

    @property
    def _effective_access_policies(self) -> tuple[ToolAccessPolicy, ...]:
        parent = self._policy_parent._effective_access_policies if self._policy_parent is not None else ()
        return (*parent, *self._access_policies)

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
        if self._policy_parent is not parent:
            self._policy_generation += 1
        self._policy_parent = parent

    @property
    def _effective_policy_generation(self) -> tuple[tuple[int, int], ...]:
        """Track policy changes across awaits, including temporary restrictions."""
        local = ((id(self), self._policy_generation),)
        if self._policy_parent is not None:
            return local + self._policy_parent._effective_policy_generation
        return local

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

    @property
    def _effective_grants(self) -> ApprovalGrantStore:
        """Share user approvals across the whole session ancestry."""
        if self._policy_parent is not None:
            return self._policy_parent._effective_grants
        return self._grants

    @property
    def is_plan_mode_active(self) -> bool:
        """Whether the effective Plan Mode boundary is currently in force."""
        return self._effective_plan_mode

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
        if self._plan_mode != enabled:
            self._policy_generation += 1
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
        self._tool_registrations[tool.name] = next(_TOOL_REGISTRATIONS)

    def unregister(self: ToolRegistry, name: str) -> None:
        """Remove a tool from the registry.

        Args:
            name: The name of the tool to remove.
                  Silently does nothing if tool doesn't exist.

        Returns:
            None
        """
        self._tools.pop(name, None)
        self._tool_registrations.pop(name, None)

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
        if self._local_confirmation_handler is not handler:
            self._policy_generation += 1
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
        if tool_name not in self._auto_approve_policies:
            self._policy_generation += 1
        self._auto_approve_policies.add(tool_name)

    def remove_auto_approve_policy(self: ToolRegistry, tool_name: str) -> None:
        """Remove an auto-approve policy for a tool.

        Args:
            tool_name: The name of the tool to remove from auto-approve.

        Returns:
            None
        """
        if tool_name in self._auto_approve_policies:
            self._policy_generation += 1
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

    def list_approval_grants(self) -> list[GrantKey]:
        """List the user-approved grants active in this session scope."""
        return self._effective_grants.all()

    def clear_grants(self) -> None:
        """Invalidate every user approval for the session scope.

        Called at session boundaries (new session, resume, or explicit reset)
        so that approvals never carry over into a different session scope.
        """
        self._effective_grants.clear()

    def evaluate_policy(self, name: str, params: dict[str, object]) -> PolicyDecision | None:
        """Return the centralized effective policy for one invocation.

        The verdict combines the effective Plan Mode boundary, the tool's
        per-invocation operation effect, and this registry's approval
        grants. Returns None when the tool is not registered.
        """
        tool = self.get(name)
        if tool is None:
            return None
        return evaluate_effective_policy(
            tool,
            params,
            plan_mode_active=self._effective_plan_mode,
            auto_approved=self.is_auto_approved(name),
            access_policies=(*current_access_policies(), *self._effective_access_policies),
        )

    def _tool_registration(self, name: str, tool: Tool) -> int:
        """Resolve the registration identity shared by parent and scoped views."""
        if self._tools.get(name) is tool:
            return self._tool_registrations[name]
        if self._policy_parent is not None and self._policy_parent.get(name) is tool:
            return self._policy_parent._tool_registration(name, tool)
        # Scope-bound discovery proxies have no confirmation grant; identity is
        # still compared by object reference before dispatch.
        return 0

    def _capture_authorization(
        self, name: str, params: dict[str, object],
    ) -> _Authorization | ToolResult:
        """Read current policy and capture its invocation scope without awaiting."""
        tool = self.get(name)
        if tool is None:
            return ToolResult(
                content=f"Error: Tool '{name}' not found",
                success=False,
                error=f"Tool '{name}' not found",
            )

        decision = evaluate_effective_policy(
            tool,
            params,
            plan_mode_active=self._effective_plan_mode,
            auto_approved=self.is_auto_approved(name),
            access_policies=(*current_access_policies(), *self._effective_access_policies),
        )
        if not decision.allowed:
            return ToolResult(
                content=(f"Tool '{name}' is disabled in Plan Mode. Use /plan to toggle."
                         if decision.denial_reason == "Tool disabled in Plan Mode"
                         else decision.denial_reason or "Tool access denied"),
                success=False,
                error=decision.denial_reason,
            )

        try:
            scope = invocation_scope_digest(tool, params)
        except (OSError, RuntimeError, ValueError) as exc:
            message = f"Cannot resolve tool authorization scope: {sanitize_error_message(exc)}"
            return ToolResult(content=message, success=False, error=message)
        request = decision.confirmation or ConfirmationRequest(name, "", params, risk_level="")
        grants = self._effective_grants
        return _Authorization(
            tool=tool,
            key=grant_key_for(
                request, decision.effective_kind, scope_digest=scope,
                tool_registration=self._tool_registration(name, tool),
            ),
            grants=grants,
            grant_generation=grants.generation,
            confirmation=decision.confirmation,
            policy_generation=self._effective_policy_generation,
        )

    def _revalidate_authorization(
        self, authorization: _Authorization, params: dict[str, object], *, require_grant: bool = True,
    ) -> ToolResult | None:
        """Reject changed scope or withdrawn authority without prompting in a lock."""
        current = self._capture_authorization(authorization.tool.name, params)
        if isinstance(current, ToolResult):
            return current
        if (
            current.tool is not authorization.tool
            or current.key != authorization.key
            or current.grants is not authorization.grants
            or current.grant_generation != authorization.grant_generation
            or current.policy_generation != authorization.policy_generation
            or (
                require_grant and current.confirmation is not None
                and not current.grants.is_granted(current.key)
            )
        ):
            message = "Tool authorization scope changed; retry the invocation for fresh approval"
            return ToolResult(content=message, success=False, error=message)
        return None

    async def _authorize_invocation(
        self, name: str, params: dict[str, object],
    ) -> _Authorization | ToolResult:
        """Approve one captured scope, retaining no grant when that scope changes."""
        authorization = self._capture_authorization(name, params)
        if isinstance(authorization, ToolResult):
            return authorization
        tool = authorization.tool
        if self._execution_guard is not None:
            deferred = self._execution_guard(tool, params)
            if deferred is not None:
                return deferred

        confirmation_request = authorization.confirmation
        if confirmation_request is not None:
            key = authorization.key
            if not authorization.grants.is_granted(key):
                handler = self._confirmation_handler
                if handler:
                    approved = await handler(confirmation_request)
                    if not approved:
                        return ToolResult(
                            content=f"Tool execution denied by user: {name}",
                            success=False,
                            error="Execution denied by user",
                        )
                    stale = self._revalidate_authorization(authorization, params, require_grant=False)
                    if stale is not None:
                        return stale
                    authorization.grants.grant(key)
                    # Instructions may change while the user considers approval.
                    # Retain that approval if fresh context defers this attempt.
                    if self._execution_guard is not None:
                        deferred = self._execution_guard(tool, params)
                        if deferred is not None:
                            return deferred
                else:
                    # Headless input is never fabricated: a confirmation
                    # requirement with no input channel is an explicit
                    # needs-input denial, distinct from a user denial.
                    return ToolResult(
                        content=(
                            f"Tool '{name}' requires user confirmation, which is not "
                            "available in this session. The action was not executed."
                        ),
                        success=False,
                        error="Confirmation required but no confirmation handler is available",
                    )

        stale = self._revalidate_authorization(authorization, params)
        return stale if stale is not None else authorization

    async def authorize(self, name: str, params: dict[str, object]) -> Tool | ToolResult:
        """Return a currently authorized tool or denial without executing it.

        Revalidate after awaited approval. Unchanged grants are shared across
        registry ancestry; changed registrations, projects or physical targets
        require fresh approval. Custom dispatchers must perform any additional
        checks needed after their own subsequent asynchronous work.
        """
        authorization = await self._authorize_invocation(name, params)
        return authorization if isinstance(authorization, ToolResult) else authorization.tool

    async def execute(self: ToolRegistry, name: str, params: dict[str, object]) -> ToolResult:
        """Execute a tool by name with the given parameters.

        This method handles the full execution flow:
        1. Look up the tool
        2. Check Plan Mode restrictions
        3. Check if confirmation is needed (unless auto-approved or READ tool)
        4. Call confirmation handler if needed; an unavailable handler yields
           an explicit needs-input denial, never a silent approval
        5. Execute the tool if approved (with retries for NETWORK tools)

        Args:
            name: The name of the tool to execute.
            params: The parameters to pass to the tool.

        Returns:
            A ToolResult containing the execution result or error.
        """
        authorization = await self._authorize_invocation(name, params)
        if isinstance(authorization, ToolResult):
            return authorization
        tool = authorization.tool

        async def execute_once() -> ToolResult:
            # The formatter can await its mutation lock and filesystem snapshot
            # after authorization. Check again at the actual dispatch boundary.
            stale = self._revalidate_authorization(authorization, params)
            if stale is not None:
                return stale
            if self._execution_guard is not None:
                deferred = self._execution_guard(tool, params)
                if deferred is not None:
                    return deferred
            stale = self._revalidate_authorization(authorization, params)
            if stale is not None:
                return stale
            with use_access_policies(self._effective_access_policies):
                return await tool.execute(**params)

        async def execute_authorized() -> ToolResult:
            if (
                tool.execution_kind(params) == ToolKind.NETWORK
                and self._retry_config.max_retries > 0
            ):
                return await retry_async(
                    execute_once,
                    config=self._retry_config,
                )
            return await execute_once()

        # Formatting completes before verification can consume the tool result.
        try:
            if self._effective_access_policies or current_access_policies():
                # Black and workspace discovery are unmediated subprocess/I/O
                # paths. Restricted operations use only their qualified body.
                result = await execute_authorized()
            else:
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
