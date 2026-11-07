"""Orchestrator for multi-agent development team.

This is the main entry point for the multi-agent system.  All supporting
types, components, and controllers live in sibling modules and are
re-exported here for backward compatibility.
"""

from __future__ import annotations

from contextlib import aclosing
from typing import TYPE_CHECKING, Any

from henchman.agents.delegation import DelegationRunner
from henchman.agents.metrics import OrchestratorMetrics
from henchman.core.events import AgentEvent, EventType
from henchman.core.operation_recovery import OperationRecoveryError
from henchman.core.run_accounting import RunInvocation, public_run_budget
from henchman.core.run_budget import BudgetControlError
from henchman.core.runtime_accounting import budgeted_events
from henchman.core.runtime_operations import operated_events
from henchman.providers.runtime_budget import current_run_budget

# Re-export symbols that external code imports from this module
from .orchestrator_execution import _last_assistant_content
from .orchestrator_init import OrchestratorConfig, init_orchestrator
from .orchestrator_run import claim_public_run, finalize_run, prepare_run, primary_actor_events
from .orchestrator_timeout import TimeoutSummaryBuilder
from .orchestrator_types import (
    COLON_STALL_NUDGE,
    MAX_COLON_STALL_RETRIES,
    AgentLoopParams,
    CompletionRequirement,
    CompletionStatus,
    DelegationParams,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator

    from henchman.agents.ledger import TaskLedger
    from henchman.agents.metrics_reporter import MetricsReporter
    from henchman.agents.orchestrator_components import AgentValidator
    from henchman.agents.orchestrator_execution import ExecutionController
    from henchman.agents.orchestrator_tools import ToolController
    from henchman.agents.pool import AgentPool
    from henchman.agents.subagents import BackgroundSubagentManager
    from henchman.config.context import ContextSnapshot
    from henchman.config.schema import Settings
    from henchman.core.agent import Agent
    from henchman.core.eventbus import EventBus
    from henchman.core.session_operations import SessionRunOperations
    from henchman.core.session_run_accounting import SessionRunAccounting
    from henchman.providers.base import ModelProvider
    from henchman.providers.registry import ProviderRegistry
    from henchman.providers.runtime_budget import RunBudgetScope
    from henchman.tools.registry import ToolRegistry

# Backward-compat aliases used by tests
_COLON_STALL_NUDGE = COLON_STALL_NUDGE
_MAX_COLON_STALL_RETRIES = MAX_COLON_STALL_RETRIES

__all__ = [
    "_COLON_STALL_NUDGE",
    "_MAX_COLON_STALL_RETRIES",
    "AgentLoopParams",
    "CompletionRequirement",
    "CompletionStatus",
    "DelegationParams",
    "Orchestrator",
    "OrchestratorConfig",
    "OrchestratorMetrics",
    "TimeoutSummaryBuilder",
]


class Orchestrator:
    """Orchestrates a team of agents to solve complex tasks."""

    instruction_snapshot: ContextSnapshot | None

    default_provider: ModelProvider
    provider_registry: ProviderRegistry | None
    tool_registry: ToolRegistry
    event_bus: EventBus
    settings: Settings
    environment_context: str | None
    metrics: OrchestratorMetrics
    _reporter: MetricsReporter
    _last_loop_tool_call_count: int
    _last_loop_success_count: int
    _last_loop_timed_out: bool
    last_completion_status: CompletionStatus
    validator: AgentValidator
    tool_controller: ToolController
    execution_controller: ExecutionController
    pool: AgentPool
    shared_context: list[dict[str, Any]]
    ledger: TaskLedger | None
    tech_lead: Agent
    delegation_runner: DelegationRunner
    subagents: BackgroundSubagentManager

    def __init__(
        self: Orchestrator,
        default_provider: ModelProvider,
        config: OrchestratorConfig | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Orchestrator.

        Args:
            default_provider: The default model provider.
            config: Optional grouped configuration.
            **kwargs: Legacy keyword arguments (forwarded to OrchestratorConfig).
        """
        self._public_run_active = False
        self.last_budget_scope: RunBudgetScope | None = None
        self.accounting_runtime: SessionRunAccounting | None = None
        self.operation_runtime: SessionRunOperations | None = None
        init_orchestrator(self, default_provider, config, **kwargs)

    # ------------------------------------------------------------------
    # Public run methods
    # ------------------------------------------------------------------

    async def run(
        self: Orchestrator,
        user_input: str,
        *,
        completion_requirement: CompletionRequirement = CompletionRequirement.RESPONSE,
        budget_scope: RunBudgetScope | None = None,
        invocation: RunInvocation | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Run the team with one shared budget for primary and delegated work.

        An explicit/enclosing scope spans multiple public turns. Otherwise this
        call captures a fresh process-lifetime budget from the current settings.
        """
        async with aclosing(self._accounted_run(
            user_input, budget_scope, completion_requirement=completion_requirement,
            invocation=invocation,
        )) as events:
            async for event in events:
                yield event

    async def _run(
        self, params: AgentLoopParams,
    ) -> AsyncIterator[AgentEvent]:
        """Run the orchestrator with user input.

        Args:
            params: Loop parameters owning the target's public-run reservation.

        Yields:
            AgentEvent: Stream of agent events including content, tool calls,
                and completion status.
        """
        prepare_run(self, params.input_text)
        yield AgentEvent(
            type=EventType.AGENT_STARTED,
            data={"agent": "tech_lead"},
            source_agent="orchestrator",
        )
        from henchman.agents.subagent_runtime import run_with_notifications

        try:
            async with aclosing(run_with_notifications(self, params)) as stream:
                async for event in stream:
                    yield event
        except BaseException:
            await self.cancel_subagents()
            raise
        for event in finalize_run(self, params.agent, "tech_lead"):
            yield event

    async def cancel_subagents(self) -> None:
        """Cancel and join dynamic work while keeping the session reusable."""
        manager = getattr(self, "subagents", None)
        if manager is not None:
            await manager.cancel_all()
            manager.clear_notifications()

    async def aclose(self) -> None:
        """Cancel and join all session-owned background conversations on shutdown."""
        manager = getattr(self, "subagents", None)
        if manager is not None:
            await manager.close()

    async def run_direct(
        self: Orchestrator,
        role: str,
        user_input: str,
        *,
        completion_requirement: CompletionRequirement = CompletionRequirement.RESPONSE,
        budget_scope: RunBudgetScope | None = None,
        invocation: RunInvocation | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Run one role with shared accounting, including its delegated work."""
        async with aclosing(self._accounted_run(
            user_input, budget_scope, completion_requirement=completion_requirement,
            invocation=invocation, direct_role=role,
        )) as events:
            async for event in events:
                yield event

    async def _accounted_run(
        self, user_input: str, supplied: RunBudgetScope | None,
        *, completion_requirement: CompletionRequirement,
        invocation: RunInvocation | None = None, direct_role: str | None = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        """Claim runtime ownership before creating or recovering accounting state."""
        with claim_public_run(self):
            if invocation is not None and invocation.claimed:
                raise ValueError("Run invocation has already been claimed")
            agent = self.tech_lead if direct_role is None else self.pool.get_agent(direct_role)
            params = AgentLoopParams(
                agent=agent, input_text=user_input,
                completion_requirement=CompletionRequirement(completion_requirement),
            )
            # The same owner reenters as running=True in execution_controller.
            # Keep this reservation across awaited setup and finalization.
            with self.pool.claim_agent(agent, owner=params):
                if invocation is not None:
                    invocation.claimed = True
                self.last_budget_scope = None
                self.last_completion_status = CompletionStatus.FAILED
                await self.subagents.prepare_for_run()
                if self.operation_runtime is None:
                    from henchman.core.session_operations import SessionRunOperations

                    self.operation_runtime = SessionRunOperations.for_process(self.settings)
                operation_run = self.operation_runtime.begin(agent=agent, user_input=user_input)
                provider = agent.provider
                managed = self.accounting_runtime if supplied is None and current_run_budget() is None else None
                scope = (
                    managed.begin(provider) if managed is not None
                    else public_run_budget(self.settings, provider, supplied)
                )
                self.last_budget_scope = scope
                if invocation is not None:
                    invocation.budget_scope = scope
                stream = self._run(params) if direct_role is None else self._run_direct(direct_role, params)
                completed = False
                primary: BaseException | None = None
                try:
                    async with aclosing(primary_actor_events(operated_events(budgeted_events(stream, scope), operation_run))) as events:
                        async for event in events:
                            if (event.type == EventType.AGENT_COMPLETED
                                and event.source_agent == "orchestrator" and isinstance(event.data, dict)
                                and event.data.get("scope") == "run"):
                                completed = event.data.get("status") in {"completed", "responded"}
                            yield event
                except BaseException as exc:
                    primary = exc
                    raise
                finally:
                    cleanup: list[BaseException] = []
                    try:
                        self.operation_runtime.finish(operation_run, failed=not completed)
                    except BaseException as exc:
                        cleanup.append(exc)
                    try:
                        if managed is not None:
                            managed.finish(scope, completed=completed and not cleanup,
                                           background_active=self.subagents.has_running_work())
                    except BaseException as exc:
                        cleanup.append(exc)
                    if cleanup:
                        controls = (OperationRecoveryError, BudgetControlError)
                        # Preserve original controls/cancellation while still
                        # settling both authorities. A cleanup control outranks
                        # an ordinary error so callers cannot retry through it.
                        if primary is not None and (isinstance(primary, controls) or not isinstance(primary, Exception)):
                            primary.add_note("Runtime recovery/accounting cleanup also failed")
                        else:
                            error = next((item for item in cleanup if isinstance(item, controls)), cleanup[0])
                            if primary is None or isinstance(error, controls):
                                raise error
                            primary.add_note("Runtime recovery/accounting cleanup also failed")

    async def _run_direct(
        self, role: str, params: AgentLoopParams,
    ) -> AsyncIterator[AgentEvent]:
        """Run a specific agent directly, bypassing the Tech Lead.

        Args:
            role: The role of the agent to run (e.g., "coder", "architect").
            params: Loop parameters owning the target's public-run reservation.

        Yields:
            AgentEvent: Stream of agent events including content, tool calls,
                and completion status.
        """
        agent = params.agent
        prepare_run(self, params.input_text)
        yield AgentEvent(
            type=EventType.AGENT_STARTED,
            data={"agent": role},
            source_agent="orchestrator",
        )
        from henchman.agents.subagent_runtime import run_with_notifications

        execution = (
            run_with_notifications(self, params) if agent is self.tech_lead
            else self.execution_controller.run_agent_loop(params)
        )
        try:
            async with aclosing(execution) as stream:
                async for event in stream:
                    yield event
        except BaseException:
            await self.cancel_subagents()
            raise
        for event in finalize_run(self, agent, role):
            yield event

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def get_metrics_report(self: Orchestrator) -> str:
        """Generate a formatted performance metrics dashboard.

        Returns:
            A formatted string containing performance metrics.
        """
        return self._reporter.get_metrics_report()

    def get_pool(self: Orchestrator) -> AgentPool:
        """Get the agent pool.

        Returns:
            The AgentPool instance used by this orchestrator.
        """
        return self.pool

    def get_event_bus(self: Orchestrator) -> EventBus:
        """Get the event bus.

        Returns:
            The EventBus instance used by this orchestrator.
        """
        return self.event_bus

    # ------------------------------------------------------------------
    # Backward-compat delegates
    # ------------------------------------------------------------------

    @property
    def _delegation_runner(self: Orchestrator) -> DelegationRunner:
        """Backward-compat alias for :attr:`delegation_runner`."""
        return self.delegation_runner

    def _assess_completion(self: Orchestrator, agent: Agent) -> CompletionStatus:
        """Backward-compat delegate to execution controller."""
        return self.execution_controller.assess_completion(agent)

    @staticmethod
    def _assemble_delegation_input(
        task: str,
        brief: dict[str, Any] | None,
        mission: str | None = None,
    ) -> str:
        """Backward-compat delegate to DelegationRunner."""
        return DelegationRunner._assemble_delegation_input(
            task,
            brief,
            mission,
        )

    @staticmethod
    def _parse_completion_report(summary: str) -> dict[str, str]:
        """Backward-compat delegate to DelegationRunner."""
        return DelegationRunner._parse_completion_report(summary)

    @staticmethod
    def _last_assistant_content(agent: Agent) -> str:
        """Return the last assistant message content."""
        return _last_assistant_content(agent)
