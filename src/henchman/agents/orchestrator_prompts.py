"""Prompt factory for the orchestrator module.

Builds system prompts for the Tech Lead agent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from henchman.config.schema import AgentConfig


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
            system_prompt: Nonempty runtime override; empty means no override.
            environment_context: Pre-formatted environment block for agents.

        Returns:
            The Tech Lead system prompt string.
        """
        if system_prompt:
            return system_prompt
        leader = agent_configs.get("tech_lead")
        if leader is not None and leader.system_prompt is not None:
            return leader.system_prompt
        return _build_prompt(agent_configs, environment_context)


def _build_prompt(
    agent_configs: dict[str, AgentConfig],
    environment_context: str | None,
) -> str:
    """Build the Tech Lead prompt from agent configurations."""
    from henchman.agents.prompts import get_agent_prompt

    del agent_configs  # Legacy role presets remain opt-in compatibility commands.
    return get_agent_prompt(
        role="tech_lead",
        environment_context=environment_context,
    )


def _extract_team_info(
    configs: list[AgentConfig],
) -> tuple[list[str], dict[str, str], list[str]]:
    """Extract team member info, descriptions, and delegatable agent roles."""
    members = [f"{c.name} ({c.role})" for c in configs]
    descriptions = {c.role: c.description or "" for c in configs}
    delegatable = [c.role for c in configs]
    return members, descriptions, delegatable


def _get_enabled_configs(
    agent_configs: dict[str, AgentConfig],
) -> list[AgentConfig]:
    """Return only the enabled agent configurations."""
    return [c for c in agent_configs.values() if c.enabled]
