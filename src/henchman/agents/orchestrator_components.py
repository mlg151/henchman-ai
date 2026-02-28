"""Base component and validation classes for the orchestrator module.

Provides the shared base class for orchestrator components,
agent behavior validation, and tool metrics tracking.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import Message

from .orchestrator_types import (
    MAX_THINKING_SCORE,
    MIN_THINKING_LINES,
    THINKING_QUALITY_INCREMENT,
    TOOL_ERROR_MAX_LENGTH,
)

if TYPE_CHECKING:
    from henchman.agents.metrics import OrchestratorMetrics


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
        """Validate Tech Lead thinking patterns and update metrics."""
        if not _should_check_thinking(self.orchestrator, agent):
            return None

        content = agent.messages[-1].content or ""
        stripped = content.strip()

        if stripped.startswith("THINKING:"):
            _handle_valid_thinking(self.metrics, content)
            return None
        if stripped:
            return _handle_missing_thinking(agent)
        return None

    def check_stall_failure(
        self: AgentValidator,
        agent: Any,
    ) -> AgentEvent | None:
        """Check if agent has stalled and report failure."""
        return _check_stall_failure(self.orchestrator, agent)


class ToolMetricsController(OrchestratorComponent):
    """Manages tool metrics and error tracking."""

    def update_tool_metrics(
        self: ToolMetricsController,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        success: bool,
    ) -> None:
        """Update metrics for a tool call."""
        self.metrics.update_tool_metrics(tool_name, arguments, success)

    def track_tool_error(
        self: ToolMetricsController,
        tool_errors: list[str],
        tool_name: str,
        result_content: str | None,
    ) -> None:
        """Track tool errors for delegation summaries."""
        error_message = result_content or "unknown error"
        tool_errors.append(
            f"{tool_name}: {error_message[:TOOL_ERROR_MAX_LENGTH]}",
        )

    def update_delegation_metrics(
        self: ToolMetricsController,
        target: str,
    ) -> None:
        """Update metrics for a delegation."""
        self.metrics.delegation_count += 1
        if target in self.metrics.delegation_by_type:
            self.metrics.delegation_by_type[target] += 1


# ---------------------------------------------------------------------------
# Module-level helpers (extracted to reduce class size / feature envy)
# ---------------------------------------------------------------------------


def _should_check_thinking(orchestrator: Any, agent: Any) -> bool:
    """Determine if thinking pattern should be checked for this agent."""
    return (
        agent is orchestrator.tech_lead
        and bool(agent.messages)
        and agent.messages[-1].role == "assistant"
    )


def _handle_valid_thinking(metrics: Any, content: str) -> None:
    """Handle valid thinking pattern and update metrics."""
    metrics.thinking_pattern_usage += 1
    lines = content.strip().split("\n")
    numbered = [
        ln for ln in lines
        if ln.strip().startswith(("1.", "2.", "3.", "4.", "5."))
    ]
    if len(numbered) >= MIN_THINKING_LINES:
        metrics.thinking_quality_score = min(
            MAX_THINKING_SCORE,
            metrics.thinking_quality_score + THINKING_QUALITY_INCREMENT,
        )


def _handle_missing_thinking(agent: Any) -> AgentEvent:
    """Handle missing thinking pattern by adding reminder."""
    reminder = (
        "\n[Thinking Required] Your response must start with THINKING: "
        "followed by your reasoning process. Please revise."
    )
    agent.messages.append(Message(role="user", content=reminder))
    return AgentEvent(
        type=EventType.THINKING_REQUIRED,
        data="Thinking pattern missing in Tech Lead response",
        source_agent="orchestrator",
    )


def _check_stall_failure(orchestrator: Any, agent: Any) -> AgentEvent | None:
    """Check if agent has stalled and report failure."""
    if agent is orchestrator.tech_lead:
        return None
    if not getattr(agent, "_stall_failure", False):
        return None

    role_label = agent.identity.role if agent.identity else "agent"
    nudge_count = getattr(agent, "_stall_nudge_count", 0)
    fail_msg = (
        f"STALL FAILURE: {role_label} announced intent but "
        f"never used tools after {nudge_count} nudges. "
        f"The task was NOT completed."
    )
    agent.messages.append(Message(role="assistant", content=fail_msg))
    return AgentEvent(
        type=EventType.ERROR,
        data=fail_msg,
        source_agent=role_label,
    )
