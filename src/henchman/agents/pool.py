"""AgentPool manages the lifecycle and instantiation of agents in a team."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import partial
from typing import TYPE_CHECKING

from henchman.agents.identity import AgentIdentity
from henchman.config.schema import ProviderSettings
from henchman.core.agent import Agent, validate_context_limit
from henchman.providers.anthropic import AnthropicProvider
from henchman.providers.factory import create_configured_provider
from henchman.tools.registry import ToolRegistry
from henchman.tools.scoped_registry import ScopedToolRegistry

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
        max_tokens: Explicit context budget, or None for model-derived limits.
        context_window: Hard requested capacity, separate from compaction budget.
        leader_system_prompt: Optional runtime override for the leader prompt.
    """

    environment_context: str | None = field(default=None)
    intelligent_context: bool = field(default=False)
    importance_threshold: float = field(default=0.5)
    cluster_similarity_threshold: float = field(default=0.7)
    adaptive_compression: bool = field(default=True)
    max_tokens: int | None = None
    context_window: int | None = None
    leader_system_prompt: str | None = None


# ---------------------------------------------------------------------------
# Scoped registry factory
# ---------------------------------------------------------------------------


def effective_scope_tools(parent: ToolRegistry, allowed_tools: list[str]) -> list[str]:
    """Include registered lifecycle tools needed by session goals and background jobs.

    Companion tools observe or stop existing work; they never grant new process
    launch capabilities. The resulting registry retains parent authorization,
    plan-mode rules, and explicit local exclusions.
    """
    companions = ["goal_status"]
    if any(name in allowed_tools and parent.get(name) is not None
           for name in ("shell", "python_exec")):
        companions.extend(["task_get", "task_list", "task_output", "task_stop"])
    return list(dict.fromkeys([
        *allowed_tools, *(name for name in companions if parent.get(name) is not None),
    ]))


def create_scoped_registry(
    parent: ToolRegistry,
    allowed_tools: list[str] | None,
    extra_tools: list["Tool"] | None = None,
    auto_approve: list[str] | None = None,
    *,
    inherit_auto_approve: bool = False,
) -> ToolRegistry:
    """Create a live registry of allowed parent tools and explicit local extras.

    Args:
        parent: The parent ToolRegistry to follow.
        allowed_tools: Names of tools to allow.
        extra_tools: Additional tools to register.
        auto_approve: Tool names to auto-approve.
        inherit_auto_approve: Follow current parent auto-approvals when true.

    Returns:
        A new ToolRegistry instance.
    """
    new_registry = ScopedToolRegistry(
        parent, effective_scope_tools(parent, allowed_tools) if allowed_tools is not None else None,
        inherit_auto_approve=inherit_auto_approve
    )

    if extra_tools:
        for tool in extra_tools:
            if new_registry.get(tool.name):
                new_registry.unregister(tool.name)
            new_registry.register(tool)

    if auto_approve:
        for name in auto_approve:
            new_registry.add_auto_approve_policy(name)

    return new_registry


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def effective_context_budget(max_tokens: int, compaction_threshold: float) -> int:
    """Convert configured context capacity and compaction threshold to a budget."""
    return max(1, int(max_tokens * compaction_threshold))


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


class ActiveAgentError(ValueError):
    """An execution attempted to reuse an agent already reserved or running."""


