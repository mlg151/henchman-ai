"""Orchestrator for multi-agent development team.

This is the main entry point for the multi-agent system.  All supporting
types, components, and controllers live in sibling modules and are
re-exported here for backward compatibility.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from henchman.agents.delegation import DelegationRunner
from henchman.agents.metrics import OrchestratorMetrics
from henchman.core.events import AgentEvent, EventType

# Re-export symbols that external code imports from this module
from .orchestrator_execution import _last_assistant_content
from .orchestrator_init import OrchestratorConfig, init_orchestrator
from .orchestrator_run import finalize_run, prepare_run
from .orchestrator_timeout import TimeoutSummaryBuilder
from .orchestrator_types import (
    COLON_STALL_NUDGE,
    MAX_COLON_STALL_RETRIES,
    AgentLoopParams,
    CompletionStatus,
    DelegationParams,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from henchman.agents.pool import AgentPool
    from henchman.core.agent import Agent
    from henchman.core.eventbus import EventBus
    from henchman.providers.base import ModelProvider

# Backward-compat aliases used by tests
_COLON_STALL_NUDGE = COLON_STALL_NUDGE
_MAX_COLON_STALL_RETRIES = MAX_COLON_STALL_RETRIES

__all__ = [
    "_COLON_STALL_NUDGE",
    "_MAX_COLON_STALL_RETRIES",
    "AgentLoopParams",
    "CompletionStatus",
    "DelegationParams",
    "Orchestrator",
    "OrchestratorConfig",
    "OrchestratorMetrics",
    "TimeoutSummaryBuilder",
]


class Orchestrator:
    """Orchestrates a team of agents to solve complex tasks."""

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
        init_orchestrator(self, default_provider, config, **kwargs)

    # ------------------------------------------------------------------
    # Public run methods
    # ------------------------------------------------------------------

    async def run(
        self: Orchestrator,
        user_input: str,
    ) -> AsyncIterator[AgentEvent]:
        """Run the orchestrator with user input."""
        prepare_run(self, user_input)
        yield AgentEvent(
            type=EventType.AGENT_STARTED,
            data={"agent": "tech_lead"},
            source_agent="orchestrator",
        )
        async for event in self.execution_controller.run_agent_loop(
            AgentLoopParams(agent=self.tech_lead, input_text=user_input),
        ):
            yield event
        for event in finalize_run(self, self.tech_lead, "tech_lead"):
            yield event

    async def run_direct(
        self: Orchestrator,
        role: str,
        user_input: str,
    ) -> AsyncIterator[AgentEvent]:
        """Run a specific agent directly, bypassing the Tech Lead."""
        agent = self.pool.get_agent(role)
        yield AgentEvent(
            type=EventType.AGENT_STARTED,
            data={"agent": role},
            source_agent="orchestrator",
        )
        async for event in self.execution_controller.run_agent_loop(
            AgentLoopParams(agent=agent, input_text=user_input),
        ):
            yield event
        for event in finalize_run(self, agent, role):
            yield event

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def get_metrics_report(self: Orchestrator) -> str:
        """Generate a formatted performance metrics dashboard."""
        return self._reporter.get_metrics_report()

    def get_pool(self: Orchestrator) -> AgentPool:
        """Get the agent pool."""
        return self.pool

    def get_event_bus(self: Orchestrator) -> EventBus:
        """Get the event bus."""
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
        return DelegationRunner._assemble_delegation_input(  # noqa: SLF001
            task, brief, mission,
        )

    @staticmethod
    def _parse_completion_report(summary: str) -> dict[str, str]:
        """Backward-compat delegate to DelegationRunner."""
        return DelegationRunner._parse_completion_report(summary)  # noqa: SLF001

    @staticmethod
    def _last_assistant_content(agent: Agent) -> str:
        """Return the last assistant message content."""
        return _last_assistant_content(agent)
