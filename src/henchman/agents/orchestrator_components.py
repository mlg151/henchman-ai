"""Base component and validation classes for the orchestrator module.

Provides the shared base class for orchestrator components
and agent behavior validation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .orchestrator_validation import (
    check_stall_failure,
    handle_missing_thinking,
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
        """Validate Tech Lead thinking patterns and update metrics.
        
        Args:
            agent: The agent to validate thinking patterns for.
            
        Returns:
            AgentEvent | None: An event if thinking pattern is missing, None otherwise.
        """
        if not should_check_thinking(self.orchestrator, agent):
            return None

        content = agent.messages[-1].content or ""
        stripped = content.strip()

        if stripped.startswith("THINKING:"):
            handle_valid_thinking(self.metrics, content)
            return None
        if stripped:
            return handle_missing_thinking(agent)
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
