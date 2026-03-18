"""AgentPool manages the lifecycle and instantiation of agents in a team."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from henchman.agents.identity import AgentIdentity
from henchman.core.agent import Agent
from henchman.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from henchman.agents.config import AgentConfig
    from henchman.core.eventbus import EventBus
    from henchman.providers.base import ModelProvider
    from henchman.providers.registry import ProviderRegistry
    from henchman.tools.base import Tool


# ---------------------------------------------------------------------------
# Configuration parameter object
# ---------------------------------------------------------------------------


@dataclass
class ContextConfig:
    """Groups context-management knobs for AgentPool.

    Attributes:
        environment_context: Pre-formatted environment block injected into prompts.
        intelligent_context: Whether to use intelligent context management.
        importance_threshold: Minimum importance score to preserve a message.
        cluster_similarity_threshold: Similarity threshold for clustering messages.
        adaptive_compression: Whether to use adaptive compression techniques.
    """

    environment_context: str | None = field(default=None)
    intelligent_context: bool = field(default=False)
    importance_threshold: float = field(default=0.5)
    cluster_similarity_threshold: float = field(default=0.7)
    adaptive_compression: bool = field(default=True)


# ---------------------------------------------------------------------------
# Scoped registry factory
# ---------------------------------------------------------------------------


def create_scoped_registry(
    parent: ToolRegistry,
    allowed_tools: list[str],
    extra_tools: list["Tool"] | None = None,
    auto_approve: list[str] | None = None,
) -> ToolRegistry:
    """Create a new ToolRegistry containing only allowed tools from parent.

    Args:
        parent: The parent ToolRegistry to copy from.
        allowed_tools: Names of tools to allow.
        extra_tools: Additional tools to register.
        auto_approve: Tool names to auto-approve.

    Returns:
        A new ToolRegistry instance.
    """
    new_registry = ToolRegistry(retry_config=parent._retry_config)

    for name in allowed_tools:
        tool = parent.get(name)
        if tool:
            new_registry.register(tool)

    if extra_tools:
        for tool in extra_tools:
            if new_registry.get(tool.name):
                new_registry.unregister(tool.name)
            new_registry.register(tool)

    if parent._confirmation_handler:
        new_registry.set_confirmation_handler(parent._confirmation_handler)

    if auto_approve:
        for name in auto_approve:
            new_registry.add_auto_approve_policy(name)

    return new_registry


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _config_to_identity(role: str, config: "AgentConfig") -> AgentIdentity:
    """Build an AgentIdentity from a role name and its config.

    Args:
        role: The role ID string.
        config: The agent's configuration object.

    Returns:
        AgentIdentity populated from the config.
    """
    return AgentIdentity(
        id=role,
        name=config.name,
        role=role,
        description=config.description,
    )


# ---------------------------------------------------------------------------
# AgentPool
# ---------------------------------------------------------------------------


class AgentPool:
    """Manages a pool of agents, providing lazy instantiation and lifecycle management."""

    def __init__(
        self: "AgentPool",
        configs: dict[str, "AgentConfig"],
        default_provider: "ModelProvider",
        provider_registry: "ProviderRegistry | None",
        parent_tool_registry: ToolRegistry,
        event_bus: "EventBus",
        environment_context: str | None = None,
        *,
        intelligent_context: bool = False,
        importance_threshold: float = 0.5,
        cluster_similarity_threshold: float = 0.7,
        adaptive_compression: bool = True,
        context_config: ContextConfig | None = None,
    ) -> None:
        """Initialize the AgentPool.

        Args:
            configs: Dictionary of agent configurations.
            default_provider: The default model provider to use.
            provider_registry: Registry to look up provider overrides.
            parent_tool_registry: Registry containing all available tools.
            event_bus: The event bus for inter-agent communication.
            environment_context: Pre-formatted environment block for agents.
            intelligent_context: Whether to use intelligent context management.
            importance_threshold: Minimum importance score to preserve a message.
            cluster_similarity_threshold: Similarity threshold for clustering messages.
            adaptive_compression: Whether to use adaptive compression techniques.
            context_config: Preferred alternative to the four individual context
                kwargs above.  When provided the individual kwargs are ignored.
        """
        self.configs = configs
        self.default_provider = default_provider
        self.provider_registry = provider_registry
        self.parent_tool_registry = parent_tool_registry
        self.event_bus = event_bus

        if context_config is None:
            context_config = ContextConfig(
                environment_context=environment_context,
                intelligent_context=intelligent_context,
                importance_threshold=importance_threshold,
                cluster_similarity_threshold=cluster_similarity_threshold,
                adaptive_compression=adaptive_compression,
            )
        self.context_config = context_config
        self._agents: dict[str, Agent] = {}

    # ------------------------------------------------------------------
    # Convenience property (backward-compat delegation to context_config)
    # ------------------------------------------------------------------

    @property
    def environment_context(self: "AgentPool") -> str | None:
        """Delegating property for backward compatibility."""
        return self.context_config.environment_context

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_provider(
        self: "AgentPool",
        config: "AgentConfig",
    ) -> "ModelProvider":
        """Determine the model provider for an agent config.

        Args:
            config: The agent configuration.

        Returns:
            A ModelProvider instance, possibly overridden per-agent.
        """
        provider: ModelProvider = self.default_provider
        if config.provider and self.provider_registry:
            provider_cls = self.provider_registry.get(config.provider)
            provider = provider_cls()
            if config.model and hasattr(provider, "default_model"):
                provider.default_model = config.model
        return provider

    def _build_system_prompt(
        self: "AgentPool",
        role: str,
        config: "AgentConfig",
    ) -> str:
        """Return the system prompt for *role*, generating one if absent.

        Args:
            role: The agent role ID.
            config: The agent configuration.

        Returns:
            System prompt string.
        """
        if config.system_prompt is not None:
            return config.system_prompt

        team_members = [
            f"{c.name} ({c.role})"
            for c in self.configs.values()
            if c.enabled
        ]
        from henchman.agents.prompts import get_agent_prompt

        return get_agent_prompt(
            role=role,
            team_members=team_members,
            delegatable_agents=config.can_delegate_to,
            environment_context=self.context_config.environment_context,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_agent(self: "AgentPool", role: str) -> Agent:
        """Get or lazily create an agent by role.

        Args:
            role: The role ID of the agent to get.

        Returns:
            An instantiated Agent.

        Raises:
            ValueError: If the role is not configured.
        """
        if role in self._agents:
            return self._agents[role]

        if role not in self.configs:
            msg = f"Agent role '{role}' is not configured."
            raise ValueError(msg)

        config = self.configs[role]
        provider = self._resolve_provider(config)
        scoped_registry = create_scoped_registry(
            parent=self.parent_tool_registry,
            allowed_tools=config.tools,
            auto_approve=config.auto_approve,
        )
        system_prompt = self._build_system_prompt(role, config)
        identity = _config_to_identity(role, config)
        ctx = self.context_config

        agent = Agent(
            provider=provider,
            tool_registry=scoped_registry,
            system_prompt=system_prompt,
            model=config.model,
            identity=identity,
            intelligent_context=ctx.intelligent_context,
            importance_threshold=ctx.importance_threshold,
            cluster_similarity_threshold=ctx.cluster_similarity_threshold,
            adaptive_compression=ctx.adaptive_compression,
        )

        self._agents[role] = agent
        return agent

    def get_identity(self: "AgentPool", role: str) -> AgentIdentity:
        """Get the identity of a configured agent.

        Args:
            role: The role ID.

        Returns:
            AgentIdentity from configuration.
        """
        if role not in self.configs:
            msg = f"Agent role '{role}' is not configured."
            raise ValueError(msg)
        return _config_to_identity(role, self.configs[role])

    def list_agents(self: "AgentPool") -> list[AgentIdentity]:
        """List all configured agents.

        Returns:
            List of AgentIdentities for all configured agents.
        """
        return [
            _config_to_identity(role, config)
            for role, config in self.configs.items()
            if config.enabled
        ]

    def list_active_agents(self: "AgentPool") -> list[AgentIdentity]:
        """List all currently instantiated agents.

        Returns:
            List of AgentIdentities for all active agents.
        """
        return [agent.identity for agent in self._agents.values() if agent.identity]

    def reset_agent(self: "AgentPool", role: str) -> None:
        """Reset an agent's history.

        Args:
            role: The role ID.

        Returns:
            None
        """
        if role in self._agents:
            self._agents[role].clear_history()

    def reset_all(self: "AgentPool") -> None:
        """Reset history for all agents in the pool.

        Returns:
            None
        """
        for agent in self._agents.values():
            agent.clear_history()

    def shutdown(self: "AgentPool") -> None:
        """Cleanup all agents and subscriptions.

        Returns:
            None
        """
        self._agents.clear()