@dataclass
class _AgentClaim:
    agent: Agent
    owner: object
    running: bool


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
        provider_settings: ProviderSettings | None = None,
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
            provider_settings: Saved provider configuration for per-agent overrides.
        """
        self.configs = configs
        self.default_provider = default_provider
        self.provider_registry = provider_registry
        self.provider_settings = provider_settings or ProviderSettings()
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
        self._execution_claims: dict[int, _AgentClaim] = {}

    @contextmanager
    def claim_agent(
        self,
        agent: Agent,
        *,
        owner: object,
        running: bool = False,
    ) -> Iterator[None]:
        """Reserve an instance for one designated running loop at a time.

        Delegation reserves before resetting history and keeps the reservation
        through finalization. Its exact loop-parameter object owns the handoff;
        another loop or delegation cannot enter while either phase is active.
        """
        key = id(agent)
        existing = self._execution_claims.get(key)
        if existing is not None:
            if existing.owner is not owner or existing.running or not running:
                role = agent.identity.role if agent.identity else "unnamed"
                raise ActiveAgentError(f"Agent '{role}' is already active.")
            existing.running = True
            try:
                yield
            finally:
                existing.running = False
            return
        self._execution_claims[key] = _AgentClaim(agent, owner, running)
        try:
            yield
        finally:
            del self._execution_claims[key]

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
        if config.provider:
            return create_configured_provider(
                self.provider_settings,
                provider_name=config.provider,
                model=config.model,
                registry=self.provider_registry,
            )
        if not config.model:
            return self.default_provider
        return self._provider_with_model(self.default_provider, config.model)

    def _provider_with_model(
        self: "AgentPool",
        provider: "ModelProvider",
        model: str,
    ) -> "ModelProvider":
        """Construct an isolated model override using the live provider connection."""
        # A model-only override inherits the live provider, including runtime switches.
        provider_name = provider.name
        if provider_name == "openai-compatible":
            provider_name = "openai_compat"
        settings = self.provider_settings.model_copy(deep=True)
        configured = dict(getattr(settings, provider_name, {}))
        request_defaults = getattr(provider, "request_defaults", None)
        if isinstance(request_defaults, dict):
            configured.update(request_defaults)
        if isinstance(provider, AnthropicProvider):
            configured.update(
                max_tokens=provider.max_tokens,
                max_retries=provider.max_retries,
                tokens_per_minute=provider._rate_limiter.tokens_per_minute,
            )
        for field_name in ("api_key", "base_url"):
            if field_name == "api_key" and provider_name == "ollama":
                continue
            value = getattr(provider, field_name, None)
            if value is not None:
                configured[field_name] = value
        setattr(settings, provider_name, configured)
        return create_configured_provider(
            settings,
            provider_name=provider_name,
            model=model,
            registry=self.provider_registry,
        )

    def set_default_provider(self: "AgentPool", provider: "ModelProvider") -> None:
        """Switch inherited providers without replacing cached agents or histories."""
        replacements: list[tuple[Agent, ModelProvider]] = []
        for role, agent in self._agents.items():
            config = self.configs[role]
            if not config.provider:
                replacement = (
                    self._provider_with_model(provider, config.model) if config.model else provider
                )
                replacements.append((agent, replacement))
        self.default_provider = provider
        for agent, replacement in replacements:
            agent.set_provider(replacement)

    def set_context_limit(
        self,
        max_tokens: int,
        *,
        context_window: int | None = None,
    ) -> None:
        """Apply one context budget to all cached and subsequently created agents."""
        validate_context_limit(max_tokens)
        if context_window is not None:
            validate_context_limit(context_window)
            self.context_config.context_window = context_window
        self.context_config.max_tokens = max_tokens
        for agent in self._agents.values():
            agent.set_context_limit(max_tokens, context_window=context_window)

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
        if role == "tech_lead":
            from henchman.agents.orchestrator_prompts import PromptFactory

            return PromptFactory.create_tech_lead_prompt(
                self.configs,
                self.context_config.leader_system_prompt,
                self.context_config.environment_context,
            )
        if config.system_prompt is not None:
            return config.system_prompt

        team_members = [f"{c.name} ({c.role})" for c in self.configs.values() if c.enabled]
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
            allowed_tools=None if "*" in config.tools else config.tools,
            auto_approve=config.auto_approve,
            inherit_auto_approve=role == "tech_lead",
        )
        system_prompt = self._build_system_prompt(role, config)
        identity = _config_to_identity(role, config)
        ctx = self.context_config

        agent = Agent(
            provider=provider,
            tool_registry=scoped_registry,
            system_prompt=system_prompt,
            model=config.model,
            max_tokens=ctx.max_tokens if ctx.max_tokens is not None else 0,
            context_window=ctx.context_window,
            identity=identity,
            intelligent_context=ctx.intelligent_context,
            importance_threshold=ctx.importance_threshold,
            cluster_similarity_threshold=ctx.cluster_similarity_threshold,
            adaptive_compression=ctx.adaptive_compression,
        )

        self._agents[role] = agent
        scoped_registry.bind_team_tool_resolver(
            partial(self.find_team_tool_roles, requester_role=role),
        )
        return agent

    def find_team_tool_roles(self, name: str, *, requester_role: str) -> list[str] | None:
        """Inspect live scopes without creating agents, providers, or execution approvals."""
        requester = self._agents.get(requester_role)
        if requester is None or requester.tool_registry.get("delegate_task") is None:
            return None
        matches: list[str] = []
        for role, config in self.configs.items():
            candidate = self._agents.get(role)
            if not config.enabled or role == requester_role or candidate is requester:
                continue
            if candidate is not None:
                available = candidate.tool_registry.get(name) is not None
            else:
                available = (
                    ("*" in config.tools or name in effective_scope_tools(self.parent_tool_registry, config.tools))
                    and self.parent_tool_registry.get(name) is not None
                )
            if available:
                matches.append(role)
        return matches

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
