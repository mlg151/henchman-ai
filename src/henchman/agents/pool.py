"""AgentPool manages the lifecycle and instantiation of agents in a team."""

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

    # Copy allowed tools
    for name in allowed_tools:
        tool = parent.get(name)
        if tool:
            new_registry.register(tool)

    # Add extra tools
    if extra_tools:
        for tool in extra_tools:
            # If it's already there (e.g. from parent), unregister first to avoid conflict
            if new_registry.get(tool.name):
                new_registry.unregister(tool.name)
            new_registry.register(tool)

    # Copy confirmation handler
    if parent._confirmation_handler:
        new_registry.set_confirmation_handler(parent._confirmation_handler)

    # Apply auto-approve policies
    if auto_approve:
        for name in auto_approve:
            new_registry.add_auto_approve_policy(name)

    return new_registry


class AgentPool:
    """Manages a pool of agents, providing lazy instantiation and lifecycle management."""

    def __init__(
        self,
        configs: dict[str, "AgentConfig"],
        default_provider: "ModelProvider",
        provider_registry: "ProviderRegistry | None",
        parent_tool_registry: ToolRegistry,
        event_bus: "EventBus",
    ) -> None:
        """Initialize the AgentPool.

        Args:
            configs: Dictionary of agent configurations.
            default_provider: The default model provider to use.
            provider_registry: Registry to look up provider overrides.
            parent_tool_registry: Registry containing all available tools.
            event_bus: The event bus for inter-agent communication.
        """
        self.configs = configs
        self.default_provider = default_provider
        self.provider_registry = provider_registry
        self.parent_tool_registry = parent_tool_registry
        self.event_bus = event_bus
        self._agents: dict[str, Agent] = {}

    def get_agent(self, role: str) -> Agent:
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
            raise ValueError(f"Agent role '{role}' is not configured.")

        config = self.configs[role]

        # Determine provider
        provider: ModelProvider = self.default_provider
        if config.provider and self.provider_registry:
            provider_cls = self.provider_registry.get(config.provider)
            provider = provider_cls()
            # Apply model override if specified
            # Note: Provider implementation might need to handle this
            # For now we assume the provider returned is configured correctly
            # or we just use it as is.

        # Create scoped tool registry
        scoped_registry = create_scoped_registry(
            parent=self.parent_tool_registry,
            allowed_tools=config.tools,
            auto_approve=config.auto_approve,
        )

        # Get role-specific system prompt
        from henchman.agents.prompts import get_agent_prompt

        team_members = [
            f"{c.name} ({c.role})" for c in self.configs.values() if c.enabled
        ]

        system_prompt = config.system_prompt
        if system_prompt is None:
            system_prompt = get_agent_prompt(
                role=role,
                team_members=team_members,
                delegatable_agents=config.can_delegate_to,
            )

        identity = AgentIdentity(
            id=role,
            name=config.name,
            role=role,
            description=config.description,
        )

        agent = Agent(
            provider=provider,
            tool_registry=scoped_registry,
            system_prompt=system_prompt,
            model=config.model,
            identity=identity,
        )

        # Subscribe agent to messages (logic for this will be in Orchestrator)

        self._agents[role] = agent
        return agent

    def get_identity(self, role: str) -> AgentIdentity:
        """Get the identity of a configured agent.

        Args:
            role: The role ID.

        Returns:
            AgentIdentity from configuration.
        """
        if role not in self.configs:
            raise ValueError(f"Agent role '{role}' is not configured.")

        config = self.configs[role]
        return AgentIdentity(
            id=role,
            name=config.name,
            role=role,
            description=config.description,
        )

    def list_agents(self) -> list[AgentIdentity]:
        """List all configured agents.

        Returns:
            List of AgentIdentities for all configured agents.
        """
        return [
            AgentIdentity(
                id=role,
                name=config.name,
                role=role,
                description=config.description,
            )
            for role, config in self.configs.items()
            if config.enabled
        ]

    def list_active_agents(self) -> list[AgentIdentity]:
        """List all currently instantiated agents.

        Returns:
            List of AgentIdentities for all active agents.
        """
        return [
            agent.identity for agent in self._agents.values() if agent.identity
        ]

    def reset_agent(self, role: str) -> None:
        """Reset an agent's history.

        Args:
            role: The role ID.
        """
        if role in self._agents:
            self._agents[role].clear_history()

    def reset_all(self) -> None:
        """Reset history for all agents in the pool."""
        for agent in self._agents.values():
            agent.clear_history()

    def shutdown(self) -> None:
        """Cleanup all agents and subscriptions."""
        # For now, just clear the agents dict.
        # If we add persistent subscriptions in get_agent, we'll need to unsubscribe them here.
        self._agents.clear()
