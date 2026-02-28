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
            system_prompt: Optional override for Tech Lead system prompt.
            environment_context: Pre-formatted environment block for agents.

        Returns:
            The Tech Lead system prompt string.
        """
        from henchman.agents.prompts import get_agent_prompt  # noqa: PLC0415

        enabled = _get_enabled_configs(agent_configs)
        team_members = [f"{c.name} ({c.role})" for c in enabled]
        team_descriptions = {c.role: c.description or "" for c in enabled}
        delegatable_agents = [c.role for c in enabled]

        return system_prompt or get_agent_prompt(
            role="tech_lead",
            team_members=team_members,
            delegatable_agents=delegatable_agents,
            environment_context=environment_context,
            team_descriptions=team_descriptions,
        )


def _get_enabled_configs(
    agent_configs: dict[str, AgentConfig],
) -> list[AgentConfig]:
    """Return only the enabled agent configurations."""
    return [c for c in agent_configs.values() if c.enabled]
