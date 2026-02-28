"""Support components for the orchestrator module.

Includes prompt building, timeout summaries, agent validation,
and metric tracking helpers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import Message

from .orchestrator_types import (
    MAX_NARRATION_DISPLAY_LENGTH,
    MAX_SUMMARY_LENGTH,
    MAX_THINKING_SCORE,
    MAX_TOOL_ARGUMENTS_TO_DISPLAY,
    MAX_TOOL_CALL_DISPLAY_LENGTH,
    MIN_THINKING_LINES,
    RECENT_TOOLS_TO_SHOW,
    THINKING_QUALITY_INCREMENT,
    TOOL_ERROR_MAX_LENGTH,
)

if TYPE_CHECKING:
    from henchman.agents.metrics import OrchestratorMetrics
    from henchman.config.schema import AgentConfig
    from henchman.providers.base import ToolCall


class PromptFactory:
    """Factory for creating agent system prompts."""

    @staticmethod
    def create_tech_lead_prompt(
        agent_configs: dict[str, AgentConfig],
        system_prompt: str | None,
        environment_context: str | None,
    ) -> str:
        """Create the Tech Lead system prompt.

        Args:
            agent_configs: Dictionary of agent configurations.
            system_prompt: Optional override for Tech Lead system prompt.
            environment_context: Pre-formatted environment block for agents.

        Returns:
            The Tech Lead system prompt string.
        """
        from henchman.agents.prompts import get_agent_prompt  # noqa: PLC0415

        enabled = _get_enabled_agent_configs(agent_configs)
        team_members = _build_team_members_list(enabled)
        team_descriptions = _build_team_descriptions_dict(enabled)
        delegatable_agents = _build_delegatable_agents_list(enabled)

        return system_prompt or get_agent_prompt(
            role="tech_lead",
            team_members=team_members,
            delegatable_agents=delegatable_agents,
            environment_context=environment_context,
            team_descriptions=team_descriptions,
        )


def _get_enabled_agent_configs(
    agent_configs: dict[str, AgentConfig],
) -> list[AgentConfig]:
    """Get enabled agent configurations from the config dictionary."""
    return [c for c in agent_configs.values() if c.enabled]


def _build_team_members_list(enabled_configs: list[AgentConfig]) -> list[str]:
    """Build list of team member descriptions."""
    return [f"{config.name} ({config.role})" for config in enabled_configs]


def _build_team_descriptions_dict(
    enabled_configs: list[AgentConfig],
) -> dict[str, str]:
    """Build dictionary of role descriptions."""
    return {config.role: config.description or "" for config in enabled_configs}


def _build_delegatable_agents_list(
    enabled_configs: list[AgentConfig],
) -> list[str]:
    """Build list of delegatable agent roles."""
    return [config.role for config in enabled_configs]


class TimeoutSummaryBuilder:
    """Helper for building timeout summaries for agents."""

    @classmethod
    def build_summary(
        cls: type[TimeoutSummaryBuilder],
        agent: Any,
        msg_start: int,
    ) -> str:
        """Build a progress summary from the agent's work so far.

        Called when a specialist hits the turn limit.  Extracts tool calls
        that were executed and any assistant narration so the Tech Lead
        knows what was accomplished and can resume or reassign.

        Args:
            agent: The agent that timed out.
            msg_start: Index where this delegation's messages began.

        Returns:
            A formatted progress summary string.
        """
        tools_used: list[str] = []
        files_touched: set[str] = set()
        narration_parts: list[str] = []

        assistant_messages = [
            m for m in agent.messages[msg_start:] if m.role == "assistant"
        ]
        for msg in assistant_messages:
            _extract_msg_info(msg, tools_used, files_touched, narration_parts)

        return _format_summary(tools_used, files_touched, narration_parts)


def _extract_msg_info(
    msg: Message,
    tools_used: list[str],
    files_touched: set[str],
    narration_parts: list[str],
) -> None:
    """Extract information from a message for timeout summary."""
    msg_tool_calls = msg.tool_calls
    msg_content = msg.content
    if msg_tool_calls:
        for tc in msg_tool_calls:
            _extract_tool_info(tc, tools_used, files_touched)
    if msg_content:
        narration_parts.append(msg_content[:MAX_SUMMARY_LENGTH])


def _extract_tool_info(
    tc: ToolCall,
    tools_used: list[str],
    files_touched: set[str],
) -> None:
    """Extract tool call information for timeout summary."""
    tc_args = tc.arguments
    args_str = ", ".join(
        f"{k}={v!r}"
        for k, v in list(tc_args.items())[:MAX_TOOL_ARGUMENTS_TO_DISPLAY]
    )
    tools_used.append(f"{tc.name}({args_str})")

    path = tc_args.get("path") or tc_args.get("file_path")
    if path and isinstance(path, str):
        files_touched.add(path)


def _format_summary(
    tools_used: list[str],
    files_touched: set[str],
    narration_parts: list[str],
) -> str:
    """Format timeout summary from collected information."""
    lines = ["**Progress at timeout:**"]
    _add_tools_section(lines, tools_used)
    _add_files_section(lines, files_touched)
    _add_narration_section(lines, narration_parts)
    _add_no_progress_section(lines, tools_used, narration_parts)
    return "\n".join(lines)


def _add_tools_section(lines: list[str], tools_used: list[str]) -> None:
    """Add tool usage section to summary lines."""
    if tools_used:
        lines.append(f"- Tool calls made: {len(tools_used)}")
        for tool in tools_used[-RECENT_TOOLS_TO_SHOW:]:
            lines.append(f"  \u2022 {tool[:MAX_TOOL_CALL_DISPLAY_LENGTH]}")


def _add_files_section(lines: list[str], files_touched: set[str]) -> None:
    """Add files touched section to summary lines."""
    if files_touched:
        lines.append(f"- Files touched: {', '.join(sorted(files_touched))}")


def _add_narration_section(
    lines: list[str],
    narration_parts: list[str],
) -> None:
    """Add narration section to summary lines."""
    if narration_parts:
        lines.append(
            f"- Last agent output: {narration_parts[-1][:MAX_NARRATION_DISPLAY_LENGTH]}",
        )


def _add_no_progress_section(
    lines: list[str],
    tools_used: list[str],
    narration_parts: list[str],
) -> None:
    """Add no progress section if nothing was done."""
    if not tools_used and not narration_parts:
        lines.append("- No significant progress was made.")


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
        if not self._should_check_thinking_pattern(agent):
            return None

        content = agent.messages[-1].content or ""
        stripped = content.strip()

        if stripped.startswith("THINKING:"):
            self._handle_valid_thinking_pattern(content)
            return None
        if stripped:
            return self._handle_missing_thinking_pattern(agent)
        return None

    def _should_check_thinking_pattern(
        self: AgentValidator,
        agent: Any,
    ) -> bool:
        """Determine if thinking pattern should be checked for this agent."""
        return (
            agent is self.orchestrator.tech_lead
            and bool(agent.messages)
            and agent.messages[-1].role == "assistant"
        )

    def _handle_valid_thinking_pattern(
        self: AgentValidator,
        content: str,
    ) -> None:
        """Handle valid thinking pattern and update metrics."""
        self.metrics.thinking_pattern_usage += 1
        lines = content.strip().split("\n")
        thinking_lines = [
            line
            for line in lines
            if line.strip().startswith(("1.", "2.", "3.", "4.", "5."))
        ]
        if len(thinking_lines) >= MIN_THINKING_LINES:
            self.metrics.thinking_quality_score = min(
                MAX_THINKING_SCORE,
                self.metrics.thinking_quality_score + THINKING_QUALITY_INCREMENT,
            )

    def _handle_missing_thinking_pattern(
        self: AgentValidator,
        agent: Any,
    ) -> AgentEvent:
        """Handle missing thinking pattern by adding reminder and returning event."""
        thinking_reminder = (
            "\n[Thinking Required] Your response must start with THINKING: "
            "followed by your reasoning process. Please revise."
        )
        agent.messages.append(Message(role="user", content=thinking_reminder))
        return AgentEvent(
            type=EventType.THINKING_REQUIRED,
            data="Thinking pattern missing in Tech Lead response",
            source_agent="orchestrator",
        )

    def check_stall_failure(
        self: AgentValidator,
        agent: Any,
    ) -> AgentEvent | None:
        """Check if agent has stalled and report failure."""
        if not self._should_check_stall_failure(agent):
            return None

        fail_msg = self._create_stall_failure_message(agent)
        agent.messages.append(Message(role="assistant", content=fail_msg))
        return self._create_stall_failure_event(agent, fail_msg)

    def _should_check_stall_failure(
        self: AgentValidator,
        agent: Any,
    ) -> bool:
        """Determine if stall failure should be checked for this agent."""
        return agent is not self.orchestrator.tech_lead and getattr(
            agent, "_stall_failure", False,
        )

    def _create_stall_failure_message(
        self: AgentValidator,
        agent: Any,
    ) -> str:
        """Create stall failure message for the agent."""
        role_label = agent.identity.role if agent.identity else "agent"
        stall_nudge_count = getattr(agent, "_stall_nudge_count", 0)
        return (
            f"STALL FAILURE: {role_label} announced intent but "
            f"never used tools after "
            f"{stall_nudge_count} nudges. "
            f"The task was NOT completed."
        )

    def _create_stall_failure_event(
        self: AgentValidator,
        agent: Any,
        fail_msg: str,
    ) -> AgentEvent:
        """Create stall failure event."""
        role_label = agent.identity.role if agent.identity else "agent"
        return AgentEvent(
            type=EventType.ERROR,
            data=fail_msg,
            source_agent=role_label,
        )


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
        truncated_error = error_message[:TOOL_ERROR_MAX_LENGTH]
        tool_errors.append(f"{tool_name}: {truncated_error}")

    def update_delegation_metrics(
        self: ToolMetricsController,
        target: str,
    ) -> None:
        """Update metrics for a delegation."""
        self.metrics.delegation_count += 1
        if target in self.metrics.delegation_by_type:
            self.metrics.delegation_by_type[target] += 1
