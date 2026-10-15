"""Tech Lead agent setup for the Orchestrator.

Creates and configures the Tech Lead agent, including identity and prompt
generation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from henchman.providers.base import ModelProvider


def setup_tech_lead(
    orch: Any,
    agent_configs: dict[str, Any],
    default_provider: ModelProvider,
    *,
    system_prompt: str | None,
    environment_context: str | None,
) -> None:
    """Set up the Tech Lead agent on the orchestrator.

    Args:
        orch: The orchestrator instance.
        agent_configs: Compatibility argument; configurations come from the pool.
        default_provider: Compatibility argument; provider resolution uses the pool.
        system_prompt: Optional custom system prompt.
        environment_context: Optional environment context.

    Returns:
        None: This function sets up the Tech Lead agent on the orchestrator
        instance but returns nothing.
    """
    del agent_configs, default_provider  # The pool owns both configuration sources.
    if not orch.tool_registry.get("delegate_task"):
        from henchman.tools.builtins.delegate import (
            DelegateTaskTool,  # Lazy to avoid circular import
        )

        orch.tool_registry.register(DelegateTaskTool())
    orch.pool.context_config.leader_system_prompt = system_prompt
    orch.pool.context_config.environment_context = environment_context
    orch.tech_lead = orch.pool.get_agent("tech_lead")
    orch.tech_lead._stall.enabled = False


def create_tech_lead_identity() -> Any:
    """Create the Tech Lead agent identity.

    Returns:
        AgentIdentity: An identity object configured for the Tech Lead role.
    """
    from henchman.agents.identity import AgentIdentity

    return AgentIdentity(
        id="tech_lead",
        name="Leader",
        role="tech_lead",
        description="Architect, implementer, and quality gate",
    )
