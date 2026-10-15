"""Initialization logic for the Orchestrator.

Contains OrchestratorConfig, setup helpers, and factory functions
used during Orchestrator construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from henchman.agents.delegation import DelegationRunner
from henchman.agents.metrics import OrchestratorMetrics
from henchman.agents.metrics_reporter import MetricsReporter
from henchman.agents.pool import AgentPool, ContextConfig, effective_context_budget
from henchman.agents.presets import get_default_team
from henchman.core.eventbus import EventBus

from .orchestrator_components import AgentValidator
from .orchestrator_execution import ExecutionController
from .orchestrator_tech_lead import setup_tech_lead
from .orchestrator_tools import ToolController
from .orchestrator_types import CompletionStatus

if TYPE_CHECKING:
    from henchman.config.schema import Settings
    from henchman.providers.base import ModelProvider
    from henchman.providers.registry import ProviderRegistry
    from henchman.tools.registry import ToolRegistry


# ---------------------------------------------------------------------------
# Configuration dataclass
# ---------------------------------------------------------------------------


@dataclass
class OrchestratorConfig:
    """Optional configuration for :class:`Orchestrator` initialization."""

    provider_registry: ProviderRegistry | None = None
    tool_registry: ToolRegistry | None = None
    event_bus: EventBus | None = None
    settings: Settings | None = None
    system_prompt: str | None = None
    environment_context: str | None = None


# ---------------------------------------------------------------------------
# Orchestrator initialization
# ---------------------------------------------------------------------------


def init_orchestrator(
    orch: Any,
    default_provider: ModelProvider,
    config: OrchestratorConfig | None,
    **kwargs: Any,
) -> None:
    """Fully initialize an Orchestrator instance.

    Args:
        orch: The orchestrator instance to initialize.
        default_provider: The default model provider.
        config: Optional grouped configuration.
        **kwargs: Legacy keyword arguments (forwarded to OrchestratorConfig).

    Returns:
        None
    """
    if config is None:
        config = OrchestratorConfig(**kwargs)
    _init_core(orch, default_provider, config)
    _init_agents(orch, default_provider, config)


# ---------------------------------------------------------------------------
# Internal setup helpers
# ---------------------------------------------------------------------------


def _init_core(
    orch: Any,
    default_provider: ModelProvider,
    config: OrchestratorConfig,
) -> None:
    """Initialize core attributes, metrics, and controllers."""
    from henchman.config.schema import Settings
    from henchman.tools.registry import ToolRegistry

    orch.default_provider = default_provider
    orch.provider_registry = config.provider_registry
    orch.tool_registry = config.tool_registry if config.tool_registry is not None else ToolRegistry()
    orch.event_bus = config.event_bus or EventBus()
    orch.settings = config.settings or Settings()
    orch.environment_context = config.environment_context
    orch.metrics = OrchestratorMetrics()
    orch._reporter = MetricsReporter(orch.metrics)
    orch._last_loop_tool_call_count = 0
    orch._last_loop_success_count = 0
    orch._last_loop_timed_out = False
    orch.last_completion_status = CompletionStatus.COMPLETED
    orch.validator = AgentValidator(orch)
    orch.tool_controller = ToolController(orch)
    orch.execution_controller = ExecutionController(orch)


def _init_agents(
    orch: Any,
    default_provider: ModelProvider,
    config: OrchestratorConfig,
) -> None:
    """Initialize agent pool, tech lead, and delegation runner."""
    agent_configs = get_default_team()
    if orch.settings.agents.agents:
        for role, cfg in orch.settings.agents.agents.items():
            agent_configs[role] = cfg
    _create_pool(orch, agent_configs, default_provider, config)
    orch.shared_context = []
    orch.ledger = None
    setup_tech_lead(
        orch,
        agent_configs,
        default_provider,
        system_prompt=config.system_prompt,
        environment_context=config.environment_context,
    )
    orch.delegation_runner = DelegationRunner(
        pool=orch.pool,
        settings=orch.settings,
        shared_context=orch.shared_context,
        metrics=orch.metrics,
        run_agent_loop=orch.execution_controller.run_agent_loop,
        assess_completion=orch.execution_controller.assess_completion,
    )
    from henchman.agents.subagent_runtime import initialize_subagents

    initialize_subagents(orch)


def _create_pool(
    orch: Any,
    agent_configs: dict[str, Any],
    default_provider: ModelProvider,
    config: OrchestratorConfig,
) -> None:
    """Create the agent pool."""
    ctx = orch.settings.context
    orch.pool = AgentPool(
        configs=agent_configs,
        default_provider=default_provider,
        provider_registry=config.provider_registry,
        provider_settings=orch.settings.providers,
        parent_tool_registry=orch.tool_registry,
        event_bus=orch.event_bus,
        context_config=ContextConfig(
            environment_context=config.environment_context,
            intelligent_context=ctx.intelligent_context,
            importance_threshold=ctx.importance_threshold,
            cluster_similarity_threshold=ctx.cluster_similarity_threshold,
            adaptive_compression=ctx.adaptive_compression,
            max_tokens=effective_context_budget(ctx.max_tokens, ctx.compaction_threshold),
            context_window=ctx.max_tokens,
        ),
    )
