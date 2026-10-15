"""Base component and validation classes for the orchestrator module.

Provides the shared base class for orchestrator components
and agent behavior validation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .orchestrator_validation import (
    check_stall_failure,
    handle_valid_thinking,
    should_check_thinking,
)

if TYPE_CHECKING:
    from henchman.agents.metrics import OrchestratorMetrics
    from henchman.core.events import AgentEvent


class OrchestratorComponent:
    """Base class for orchestrator components with shared initialization."""

    def __init__(self: OrchestratorComponent, orchestrator: Any) -> None:
        """Initialize the orchestrator component.

        Args:
            orchestrator: The parent orchestrator instance.
        """
        self.orchestrator = orchestrator
        self.metrics: OrchestratorMetrics = orchestrator.metrics


class AgentValidator(OrchestratorComponent):
    """Validates agent behavior and patterns."""

    def check_thinking_pattern(
        self: AgentValidator,
        agent: Any,
    ) -> AgentEvent | None:
        """Observe optional Tech Lead planning format without rewriting history.

        Legacy providers may still emit a ``THINKING:`` prefix. Keep their
        metrics, but an absent prefix is not evidence of an incomplete task.
        Actual tool results and stall checks determine completion separately.
        """
        if not should_check_thinking(self.orchestrator, agent):
            return None

        content = agent.messages[-1].content or ""
        stripped = content.strip()

        if stripped.startswith("THINKING:"):
            handle_valid_thinking(self.metrics, content)
            return None
        return None

    def check_stall_failure(
        self: AgentValidator,
        agent: Any,
    ) -> AgentEvent | None:
        """Check if agent has stalled and report failure.

        Args:
            agent: The agent to check for stall failure.

        Returns:
            AgentEvent | None: An event if agent has stalled, None otherwise.
        """
        return check_stall_failure(self.orchestrator, agent)
