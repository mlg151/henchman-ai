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

# Re-export symbols that external code imports from this module
from .orchestrator_execution import _last_assistant_content
from .orchestrator_init import OrchestratorConfig, init_orchestrator
from .orchestrator_run import claim_public_run, finalize_run, prepare_run
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
    from collections.abc import AsyncIterator

    from henchman.agents.ledger import TaskLedger
    from henchman.agents.metrics_reporter import MetricsReporter
    from henchman.agents.orchestrator_components import AgentValidator
    from henchman.agents.orchestrator_execution import ExecutionController
    from henchman.agents.orchestrator_tools import ToolController
    from henchman.agents.pool import AgentPool
    from henchman.agents.subagents import BackgroundSubagentManager
    from henchman.config.schema import Settings
    from henchman.core.agent import Agent
    from henchman.core.eventbus import EventBus
    from henchman.providers.base import ModelProvider
    from henchman.providers.registry import ProviderRegistry
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
        init_orchestrator(self, default_provider, config, **kwargs)

    # ------------------------------------------------------------------
    # Public run methods
    # ------------------------------------------------------------------

    async def run(
        self: Orchestrator,
        user_input: str,
        *,
        completion_requirement: CompletionRequirement = CompletionRequirement.RESPONSE,
    ) -> AsyncIterator[AgentEvent]:
        """Run the orchestrator with user input.

        Args:
            user_input: The user's input or task description.
            completion_requirement: Accept a response or require successful actions.

        Yields:
            AgentEvent: Stream of agent events including content, tool calls,
                and completion status.
        """
        with claim_public_run(self):
            params = AgentLoopParams(
                agent=self.tech_lead, input_text=user_input,
                completion_requirement=CompletionRequirement(completion_requirement),
            )
            with self.pool.claim_agent(self.tech_lead, owner=params):
                prepare_run(self, user_input)
                yield AgentEvent(
                    type=EventType.AGENT_STARTED,
                    data={"agent": "tech_lead"},
                    source_agent="orchestrator",
                )
                from henchman.agents.subagent_runtime import run_with_notifications
                from henchman.agents.subagents import subagent_actor

                try:
                    with subagent_actor("tech_lead"):
                        async with aclosing(run_with_notifications(self, params)) as stream:
                            async for event in stream:
                                yield event
                except BaseException:
                    await self.cancel_subagents()
                    raise
                for event in finalize_run(self, self.tech_lead, "tech_lead"):
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
    ) -> AsyncIterator[AgentEvent]:
        """Run a specific agent directly, bypassing the Tech Lead.

        Args:
            role: The role of the agent to run (e.g., "coder", "architect").
            user_input: The user's input or task description.
            completion_requirement: Accept a response or require successful actions.

        Yields:
            AgentEvent: Stream of agent events including content, tool calls,
                and completion status.
        """
        with claim_public_run(self):
            requirement = CompletionRequirement(completion_requirement)
            agent = self.pool.get_agent(role)
            params = AgentLoopParams(
                agent=agent, input_text=user_input, completion_requirement=requirement,
            )
            with self.pool.claim_agent(agent, owner=params):
                prepare_run(self, user_input)
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
