"""Tech Lead agent setup for the Orchestrator.

Creates and configures the Tech Lead agent, including identity and prompt
generation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from henchman.core.agent import Agent
from henchman.tools.builtins.delegate import DelegateTaskTool

from .orchestrator_prompts import PromptFactory

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
        agent_configs: Merged agent configurations.
        default_provider: The default model provider.
        system_prompt: Optional custom system prompt.
        environment_context: Optional environment context.
    """
    if not orch.tool_registry.get("delegate_task"):
        orch.tool_registry.register(DelegateTaskTool())
    tl_prompt = PromptFactory.create_tech_lead_prompt(
        agent_configs, system_prompt, environment_context,
    )
    ctx = orch.settings.context
    orch.tech_lead = Agent(
        provider=default_provider,
        tool_registry=orch.tool_registry,
        system_prompt=tl_prompt,
        identity=create_tech_lead_identity(),
        intelligent_context=ctx.intelligent_context,
        importance_threshold=ctx.importance_threshold,
        cluster_similarity_threshold=ctx.cluster_similarity_threshold,
        adaptive_compression=ctx.adaptive_compression,
    )
    orch.tech_lead._stall.enabled = False  # noqa: SLF001


def create_tech_lead_identity() -> Any:
    """Create the Tech Lead agent identity."""
    from henchman.agents.identity import AgentIdentity  # noqa: PLC0415

    return AgentIdentity(
        id="tech_lead",
        name="Leader",
        role="tech_lead",
        description="Architect, implementer, and quality gate",
    )
