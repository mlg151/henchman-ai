"""Tool registry for managing and executing tools."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import dataclass, replace
from itertools import count
from typing import TYPE_CHECKING

from henchman.tools.access_policy import (
    ToolAccessError,
    ToolAccessPolicy,
    current_access_policies,
    use_access_policies,
    use_network_authorization,
    use_repository_read_authorization,
)
from henchman.tools.base import ConfirmationRequest, Tool, ToolKind, ToolResult
from henchman.tools.checkpoint_capture import MutationCheckpoint, use_checkpoint
from henchman.tools.contracts import SchemaContract, SchemaContractError, validate_tool_output
from henchman.tools.formatting import PythonAutoFormatter
from henchman.tools.policy import (
    ApprovalGrantStore,
    GrantKey,
    PolicyDecision,
    evaluate_effective_policy,
    grant_key_for,
    invocation_scope_digest,
)
from henchman.tools.repair_scope import RepairControlError, current_repair
from henchman.tools.security import sanitize_error_message
from henchman.utils.retry import RetryConfig, retry_async

if TYPE_CHECKING:
    from pathlib import Path

    from henchman.config.schema import ToolSettings
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
    input_contract: SchemaContract
    output_contract: SchemaContract | None


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
        self._read_confirmation_required = False
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

    def _check_execution_guards(self, tool: Tool, params: dict[str, object]) -> ToolResult | None:
        """Retain live ancestor deferrals in every scoped dispatch boundary."""
        registry: ToolRegistry | None = self
        while registry is not None:
            guard = registry._execution_guard
            if guard is not None:
                deferred = guard(tool, params)
                if deferred is not None:
                    return deferred
            registry = registry._policy_parent
        return None

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

    def set_read_confirmation_required(self, required: bool) -> None:
        """Set trusted local read approval policy without widening an ancestor."""
        if self._read_confirmation_required != required:
            self._policy_generation += 1
        self._read_confirmation_required = required

    def restrict_tool_settings(self, settings: ToolSettings, *, project_root: Path) -> None:
        """Bind configured tool controls without weakening existing restrictions."""
        policy = ToolAccessPolicy.from_settings(settings, project_root=project_root)
        self.restrict_access_policy(policy)
        if not settings.auto_approve_read:
            self.set_read_confirmation_required(True)

    @property
    def _effective_read_confirmation(self) -> bool:
        return self._read_confirmation_required or (
            self._policy_parent is not None and self._policy_parent._effective_read_confirmation
        )

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
        # Compile before publication; even unused definitions must be local,
        # bounded and valid. Invalid registration cannot leave a visible tool.
        SchemaContract(tool.parameters)
        output_schema = tool.output_schema
        if output_schema is not None:
            SchemaContract(output_schema)
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
        tools = [
            tool
            for name in self.list_tools()
            if (tool := self.get(name)) is not None
        ]
        repair = current_repair()
        if repair is not None:
            tools = repair.disclosed_tools(tools)
        return [tool.to_declaration() for tool in tools]

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
            require_read_confirmation=self._effective_read_confirmation,
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
            require_read_confirmation=self._effective_read_confirmation,
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
            input_contract = SchemaContract(tool.parameters)
            output_schema = tool.output_schema
            output_contract = SchemaContract(output_schema) if output_schema is not None else None
            scope = invocation_scope_digest(tool, params)
        except SchemaContractError as exc:
            return ToolResult(content=str(exc), success=False, error=str(exc))
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
            input_contract=input_contract,
            output_contract=output_contract,
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
            or current.input_contract.schema != authorization.input_contract.schema
            or (current.output_contract.schema if current.output_contract is not None else None)
            != (authorization.output_contract.schema if authorization.output_contract is not None else None)
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
        repair = current_repair()
        if repair is not None:
            repair.paths(tool, params)
        deferred = self._check_execution_guards(tool, params)
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
                    deferred = self._check_execution_guards(tool, params)
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
        from henchman.tools.contracts import SchemaContractError, validate_tool_input

        candidate = self.get(name)
        if candidate is not None:
            try:
                validate_tool_input(candidate.parameters, params)
            except SchemaContractError as exc:
                return ToolResult(content=str(exc), success=False, error=str(exc))
        authorization = await self._authorize_invocation(name, params)
        return authorization if isinstance(authorization, ToolResult) else authorization.tool

    async def execute(self: ToolRegistry, name: str, params: dict[str, object]) -> ToolResult:
        """Execute a tool by name with the given parameters.

        This method handles the full execution flow:
        1. Look up the tool
        2. Check Plan Mode restrictions
        3. Resolve configured read confirmation and tool-specific approvals
        4. Call confirmation handler if needed; an unavailable handler yields
           an explicit needs-input denial, never a silent approval
        5. Execute the tool if approved (with retries for NETWORK tools)

        Args:
            name: The name of the tool to execute.
            params: The parameters to pass to the tool.

        Returns:
            A ToolResult containing the execution result or error.
        """
        from henchman.core.operation_recovery import (
            DispatchPermit,
            OperationRecoveryError,
            project_operation_result,
        )
        from henchman.core.run_budget import BudgetControlError
        from henchman.core.runtime_operations import (
            current_operation_call,
            tool_result_from_operation,
        )
        from henchman.providers.continuation import ProviderContinuationError
        from henchman.tools.contracts import SchemaContractError, validate_tool_input

        operation = current_operation_call()
        if operation is not None:
            params = deepcopy(params)
        candidate = self.get(name)
        if candidate is not None:
            try:
                validate_tool_input(candidate.parameters, params)
            except SchemaContractError as exc:
                return ToolResult(content=str(exc), success=False, error=str(exc))
        authorization = await self._authorize_invocation(name, params)
        if isinstance(authorization, ToolResult):
            return authorization
        tool = authorization.tool
        repair = current_repair()
        permit: DispatchPermit | None = None
        prepared = False
        capture: MutationCheckpoint | None = None
        formatter_authorization: _Authorization | None = None

        def check_repair_authorization() -> None:
            assert repair is not None
            repair.check_implementation(tool)
            current = formatter_authorization or authorization
            stale = self._revalidate_authorization(current, params, require_grant=formatter_authorization is None)
            if (authorization.confirmation is not None
                and not authorization.grants.is_granted(authorization.key)):
                raise RepairControlError("Repair approval was withdrawn")
            if stale is None:
                stale = self._check_execution_guards(tool, params)
            if stale is not None or self._revalidate_authorization(current, params, require_grant=formatter_authorization is None) is not None:
                raise RepairControlError("Repair tool approval, instructions or live policy changed")
        if operation is not None:
            previous = next((record for record in operation.run.journal.report().records
                             if record.operation_id == operation.binding.operation_id), None)
            if previous is not None and previous.state == "completed":
                # A replayed observation must skip formatter mutation as well as
                # the tool body. Revalidate its captured definition first.
                previous = operation.prepare(name, params, "read" if tool.execution_kind(params) == ToolKind.READ else "effectful")
                assert previous.result is not None
                return tool_result_from_operation(previous.result)

        async def execute_once() -> ToolResult:
            nonlocal permit, prepared, formatter_authorization
            try:
                validate_tool_input(tool.parameters, params)
            except SchemaContractError as exc:
                return ToolResult(content=str(exc), success=False, error=str(exc))
            # The formatter can await its mutation lock and filesystem snapshot
            # after authorization. Check again at the actual dispatch boundary.
            stale = self._revalidate_authorization(authorization, params)
            if stale is not None:
                return stale
            deferred = self._check_execution_guards(tool, params)
            if deferred is not None:
                return deferred
            stale = self._revalidate_authorization(authorization, params)
            if stale is not None:
                return stale
            if repair is not None:
                await repair.admit(tool, params)
                check_repair_authorization()
            if operation is not None:
                record = operation.prepare(name, params, "read" if tool.execution_kind(params) == ToolKind.READ else "effectful")
                if record.state == "completed" and record.result is not None:
                    return tool_result_from_operation(record.result)
                prepared = True
                assert capture is not None
                await capture.begin()
                if repair is not None:
                    await repair.admit(tool, params)
                # Capture awaits bounded filesystem work. Its scope conveys no
                # authority: policy, tool identity, targets and guards must all
                # still permit this invocation immediately before its effect.
                stale = self._revalidate_authorization(authorization, params)
                if stale is None:
                    stale = self._check_execution_guards(tool, params)
                if stale is None:
                    stale = self._revalidate_authorization(authorization, params)
                if stale is not None:
                    operation.cancel()
                    return stale
                permit = operation.start()
                if permit is None:
                    raise OperationRecoveryError("operation_already_dispatched")
            if repair is not None:
                await asyncio.sleep(0)
                repair.check()
                check_repair_authorization()
            if capture is not None and permit is not None:
                capture.dispatched = True
            with use_access_policies(self._effective_access_policies):
                from henchman.tools.builtins.pattern_search import PatternSearchTool
                from henchman.tools.builtins.web_fetch import WebFetchTool

                if (type(tool) is PatternSearchTool and params.get("strategy") == "repository"
                    and getattr(tool.execute, "__func__", None) is PatternSearchTool.execute):
                    implementation = getattr(tool.execute, "__func__", None)
                    repository_binding = tool._workspace
                    repository_session = tool._session_manager

                    def check_repository_authorization() -> None:
                        if (self._revalidate_authorization(authorization, params) is not None
                            or getattr(tool.execute, "__func__", None) is not implementation
                            or tool._workspace is not repository_binding
                            or tool._session_manager is not repository_session):
                            raise ToolAccessError("Repository search authorization changed")
                        if self._check_execution_guards(tool, params) is not None:
                            raise ToolAccessError("Repository search deferred by execution guard")
                        if (self._revalidate_authorization(authorization, params) is not None
                            or getattr(tool.execute, "__func__", None) is not implementation
                            or tool._workspace is not repository_binding
                            or tool._session_manager is not repository_session):
                            raise ToolAccessError("Repository search authorization changed")

                    with use_repository_read_authorization(check_repository_authorization):
                        repository_execute: Callable[..., Awaitable[ToolResult]] = tool.execute
                        return await repository_execute(**params)
                if type(tool) is WebFetchTool and getattr(tool.execute, "__func__", None) is WebFetchTool.execute:
                    implementation = getattr(tool.execute, "__func__", None)

                    def check_network_authorization() -> None:
                        # Admission evaluates static restrictions only. Calling
                        # it here cannot recursively invoke this live lease.
                        stale = self._revalidate_authorization(authorization, params)
                        if stale is not None or getattr(tool.execute, "__func__", None) is not implementation:
                            raise ToolAccessError("Network operation authorization changed; retry for fresh approval")
                        if self._check_execution_guards(tool, params) is not None:
                            raise ToolAccessError("Network operation deferred by the current execution guard")
                        # A trusted repeatable guard can itself update policy.
                        if (self._revalidate_authorization(authorization, params) is not None
                            or getattr(tool.execute, "__func__", None) is not implementation):
                            raise ToolAccessError("Network operation authorization changed; retry for fresh approval")

                    with use_network_authorization(check_network_authorization):
                        return await tool.execute(**params)
                result = await tool.execute(**params)
                if repair is not None and capture is not None and capture.dispatched and capture.paths:
                    # Qualified edit/write bodies can replace their file inode.
                    # Capture that owned outcome before yielding; only formatting
                    # may use it, and the original grant must remain live.
                    observed = self._capture_authorization(tool.name, params)
                    if isinstance(observed, ToolResult):
                        raise RepairControlError("Repair authorization changed after its tool effect")
                    key = replace(authorization.key, scope_digest=observed.key.scope_digest)
                    if key != observed.key:
                        raise RepairControlError("Repair authorization changed after its tool effect")
                    formatter_authorization = replace(authorization, key=key)
                    check_repair_authorization()
                return result

        async def execute_authorized() -> ToolResult:
            if (
                tool.execution_kind(params) == ToolKind.NETWORK
                and operation is None
                and self._retry_config.max_retries > 0
            ):
                return await retry_async(
                    execute_once,
                    config=self._retry_config,
                )
            return await execute_once()

        # Formatting completes before verification can consume the tool result.
        try:
            capture = MutationCheckpoint(operation, tool, params,
                                         lambda: bool(self._effective_access_policies or current_access_policies()))
            with use_checkpoint(capture), repair.invocation(check_repair_authorization) if repair is not None else nullcontext():
                try:
                    if self._effective_access_policies or current_access_policies():
                        # Black and workspace discovery are unmediated subprocess/I/O
                        # paths. Restricted operations use only their qualified body.
                        result = await execute_authorized()
                    else:
                        result = await self._effective_formatter.run(tool, params, execute_authorized)
                finally:
                    # The shared formatter finalizes under its mutation lock.
                    # Bypassed/custom formatters still join capture cleanup here.
                    await capture.finish(sys.exception())
        except BaseException as exc:
            if operation is not None and prepared:
                operation.cancel_after_error(exc)
                if permit is not None and isinstance(exc, Exception) and not isinstance(exc, (OperationRecoveryError, BudgetControlError, ProviderContinuationError, RepairControlError)):
                    raise OperationRecoveryError("outcome_unknown") from exc
            if isinstance(exc, (OperationRecoveryError, BudgetControlError, ProviderContinuationError, RepairControlError)) or not isinstance(exc, Exception):
                raise
            sanitized_error = sanitize_error_message(exc)
            return ToolResult(
                content=f"Error executing tool '{name}': {sanitized_error}",
                success=False,
                error=sanitized_error,
            )

        try:
            result = validate_tool_output(result, authorization.output_contract)
        except SchemaContractError as exc:
            # The effect already ran. Preserve a completed failure observation,
            # never a retryable exception or unvalidated successful payload.
            result = ToolResult(content=str(exc), success=False, error=str(exc))

        if capture is not None:
            result = capture.project(result)

        if operation is not None and permit is not None:
            try:
                projected = project_operation_result(result.content, result.success, result.error,
                                                     redactor=operation.run.session.evidence_redactor,
                                                     content_blocks=result.content_blocks, structured_content=result.structured_content,
                                                     structured_content_present=result.structured_content_present, metadata=result.metadata)
                operation.complete(permit, projected)
            except BaseException as exc:
                operation.cancel_after_error(exc)
                if isinstance(exc, (OperationRecoveryError, BudgetControlError, ProviderContinuationError, RepairControlError)) or not isinstance(exc, Exception):
                    raise
                raise OperationRecoveryError("operation_result_unavailable") from exc
            return tool_result_from_operation(projected, display=result.display)

        # Truncate large outputs to prevent context overflow
        if result.content and len(result.content) > MAX_TOOL_OUTPUT:
            truncated_content = result.content[:MAX_TOOL_OUTPUT]
            truncated_content += f"\n\n[... truncated after {MAX_TOOL_OUTPUT} chars]"
            result = replace(result, content=truncated_content)

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
        from henchman.core.operation_recovery import OperationRecoveryError
        from henchman.core.run_budget import BudgetControlError
        from henchman.providers.continuation import ProviderContinuationError

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
            if isinstance(result, (OperationRecoveryError, BudgetControlError, ProviderContinuationError, RepairControlError)):
                raise result
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
