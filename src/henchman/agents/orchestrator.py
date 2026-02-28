"""Orchestrator for multi-agent development team.

This is the main entry point for the multi-agent system.  All supporting
types, components, and controllers live in sibling modules and are
re-exported here for backward compatibility.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from henchman.agents.delegation import DelegationRunner
from henchman.agents.ledger import TaskLedger
from henchman.agents.metrics import OrchestratorMetrics
from henchman.agents.metrics_reporter import MetricsReporter
from henchman.agents.pool import AgentPool
from henchman.agents.presets import get_default_team
from henchman.core.agent import Agent
from henchman.core.eventbus import EventBus
from henchman.core.events import AgentEvent, EventType
from henchman.tools.builtins.delegate import DelegateTaskTool

# Re-export symbols that external code imports from this module
from .orchestrator_components import (
    AgentValidator,
    OrchestratorComponent,
    ToolMetricsController,
)
from .orchestrator_execution import ExecutionController, _last_assistant_content
from .orchestrator_prompts import PromptFactory
from .orchestrator_timeout import TimeoutSummaryBuilder
from .orchestrator_tools import ToolController
from .orchestrator_turns import TurnEnforcementParams
from .orchestrator_types import (
    COLON_STALL_NUDGE,
    DELEGATE_TASK_TOOL,
    MAX_COLON_STALL_RETRIES,
    MAX_USER_INPUT_LENGTH,
    AgentLoopParams,
    CompletionStatus,
    DelegationExecutionParams,
    DelegationParams,
    LoopState,
    NoPendingToolsResult,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from henchman.config.schema import Settings
    from henchman.providers.base import ModelProvider
    from henchman.providers.registry import ProviderRegistry
    from henchman.tools.registry import ToolRegistry

# Backward-compat aliases used by tests
_COLON_STALL_NUDGE = COLON_STALL_NUDGE
_MAX_COLON_STALL_RETRIES = MAX_COLON_STALL_RETRIES
_DELEGATE_TASK_TOOL = DELEGATE_TASK_TOOL

__all__ = [
    "_COLON_STALL_NUDGE",
    "_DELEGATE_TASK_TOOL",
    "_MAX_COLON_STALL_RETRIES",
    "AgentLoopParams",
    "AgentValidator",
    "CompletionStatus",
    "DelegationExecutionParams",
    "DelegationParams",
    "ExecutionController",
    "LoopState",
    "NoPendingToolsResult",
    "Orchestrator",
    "OrchestratorComponent",
    "OrchestratorMetrics",
    "PromptFactory",
    "TimeoutSummaryBuilder",
    "ToolController",
    "ToolMetricsController",
    "TurnEnforcementParams",
]


@dataclass
class OrchestratorConfig:
    """Optional configuration for :class:`Orchestrator` initialization."""

    provider_registry: ProviderRegistry | None = None
    tool_registry: ToolRegistry | None = None
    event_bus: EventBus | None = None
    settings: Settings | None = None
    system_prompt: str | None = None
    environment_context: str | None = None


class Orchestrator:
    """Orchestrates a team of agents to solve complex tasks."""

    def __init__(
        self: Orchestrator,
        default_provider: ModelProvider,
        config: OrchestratorConfig | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Orchestrator.

        Args:
            default_provider: The default model provider.
            config: Optional grouped configuration.
            **kwargs: Legacy keyword arguments (forwarded to OrchestratorConfig).
        """
        if config is None:
            config = OrchestratorConfig(**kwargs)
        self._init_core(default_provider, config)
        self._init_agents(default_provider, config)

    def _init_core(
        self: Orchestrator,
        default_provider: ModelProvider,
        config: OrchestratorConfig,
    ) -> None:
        """Initialize core attributes, metrics, and controllers."""
        from henchman.config.schema import Settings  # noqa: PLC0415
        from henchman.tools.registry import ToolRegistry  # noqa: PLC0415

        self.default_provider = default_provider
        self.provider_registry = config.provider_registry
        self.tool_registry = config.tool_registry or ToolRegistry()
        self.event_bus = config.event_bus or EventBus()
        self.settings: Settings = config.settings or Settings()
        self.environment_context = config.environment_context
        self.metrics = OrchestratorMetrics()
        self._reporter = MetricsReporter(self.metrics)
        self._last_loop_tool_call_count: int = 0
        self.last_completion_status: CompletionStatus = CompletionStatus.COMPLETED
        self.validator = AgentValidator(self)
        self.tool_controller = ToolController(self)
        self.execution_controller = ExecutionController(self)

    def _init_agents(
        self: Orchestrator,
        default_provider: ModelProvider,
        config: OrchestratorConfig,
    ) -> None:
        """Initialize agent pool, tech lead, and delegation runner."""
        agent_configs = self._load_agent_configs()
        ctx = self.settings.context
        self.pool = AgentPool(
            configs=agent_configs,
            default_provider=default_provider,
            provider_registry=config.provider_registry,
            parent_tool_registry=self.tool_registry,
            event_bus=self.event_bus,
            environment_context=config.environment_context,
            intelligent_context=ctx.intelligent_context,
            importance_threshold=ctx.importance_threshold,
            cluster_similarity_threshold=ctx.cluster_similarity_threshold,
            adaptive_compression=ctx.adaptive_compression,
        )
        self.shared_context: list[dict[str, Any]] = []
        self.ledger: TaskLedger | None = None
        self._setup_tech_lead(agent_configs, default_provider, config)
        self.delegation_runner = DelegationRunner(
            pool=self.pool,
            settings=self.settings,
            shared_context=self.shared_context,
            metrics=self.metrics,
            run_agent_loop=self.execution_controller.run_agent_loop,
            assess_completion=self.execution_controller.assess_completion,
        )

    def _load_agent_configs(self: Orchestrator) -> dict[str, Any]:
        """Load and merge agent configurations."""
        agent_configs = get_default_team()
        if self.settings.agents.agents:
            for role, cfg in self.settings.agents.agents.items():
                agent_configs[role] = cfg
        return agent_configs

    def _setup_tech_lead(
        self: Orchestrator,
        agent_configs: dict[str, Any],
        default_provider: ModelProvider,
        config: OrchestratorConfig,
    ) -> None:
        """Set up the Tech Lead agent."""
        if not self.tool_registry.get("delegate_task"):
            self.tool_registry.register(DelegateTaskTool())
        tl_prompt = PromptFactory.create_tech_lead_prompt(
            agent_configs, config.system_prompt, config.environment_context,
        )
        ctx = self.settings.context
        self.tech_lead = Agent(
            provider=default_provider,
            tool_registry=self.tool_registry,
            system_prompt=tl_prompt,
            identity=_create_tech_lead_identity(),
            intelligent_context=ctx.intelligent_context,
            importance_threshold=ctx.importance_threshold,
            cluster_similarity_threshold=ctx.cluster_similarity_threshold,
            adaptive_compression=ctx.adaptive_compression,
        )
        self.tech_lead.stall_detection_enabled = False

    # ------------------------------------------------------------------
    # Public run methods
    # ------------------------------------------------------------------

    async def run(
        self: Orchestrator,
        user_input: str,
    ) -> AsyncIterator[AgentEvent]:
        """Run the orchestrator with user input."""
        self._prepare_run(user_input)
        yield AgentEvent(
            type=EventType.AGENT_STARTED,
            data={"agent": "tech_lead"},
            source_agent="orchestrator",
        )
        async for event in self.execution_controller.run_agent_loop(
            AgentLoopParams(agent=self.tech_lead, input_text=user_input),
        ):
            yield event
        for event in self._finalize_run(self.tech_lead, "tech_lead"):
            yield event

    async def run_direct(
        self: Orchestrator,
        role: str,
        user_input: str,
    ) -> AsyncIterator[AgentEvent]:
        """Run a specific agent directly, bypassing the Tech Lead."""
        agent = self.pool.get_agent(role)
        yield AgentEvent(
            type=EventType.AGENT_STARTED,
            data={"agent": role},
            source_agent="orchestrator",
        )
        async for event in self.execution_controller.run_agent_loop(
            AgentLoopParams(agent=agent, input_text=user_input),
        ):
            yield event
        for event in self._finalize_run(agent, role):
            yield event

    def _prepare_run(self: Orchestrator, user_input: str) -> None:
        """Initialize state for a new run."""
        self.ledger = TaskLedger(goal=user_input[:MAX_USER_INPUT_LENGTH])
        self.delegation_runner.ledger = self.ledger
        self.metrics.reset_for_run()
        self.metrics.performance.task_start_time = time.time()

    def _finalize_run(
        self: Orchestrator,
        agent: Agent,
        role_label: str,
    ) -> list[AgentEvent]:
        """Calculate metrics and produce final events."""
        self.metrics.performance.task_end_time = time.time()
        self.metrics.calculate_final_metrics()
        status = self.execution_controller.assess_completion(agent)
        self.last_completion_status = status
        events: list[AgentEvent] = []
        if status == CompletionStatus.NO_WORK_DONE:
            events.append(AgentEvent(
                type=EventType.ERROR,
                data="Agent completed without performing any actions.",
                source_agent="orchestrator",
            ))
        events.append(AgentEvent(
            type=EventType.AGENT_COMPLETED,
            data={"agent": role_label, "status": status.value},
            source_agent="orchestrator",
        ))
        return events

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def get_metrics_report(self: Orchestrator) -> str:
        """Generate a formatted performance metrics dashboard."""
        return self._reporter.get_metrics_report()

    def get_pool(self: Orchestrator) -> AgentPool:
        """Get the agent pool."""
        return self.pool

    def get_event_bus(self: Orchestrator) -> EventBus:
        """Get the event bus."""
        return self.event_bus

    # ------------------------------------------------------------------
    # Backward-compat delegates
    # ------------------------------------------------------------------

    @property
    def _delegation_runner(self: Orchestrator) -> DelegationRunner:
        """Backward-compat alias for :attr:`delegation_runner`."""
        return self.delegation_runner

    def _assess_completion(self: Orchestrator, agent: Agent) -> CompletionStatus:
        """Backward-compat delegate to execution controller."""
        return self.execution_controller.assess_completion(agent)

    @staticmethod
    def _assemble_delegation_input(
        task: str,
        brief: dict[str, Any] | None,
        mission: str | None = None,
    ) -> str:
        """Backward-compat delegate to DelegationRunner."""
        return DelegationRunner._assemble_delegation_input(  # noqa: SLF001
            task, brief, mission,
        )

    @staticmethod
    def _parse_completion_report(summary: str) -> dict[str, str]:
        """Backward-compat delegate to DelegationRunner."""
        return DelegationRunner._parse_completion_report(summary)  # noqa: SLF001

    @staticmethod
    def _last_assistant_content(agent: Agent) -> str:
        """Return the last assistant message content."""
        return _last_assistant_content(agent)


def _create_tech_lead_identity() -> Any:
    """Create the Tech Lead agent identity."""
    from henchman.agents.identity import AgentIdentity  # noqa: PLC0415

    return AgentIdentity(
        id="tech_lead",
        name="Leader",
        role="tech_lead",
        description="Architect, implementer, and quality gate",
    )
