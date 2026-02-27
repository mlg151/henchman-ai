"""Orchestrator for multi-agent development team."""

import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from henchman.agents.ledger import TaskLedger
from henchman.agents.pool import AgentPool
from henchman.agents.presets import get_default_team
from henchman.config.schema import Settings
from henchman.core.agent import Agent
from henchman.core.eventbus import EventBus
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import Message, ModelProvider, ToolCall
from henchman.providers.registry import ProviderRegistry
from henchman.tools.builtins.delegate import DelegateTaskTool
from henchman.tools.registry import ToolRegistry


@dataclass
class AgentLoopParams:
    """Parameters for running an agent loop.

    Encapsulates the common parameters used across different agent execution methods
    to address Primitive Obsession code smell.
    """
    agent: Agent | None = None
    """The agent to run. Either agent or target_role must be provided."""

    target_role: str | None = None
    """The role of the agent to run. Either agent or target_role must be provided."""

    input_text: str = ""
    """The input text, task, or user input for the agent to process."""

    depth: int = 0
    """Current delegation depth for tracking recursion."""

    max_turns: int = 0
    """Maximum number of turns allowed (0 for unlimited)."""

    msg_start_index: int = 0
    """Starting index in agent messages for tracking output."""

    brief: dict[str, Any] | None = None
    """Optional briefing information for delegation tasks."""


@dataclass
class DelegationParams:
    """Parameters for delegating a task to a specialist agent.

    Encapsulates the parameters used for delegation to address Primitive Obsession code smell.
    """
    target_role: str
    """The role of the agent to delegate to."""

    task: str
    """The task description to delegate."""

    brief: dict[str, Any] | None = None
    """Optional briefing information for the delegation."""

    depth: int = 0
    """Current delegation depth for tracking recursion."""


# Configuration constants for magic numbers
PERCENTAGE_MULTIPLIER = 100.0
"""Multiplier for converting ratios to percentages."""

SECONDS_PER_MINUTE = 60.0
"""Number of seconds in a minute."""

MAX_USER_INPUT_LENGTH = 500
"""Maximum length for user input truncation."""

MAX_ERROR_MESSAGE_LENGTH = 200
"""Maximum length for error message truncation."""

MAX_SUMMARY_LENGTH = 200
"""Maximum length for summary text truncation."""

MAX_CONTENT_LENGTH = 800
"""Maximum length for content truncation."""

RECENT_CONTEXT_ENTRIES = 5
"""Number of recent shared context entries to show."""

MAX_STALL_NUDGES = 10
"""Maximum number of stall nudges before marking as stalled."""

RECENT_ERRORS_TO_SHOW = 10
"""Number of recent tool errors to show in summaries."""

RECENT_TOOLS_TO_SHOW = 10
"""Number of recent tool calls to show in timeout summaries."""

MAX_TOOL_CALL_DISPLAY_LENGTH = 120
"""Maximum length for displaying tool call names in summaries."""

MAX_NARRATION_DISPLAY_LENGTH = 300
"""Maximum length for displaying narration in timeout summaries."""

MAX_TOOL_ARGUMENTS_TO_DISPLAY = 2
"""Maximum number of tool arguments to show in summaries."""

MAX_TOOL_USAGE_TO_DISPLAY = 5
"""Maximum number of tool usage entries to show in metrics."""


class CompletionStatus(Enum):
    """Status of an agent's work upon completion.

    Used in ``AGENT_COMPLETED`` event data to distinguish genuine
    completion from cases where the agent ended without doing work.
    """

    COMPLETED = "completed"
    """Agent performed meaningful tool calls and finished normally."""

    NO_WORK_DONE = "no_work_done"
    """Agent stopped without making any tool calls."""

    STALLED = "stalled"
    """Agent announced intent repeatedly but never acted."""

    TIMED_OUT = "timed_out"
    """Agent hit the turn limit before finishing."""


class ToolCategory(Enum):
    """Categories for tool classification in metrics tracking."""
    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    EDIT_FILE = "edit_file"
    SHELL = "shell"
    GIT_OPS = "git_ops"
    OTHER = "other"


# Mapping from tool names to their categories
_TOOL_CATEGORY_MAP: dict[str, ToolCategory] = {
    "read_file": ToolCategory.READ_FILE,
    "write_file": ToolCategory.WRITE_FILE,
    "edit_file": ToolCategory.EDIT_FILE,
    "shell": ToolCategory.SHELL,
    "git_ops": ToolCategory.GIT_OPS,
}


def _categorize_tool(tool_name: str) -> ToolCategory:
    """Categorize a tool by its name.

    Args:
        tool_name: Name of the tool to categorize.

    Returns:
        The tool's category, or ToolCategory.OTHER if not found.
    """
    return _TOOL_CATEGORY_MAP.get(tool_name, ToolCategory.OTHER)


class PerformanceMetrics:
    """Encapsulates performance-related metrics."""

    # Target constants
    DELEGATION_RATE_TARGET = 40.0  # Target > 40% (from current 25%)
    ERROR_RATE_TARGET = 50.0  # Target reduction of 50%
    CONTEXT_WINDOW_TARGET = 40.0  # Target < 40% (from 65%)
    FILE_RE_READS_TARGET = 1.3  # Target < 1.3 (60% reduction from 3.2)
    FILE_RE_READS_BASELINE = 3.2  # Baseline from which we're reducing by 60%

    def __init__(self) -> None:
        """Initialize performance metrics with default values."""
        self.task_start_time: float = 0.0
        self.task_end_time: float = 0.0
        self.task_duration_minutes: float = 0.0
        self.files_accessed: dict[str, int] = {}
        self.tool_usage_by_type: dict[str, int] = {}
        self.delegation_rate: float = 0.0
        self.file_re_reads: int = 0
        self.error_rate: float = 0.0
        self.context_window_usage: float = 0.0

    def reset(self) -> None:
        """Reset performance metrics for a new run."""
        self.task_start_time = 0.0
        self.task_end_time = 0.0
        self.task_duration_minutes = 0.0
        self.files_accessed.clear()
        self.tool_usage_by_type.clear()
        self.delegation_rate = 0.0
        self.file_re_reads = 0
        self.error_rate = 0.0
        self.context_window_usage = 0.0

    def calculate_file_re_reads(self) -> None:
        """Calculate file re-reads from access patterns."""
        if self.files_accessed:
            total_accesses = sum(self.files_accessed.values())
            unique_files = len(self.files_accessed)
            if unique_files > 0:
                self.file_re_reads = total_accesses - unique_files

    def track_file_access(self, file_path: str) -> None:
        """Track a file access for re-read analysis."""
        self.files_accessed[file_path] = self.files_accessed.get(file_path, 0) + 1

    def track_tool_usage(self, tool_name: str) -> None:
        """Track tool usage by type."""
        self.tool_usage_by_type[tool_name] = self.tool_usage_by_type.get(tool_name, 0) + 1


class QualityMetrics:
    """Encapsulates quality-related metrics."""

    def __init__(self) -> None:
        """Initialize quality metrics with default values."""
        self.test_results: dict[str, Any] = {"passing": 0, "total": 0, "percentage": 0.0}
        self.code_coverage: float = 0.0
        self.linting_status: dict[str, int] = {"errors": 0, "warnings": 0}
        self.documentation_coverage: float = 0.0

    def reset(self) -> None:
        """Reset quality metrics for a new run."""
        self.test_results = {"passing": 0, "total": 0, "percentage": 0.0}
        self.code_coverage = 0.0
        self.linting_status = {"errors": 0, "warnings": 0}
        self.documentation_coverage = 0.0

    def calculate_test_percentage(self) -> None:
        """Calculate test results percentage."""
        if self.test_results["total"] > 0:
            self.test_results["percentage"] = (
                self.test_results["passing"] / self.test_results["total"] * PERCENTAGE_MULTIPLIER
            )


class ToolMetrics:
    """Encapsulates tool usage metrics."""

    def __init__(self) -> None:
        """Initialize tool metrics with default values."""
        self.total_tool_calls: int = 0
        self.successful_tool_calls: int = 0
        self.failed_tool_calls: int = 0
        self.read_file_calls: int = 0
        self.write_file_calls: int = 0
        self.edit_file_calls: int = 0
        self.shell_calls: int = 0
        self.git_ops_calls: int = 0
        self.other_tool_calls: int = 0

    def reset(self) -> None:
        """Reset tool metrics for a new run."""
        self.total_tool_calls = 0
        self.successful_tool_calls = 0
        self.failed_tool_calls = 0
        self.read_file_calls = 0
        self.write_file_calls = 0
        self.edit_file_calls = 0
        self.shell_calls = 0
        self.git_ops_calls = 0
        self.other_tool_calls = 0

    def track_tool_call(self, tool_name: str, success: bool) -> None:
        """Track a tool call with its category."""
        self.total_tool_calls += 1

        if success:
            self.successful_tool_calls += 1
        else:
            self.failed_tool_calls += 1

        # Categorize tool calls using the shared categorization function
        category = _categorize_tool(tool_name)
        if category == ToolCategory.READ_FILE:
            self.read_file_calls += 1
        elif category == ToolCategory.WRITE_FILE:
            self.write_file_calls += 1
        elif category == ToolCategory.EDIT_FILE:
            self.edit_file_calls += 1
        elif category == ToolCategory.SHELL:
            self.shell_calls += 1
        elif category == ToolCategory.GIT_OPS:
            self.git_ops_calls += 1
        else:
            self.other_tool_calls += 1

    def calculate_error_rate(self) -> float:
        """Calculate error rate percentage."""
        if self.total_tool_calls > 0:
            return (self.failed_tool_calls / self.total_tool_calls) * PERCENTAGE_MULTIPLIER
        return 0.0

    def get_tool_call_counts_by_category(self) -> dict[ToolCategory, int]:
        """Get tool call counts organized by category.

        Returns:
            A dictionary mapping tool categories to their call counts.
        """
        return {
            ToolCategory.READ_FILE: self.read_file_calls,
            ToolCategory.WRITE_FILE: self.write_file_calls,
            ToolCategory.EDIT_FILE: self.edit_file_calls,
            ToolCategory.SHELL: self.shell_calls,
            ToolCategory.GIT_OPS: self.git_ops_calls,
            ToolCategory.OTHER: self.other_tool_calls,
        }


class OrchestratorMetrics:
    """Encapsulates metrics collection and calculation for the orchestrator.

    This class addresses the Primitive Obsession code smell by providing
    a proper object-oriented interface for metrics management instead of
    using a complex nested dictionary directly.
    """

    def __init__(self) -> None:
        """Initialize all metrics with default values."""
        # Core metrics
        self.thinking_pattern_usage: int = 0
        self.delegation_count: int = 0
        self.delegation_by_type: dict[str, int] = {"planner": 0, "explorer": 0, "engineer": 0}
        self.thinking_quality_score: int = 0

        # Component metrics
        self.performance = PerformanceMetrics()
        self.quality = QualityMetrics()
        self.tools = ToolMetrics()

    def reset_for_run(self) -> None:
        """Reset all metrics for a new run while preserving structure."""
        self.thinking_pattern_usage = 0
        self.delegation_count = 0
        self.delegation_by_type = {"planner": 0, "explorer": 0, "engineer": 0}
        self.thinking_quality_score = 0

        self.performance.reset()
        self.quality.reset()
        self.tools.reset()

    def calculate_final_metrics(self) -> None:
        """Calculate derived metrics after task completion."""
        # Calculate task duration
        if self.performance.task_start_time and self.performance.task_end_time:
            duration = self.performance.task_end_time - self.performance.task_start_time
            # Store duration in minutes for readability
            self.performance.task_duration_minutes = duration / SECONDS_PER_MINUTE

        # Calculate delegation rate
        total_tasks = self.tools.total_tool_calls + self.delegation_count
        if total_tasks > 0:
            self.performance.delegation_rate = self.delegation_count / total_tasks * PERCENTAGE_MULTIPLIER

        # Calculate error rate
        self.performance.error_rate = self.tools.calculate_error_rate()

        # Calculate test results percentage
        self.quality.calculate_test_percentage()

        # Calculate file re-reads
        self.performance.calculate_file_re_reads()

    def update_tool_metrics(self, tool_name: str, arguments: dict[str, Any], success: bool) -> None:
        """Update metrics for a tool call.

        Args:
            tool_name: Name of the tool called.
            arguments: Arguments passed to the tool.
            success: Whether the tool call succeeded.
        """
        # Update tool metrics
        self.tools.track_tool_call(tool_name, success)

        # Update performance metrics
        self.performance.track_tool_usage(tool_name)

        # Track file access for re-read analysis
        if tool_name == "read_file" and "path" in arguments:
            file_path = str(arguments["path"])
            self.performance.track_file_access(file_path)

    def __getitem__(self, key: str) -> Any:
        """Support dictionary-like access for backward compatibility.

        Args:
            key: The metric name to retrieve.

        Returns:
            The metric value.

        Raises:
            KeyError: If the key is not a valid metric.
        """
        # Check main class attributes
        if hasattr(self, key):
            return getattr(self, key)

        # Check component classes
        component_mapping = {
            # Performance metrics
            "task_start_time": self.performance.task_start_time,
            "task_end_time": self.performance.task_end_time,
            "task_duration_minutes": self.performance.task_duration_minutes,
            "files_accessed": self.performance.files_accessed,
            "tool_usage_by_type": self.performance.tool_usage_by_type,
            "delegation_rate": self.performance.delegation_rate,
            "file_re_reads": self.performance.file_re_reads,
            "error_rate": self.performance.error_rate,
            "context_window_usage": self.performance.context_window_usage,

            # Quality metrics
            "test_results": self.quality.test_results,
            "code_coverage": self.quality.code_coverage,
            "linting_status": self.quality.linting_status,
            "documentation_coverage": self.quality.documentation_coverage,

            # Tool metrics
            "total_tool_calls": self.tools.total_tool_calls,
            "successful_tool_calls": self.tools.successful_tool_calls,
            "failed_tool_calls": self.tools.failed_tool_calls,
            "read_file_calls": self.tools.read_file_calls,
            "write_file_calls": self.tools.write_file_calls,
            "edit_file_calls": self.tools.edit_file_calls,
            "shell_calls": self.tools.shell_calls,
            "git_ops_calls": self.tools.git_ops_calls,
            "other_tool_calls": self.tools.other_tool_calls,
        }

        if key in component_mapping:
            return component_mapping[key]

        raise KeyError(f"'{key}' is not a valid metric")

    def __contains__(self, key: str) -> bool:
        """Support 'in' operator for backward compatibility.

        Args:
            key: The metric name to check.

        Returns:
            True if the metric exists, False otherwise.
        """
        # Check main class attributes
        if hasattr(self, key):
            return True

        # Check component class mappings
        component_keys = {
            "task_start_time", "task_end_time", "task_duration_minutes",
            "files_accessed", "tool_usage_by_type", "delegation_rate",
            "file_re_reads", "error_rate", "context_window_usage",
            "test_results", "code_coverage", "linting_status", "documentation_coverage",
            "total_tool_calls", "successful_tool_calls", "failed_tool_calls",
            "read_file_calls", "write_file_calls", "edit_file_calls",
            "shell_calls", "git_ops_calls", "other_tool_calls",
        }

        return key in component_keys

    def get(self, key: str, default: Any = None) -> Any:
        """Support dictionary-like get method for backward compatibility.

        Args:
            key: The metric name to retrieve.
            default: Default value if key doesn't exist.

        Returns:
            The metric value or default.
        """
        try:
            return self[key]
        except KeyError:
            return default

    def __setitem__(self, key: str, value: Any) -> None:
        """Support dictionary-like assignment for backward compatibility.

        Args:
            key: The metric name to set.
            value: The value to assign.

        Raises:
            KeyError: If the key is not a valid metric.
        """
        # Check main class attributes
        if hasattr(self, key):
            setattr(self, key, value)
            return

        # Check component class attributes that can be set
        component_setters = {
            "task_start_time": lambda v: setattr(self.performance, "task_start_time", v),
            "task_end_time": lambda v: setattr(self.performance, "task_end_time", v),
            "task_duration_minutes": lambda v: setattr(self.performance, "task_duration_minutes", v),
            "files_accessed": lambda v: setattr(self.performance, "files_accessed", v),
            "tool_usage_by_type": lambda v: setattr(self.performance, "tool_usage_by_type", v),
            "delegation_rate": lambda v: setattr(self.performance, "delegation_rate", v),
            "file_re_reads": lambda v: setattr(self.performance, "file_re_reads", v),
            "error_rate": lambda v: setattr(self.performance, "error_rate", v),
            "context_window_usage": lambda v: setattr(self.performance, "context_window_usage", v),
            "test_results": lambda v: setattr(self.quality, "test_results", v),
            "code_coverage": lambda v: setattr(self.quality, "code_coverage", v),
            "linting_status": lambda v: setattr(self.quality, "linting_status", v),
            "documentation_coverage": lambda v: setattr(self.quality, "documentation_coverage", v),
            "total_tool_calls": lambda v: setattr(self.tools, "total_tool_calls", v),
            "successful_tool_calls": lambda v: setattr(self.tools, "successful_tool_calls", v),
            "failed_tool_calls": lambda v: setattr(self.tools, "failed_tool_calls", v),
            "read_file_calls": lambda v: setattr(self.tools, "read_file_calls", v),
            "write_file_calls": lambda v: setattr(self.tools, "write_file_calls", v),
            "edit_file_calls": lambda v: setattr(self.tools, "edit_file_calls", v),
            "shell_calls": lambda v: setattr(self.tools, "shell_calls", v),
            "git_ops_calls": lambda v: setattr(self.tools, "git_ops_calls", v),
            "other_tool_calls": lambda v: setattr(self.tools, "other_tool_calls", v),
        }

        if key in component_setters:
            component_setters[key](value)  # type: ignore[no-untyped-call]
        else:
            raise KeyError(f"'{key}' is not a valid metric")


# Configuration constants for orchestrator behavior
_ROLE_ANCHOR_INTERVAL = 8  # Interval (in tool calls) for role anchoring reminders
_WRAPUP_WARNING_OFFSET = 3  # Turns before limit to inject wrap-up warning
_MIN_THINKING_LINES = 3  # Minimum numbered lines for quality thinking pattern
_THINKING_QUALITY_INCREMENT = 5  # Points added for quality thinking pattern
_MAX_THINKING_SCORE = 100  # Maximum thinking quality score
_TOOL_ERROR_MAX_LENGTH = 200  # Max length for tool error messages in summaries
_RESULT_PREVIEW_LENGTH = 500  # Length of tool result preview in events
_MAX_COLON_STALL_RETRIES = 3  # Max retries for colon-ending stall nudge
_COLON_STALL_MIN_LENGTH = 20  # Minimum response length for colon-stall check

# Colon-stall nudge message — sent when an agent ends its response with ":"
_COLON_STALL_NUDGE = (
    "STOP. You ended your response with a colon — you announced what you "
    "were about to do but then stopped without doing it. Do NOT narrate or "
    "describe your plan. Actually perform the work NOW by calling the "
    "appropriate tool. If you cannot act, explain why."
)

# Tool name constants
_DELEGATE_TASK_TOOL = "delegate_task"


class Orchestrator:
    """Orchestrates a team of agents to solve complex tasks."""

    def __init__(
        self,
        default_provider: ModelProvider,
        provider_registry: ProviderRegistry | None = None,
        tool_registry: ToolRegistry | None = None,
        event_bus: EventBus | None = None,
        settings: Settings | None = None,
        system_prompt: str | None = None,
        environment_context: str | None = None,
    ) -> None:
        """Initialize the Orchestrator.

        Args:
            default_provider: The default model provider.
            provider_registry: Registry for provider overrides.
            tool_registry: Registry containing all available tools.
            event_bus: Optional existing event bus.
            settings: Optional application settings.
            system_prompt: Optional override for Tech Lead system prompt.
            environment_context: Pre-formatted environment block for agents.
        """
        self._initialize_basic_attributes(
            default_provider, provider_registry, tool_registry, event_bus, settings, environment_context
        )
        self._initialize_metrics_and_state()
        agent_configs = self._load_agent_configs()
        self._create_agent_pool(agent_configs, default_provider, provider_registry, environment_context)
        self._initialize_shared_context_and_ledger()
        self._setup_tech_lead_agent(agent_configs, default_provider, system_prompt, environment_context)

    def _initialize_basic_attributes(
        self,
        default_provider: ModelProvider,
        provider_registry: ProviderRegistry | None,
        tool_registry: ToolRegistry | None,
        event_bus: EventBus | None,
        settings: Settings | None,
        environment_context: str | None,
    ) -> None:
        """Initialize basic orchestrator attributes.

        Args:
            default_provider: The default model provider.
            provider_registry: Registry for provider overrides.
            tool_registry: Registry containing all available tools.
            event_bus: Optional existing event bus.
            settings: Optional application settings.
            environment_context: Pre-formatted environment block for agents.
        """
        self.default_provider = default_provider
        self.provider_registry = provider_registry
        self.tool_registry = tool_registry or ToolRegistry()
        self.event_bus = event_bus or EventBus()
        self.settings = settings or Settings()
        self.environment_context = environment_context

    def _initialize_metrics_and_state(self) -> None:
        """Initialize metrics and internal state tracking."""
        # Thinking and delegation metrics - using encapsulated class instead of primitive dict
        self.metrics = OrchestratorMetrics()

        # Track the tool call count from the last agent loop run
        self._last_loop_tool_call_count: int = 0

        # The completion status of the most recent run()/run_direct() call
        self.last_completion_status: CompletionStatus = CompletionStatus.COMPLETED

    def _load_agent_configs(self) -> dict[str, Any]:
        """Load and merge agent configurations.

        Returns:
            Dictionary of agent configurations with custom overrides applied.
        """
        agent_configs = get_default_team()
        if self.settings.agents.agents:
            # Merge custom configs/overrides
            for role, config in self.settings.agents.agents.items():
                agent_configs[role] = config
        return agent_configs

    def _create_agent_pool(
        self,
        agent_configs: dict[str, Any],
        default_provider: ModelProvider,
        provider_registry: ProviderRegistry | None,
        environment_context: str | None,
    ) -> None:
        """Create the agent pool with loaded configurations.

        Args:
            agent_configs: Dictionary of agent configurations.
            default_provider: The default model provider.
            provider_registry: Registry for provider overrides.
            environment_context: Pre-formatted environment block for agents.
        """
        self.pool = AgentPool(
            configs=agent_configs,
            default_provider=default_provider,
            provider_registry=provider_registry,
            parent_tool_registry=self.tool_registry,
            event_bus=self.event_bus,
            environment_context=environment_context,
            intelligent_context=self.settings.context.intelligent_context,
            importance_threshold=self.settings.context.importance_threshold,
            cluster_similarity_threshold=self.settings.context.cluster_similarity_threshold,
            adaptive_compression=self.settings.context.adaptive_compression,
        )

    def _initialize_shared_context_and_ledger(self) -> None:
        """Initialize shared context history and task ledger."""
        # Shared context history
        self.shared_context: list[dict[str, Any]] = []

        # Task ledger – created per run() call
        self.ledger: TaskLedger | None = None

    def _setup_tech_lead_agent(
        self,
        agent_configs: dict[str, Any],
        default_provider: ModelProvider,
        system_prompt: str | None,
        environment_context: str | None,
    ) -> None:
        """Set up the Tech Lead agent with prompt, identity, and configuration.

        Args:
            agent_configs: Dictionary of agent configurations.
            default_provider: The default model provider.
            system_prompt: Optional override for Tech Lead system prompt.
            environment_context: Pre-formatted environment block for agents.
        """
        self._register_delegate_task_tool()
        tl_prompt = self._create_tech_lead_prompt(agent_configs, system_prompt, environment_context)
        tl_identity = self._create_tech_lead_identity()
        self._create_tech_lead_agent(default_provider, tl_prompt, tl_identity)
        self._configure_tech_lead_stall_detection()

    def _register_delegate_task_tool(self) -> None:
        """Register the delegate_task tool if not already present.

        Tech Lead uses the parent tool_registry directly (not a copy)
        so that tools added later (MCP, extensions, tests) are visible.
        DelegateTaskTool is registered on the parent;
        delegated agents won't see it because create_scoped_registry
        filters by each agent's allowed_tools list.
        """
        if not self.tool_registry.get("delegate_task"):
            self.tool_registry.register(DelegateTaskTool())

    def _create_tech_lead_prompt(
        self,
        agent_configs: dict[str, Any],
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
        from henchman.agents.prompts import get_agent_prompt

        team_members = [f"{c.name} ({c.role})" for c in agent_configs.values() if c.enabled]

        team_descriptions = {
            c.role: c.description or "" for c in agent_configs.values() if c.enabled
        }

        return system_prompt or get_agent_prompt(
            role="tech_lead",
            team_members=team_members,
            delegatable_agents=[c.role for c in agent_configs.values() if c.enabled],
            environment_context=environment_context,
            team_descriptions=team_descriptions,
        )

    def _create_tech_lead_identity(self) -> Any:
        """Create the Tech Lead agent identity.

        Returns:
            AgentIdentity instance for the Tech Lead.
        """
        from henchman.agents.identity import AgentIdentity

        return AgentIdentity(
            id="tech_lead",
            name="Leader",
            role="tech_lead",
            description="Architect, implementer, and quality gate",
        )

    def _create_tech_lead_agent(
        self,
        default_provider: ModelProvider,
        tl_prompt: str,
        tl_identity: Any,
    ) -> None:
        """Create the Tech Lead agent instance.

        Args:
            default_provider: The default model provider.
            tl_prompt: Tech Lead system prompt.
            tl_identity: Tech Lead agent identity.
        """
        self.tech_lead = Agent(
            provider=default_provider,
            tool_registry=self.tool_registry,
            system_prompt=tl_prompt,
            identity=tl_identity,
            intelligent_context=self.settings.context.intelligent_context,
            importance_threshold=self.settings.context.importance_threshold,
            cluster_similarity_threshold=self.settings.context.cluster_similarity_threshold,
            adaptive_compression=self.settings.context.adaptive_compression,
        )

    def _configure_tech_lead_stall_detection(self) -> None:
        """Configure stall detection for the Tech Lead agent.

        Tech Lead legitimately narrates plans before delegating —
        disable stall detection so it isn't killed for planning.
        """
        self.tech_lead.stall_detection_enabled = False

    async def run(self, user_input: str) -> AsyncIterator[AgentEvent]:
        """Run the orchestrator with user input.

        Args:
            user_input: The user's request.

        Yields:
            AgentEvent stream from the orchestration.
        """
        # Initialize a fresh task ledger for this request
        self.ledger = TaskLedger(goal=user_input[:MAX_USER_INPUT_LENGTH])

        # Reset metrics for this run
        self.metrics.reset_for_run()

        # Set task start time
        self.metrics.performance.task_start_time = time.time()

        yield AgentEvent(
            type=EventType.AGENT_STARTED, data={"agent": "tech_lead"}, source_agent="orchestrator"
        )

        event_count = 0
        params = AgentLoopParams(
            agent=self.tech_lead,
            input_text=user_input,
        )
        async for event in self._run_agent_loop(params):
            event_count += 1
            yield event

        # Set task end time and calculate duration
        self.metrics.performance.task_end_time = time.time()

        # Calculate final metrics
        self.metrics.calculate_final_metrics()

        # Assess whether the agent actually did meaningful work
        status = self._assess_completion(self.tech_lead)
        self.last_completion_status = status

        if status == CompletionStatus.NO_WORK_DONE:
            yield AgentEvent(
                type=EventType.ERROR,
                data="Agent completed without performing any actions.",
                source_agent="orchestrator",
            )

        yield AgentEvent(
            type=EventType.AGENT_COMPLETED,
            data={"agent": "tech_lead", "status": status.value},
            source_agent="orchestrator",
        )

    async def run_direct(self, role: str, user_input: str) -> AsyncIterator[AgentEvent]:
        """Run a specific agent directly, bypassing the Tech Lead.

        Args:
            role: The role ID of the agent to run.
            user_input: The user's request.

        Yields:
            AgentEvent stream from the agent.
        """
        agent = self.pool.get_agent(role)

        yield AgentEvent(
            type=EventType.AGENT_STARTED, data={"agent": role}, source_agent="orchestrator"
        )

        params = AgentLoopParams(
            agent=agent,
            input_text=user_input,
        )
        async for event in self._run_agent_loop(params):
            yield event

        status = self._assess_completion(agent)
        self.last_completion_status = status

        if status == CompletionStatus.NO_WORK_DONE:
            yield AgentEvent(
                type=EventType.ERROR,
                data="Agent completed without performing any actions.",
                source_agent="orchestrator",
            )

        yield AgentEvent(
            type=EventType.AGENT_COMPLETED,
            data={"agent": role, "status": status.value},
            source_agent="orchestrator",
        )

    def _check_thinking_pattern(self, agent: Agent) -> AgentEvent | None:
        """Validate Tech Lead thinking patterns and update metrics.

        Args:
            agent: The agent to check (should be Tech Lead).

        Returns:
            AgentEvent if thinking reminder is needed, None otherwise.
        """
        if agent is not self.tech_lead or not agent.messages:
            return None

        last_message = agent.messages[-1]
        if last_message.role != "assistant":
            return None

        content = last_message.content or ""
        if content.strip().startswith("THINKING:"):
            self.metrics.thinking_pattern_usage += 1
            lines = content.strip().split("\n")
            thinking_lines = [
                line for line in lines if line.strip().startswith(("1.", "2.", "3.", "4.", "5."))
            ]
            if len(thinking_lines) >= _MIN_THINKING_LINES:
                self.metrics.thinking_quality_score = min(
                    _MAX_THINKING_SCORE,
                    self.metrics.thinking_quality_score + _THINKING_QUALITY_INCREMENT,
                )
            return None
        elif content.strip():
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
        return None

    def _check_stall_failure(self, agent: Agent) -> AgentEvent | None:
        """Check if agent has stalled and report failure.

        Args:
            agent: The agent to check.

        Returns:
            AgentEvent if stall failure occurred, None otherwise.
        """
        if agent is self.tech_lead or not agent._stall_failure:
            return None

        role_label = agent.identity.role if agent.identity else "agent"
        fail_msg = (
            f"STALL FAILURE: {role_label} announced intent but "
            f"never used tools after "
            f"{agent._stall_nudge_count} nudges. "
            f"The task was NOT completed."
        )
        agent.messages.append(Message(role="assistant", content=fail_msg))
        return AgentEvent(
            type=EventType.ERROR,
            data=fail_msg,
            source_agent=role_label,
        )

    @staticmethod
    def _last_assistant_content(agent: Agent) -> str:
        """Return the content of the agent's last assistant message.

        Walks backwards through the message history to find the most
        recent assistant message with non-empty content.

        Args:
            agent: The agent whose messages to inspect.

        Returns:
            The content string, or empty string if none found.
        """
        for msg in reversed(agent.messages):
            if msg.role == "assistant" and msg.content:
                return msg.content
        return ""

    def _assess_completion(self, agent: Agent) -> CompletionStatus:
        """Assess whether an agent performed meaningful work.

        Inspects the tool call count from the last loop run and
        agent state to determine the appropriate completion status.

        Args:
            agent: The agent whose work to assess.

        Returns:
            A ``CompletionStatus`` describing the outcome.
        """
        tool_calls = getattr(self, "_last_loop_tool_call_count", 0)

        # Check for stall failure first — agent announced intent but never acted
        if getattr(agent, "_stall_failure", False):
            return CompletionStatus.STALLED

        # If no tool calls were made at all, the agent did nothing
        if tool_calls == 0:
            return CompletionStatus.NO_WORK_DONE

        return CompletionStatus.COMPLETED

    def _prepare_delegation_brief(self, tool_call: ToolCall) -> dict[str, Any]:
        """Extract structured delegation fields from tool call.

        Args:
            tool_call: The delegate_task tool call.

        Returns:
            Structured delegation brief.
        """
        return {
            "done_when": tool_call.arguments.get("done_when"),
            "context": tool_call.arguments.get("context"),
            "files": tool_call.arguments.get("files"),
            "background": tool_call.arguments.get("background"),
            "requirements": tool_call.arguments.get("requirements"),
            "depends_on": tool_call.arguments.get("depends_on"),
        }

    def _update_delegation_metrics(self, target: str) -> None:
        """Update metrics for a delegation.

        Args:
            target: Target agent role.
        """
        self.metrics.delegation_count += 1
        if target in self.metrics.delegation_by_type:
            self.metrics.delegation_by_type[target] += 1

    def _process_delegation_result(
        self,
        agent: Agent,
        tool_call: ToolCall,
        result_content: str,
        delegation_had_error: bool,
        ledger_record: Any | None,
    ) -> str:
        """Process the result of a delegation.

        Args:
            agent: The calling agent.
            tool_call: The delegate_task tool call.
            result_content: Result content from delegation.
            delegation_had_error: Whether delegation had errors.
            ledger_record: Ledger record for this delegation.

        Returns:
            Content to submit as tool result.
        """
        # Update ledger with outcome
        if self.ledger and ledger_record:
            if delegation_had_error:
                self.ledger.fail_delegation(ledger_record, result_content)
            else:
                self.ledger.complete_delegation(ledger_record, result_content)

        # Append ledger snapshot so Tech Lead can re-orient
        submitted_content = result_content
        if self.ledger:
            submitted_content = f"{result_content}\n\n{self.ledger.render()}"

        agent.submit_tool_result(tool_call.id, submitted_content)
        return submitted_content

    def _inject_role_anchor(self, agent: Agent, tool_call_count: int) -> None:
        """Inject periodic role anchoring reminder if needed.

        Args:
            agent: The agent to anchor.
            tool_call_count: Current tool call count.
        """
        if tool_call_count > 0 and tool_call_count % _ROLE_ANCHOR_INTERVAL == 0 and agent.identity:
            role_id = agent.identity.role or agent.identity.id
            mission_note = ""
            if self.ledger:
                recap = self.ledger.mission_recap()
                if recap:
                    mission_note = f" Mission: {recap}"
            anchor_msg = (
                f"[Role Anchor] You are the {role_id.upper()}. "
                f"Stay focused on your assigned responsibilities. "
                f"Do not overstep your role boundaries.{mission_note}"
            )
            agent.messages.append(Message(role="user", content=anchor_msg))

    def _enforce_turn_limits(
        self,
        agent: Agent,
        max_turns: int,
        tool_call_count: int,
        msg_start_index: int,
        wrapup_warned: bool,
    ) -> tuple[bool, bool, AgentEvent | None]:
        """Enforce turn limits with warnings and hard stops.

        Args:
            agent: The agent to check.
            max_turns: Maximum allowed turns (0 = unlimited).
            tool_call_count: Current tool call count.
            msg_start_index: Message start index for timeout summary.
            wrapup_warned: Whether wrap-up warning has been issued.

        Returns:
            Tuple of (should_break, new_wrapup_warned, error_event).
        """
        if max_turns <= 0:
            return False, wrapup_warned, None

        remaining = max_turns - tool_call_count
        if remaining <= 0:
            # Hard stop — build a progress summary
            progress = self._build_timeout_summary(agent, msg_start_index)
            timeout_msg = (
                "[TURN LIMIT REACHED] You have used all available "
                "turns. Here is a summary of your progress so far:\n\n"
                f"{progress}\n\n"
                "The Tech Lead will decide how to proceed."
            )
            agent.messages.append(Message(role="assistant", content=timeout_msg))
            error_event = AgentEvent(
                type=EventType.ERROR,
                data=f"Turn limit ({max_turns}) reached for "
                f"{agent.identity.role if agent.identity else 'agent'}",
                source_agent="orchestrator",
            )
            return True, wrapup_warned, error_event

        if not wrapup_warned and remaining <= _WRAPUP_WARNING_OFFSET:
            warn_msg = (
                f"[WRAP-UP WARNING] You have {remaining} tool-call "
                f"turn(s) remaining. Prioritise:\n"
                f"1. Run any final verification (tests, lint).\n"
                f"2. Write a completion report using the "
                f"DELEGATION_SUMMARY_SCHEMA format.\n"
                f"3. List BLOCKERS if you cannot finish in time."
            )
            agent.messages.append(Message(role="user", content=warn_msg))
            return False, True, None

        return False, wrapup_warned, None

    def _update_tool_metrics(
        self, tool_name: str, arguments: dict[str, Any], success: bool
    ) -> None:
        """Update metrics for a tool call.

        Args:
            tool_name: Name of the tool called.
            arguments: Arguments passed to the tool.
            success: Whether the tool call was successful.
        """
        self.metrics.update_tool_metrics(tool_name, arguments, success)

    def _track_tool_error(
        self, tool_errors: list[str], tool_name: str, result_content: str | None
    ) -> None:
        """Track tool errors for delegation summaries.

        Args:
            tool_errors: List to collect tool errors.
            tool_name: Name of the tool that failed.
            result_content: Error content from tool result.
        """
        error_message = result_content or "unknown error"
        truncated_error = error_message[:_TOOL_ERROR_MAX_LENGTH]
        tool_errors.append(f"{tool_name}: {truncated_error}")

    def _yield_tool_result_event(
        self, agent: Agent, tool_call: ToolCall, result_content: str, success: bool = True
    ) -> AgentEvent:
        """Create and yield a tool result event.

        Args:
            agent: The agent that executed the tool.
            tool_call: The tool call that was executed.
            result_content: Result content from tool execution.
            success: Whether the tool execution was successful.

        Returns:
            AgentEvent for the tool result.
        """
        return AgentEvent(
            type=EventType.TOOL_CALL_RESULT,
            data={
                "tool_call_id": tool_call.id,
                "tool_name": tool_call.name,
                "result": (result_content or "")[:_RESULT_PREVIEW_LENGTH],
                "success": success,
            },
            source_agent=agent.identity.id if agent.identity else None,
        )



    async def _run_agent_loop(
        self,
        params: AgentLoopParams,
    ) -> AsyncIterator[AgentEvent]:
        """Handle the run loop for an agent, executing tools and intercepting delegations.

        This method is the core execution engine. It:
        1. Runs the agent and collects events
        2. Collects ALL tool calls from a single LLM response
        3. Executes regular tools via the agent's tool registry
        4. Intercepts ``delegate_task`` calls and runs sub-agent loops
        5. Submits all results back to the agent and continues
        6. Periodically re-injects role anchoring reminders (Task 5)
        7. Enforces per-delegation turn limits with wrap-up warnings
        8. Tracks tool errors for aggregation in delegation summaries

        Args:
            params: Agent loop parameters containing agent, input, depth, etc.

        Yields:
            AgentEvents from the agent loop.
        """
        # Extract parameters from the params object
        agent = params.agent
        if agent is None:
            raise ValueError("Agent must be provided in AgentLoopParams")

        user_input = params.input_text
        depth = params.depth
        max_turns = params.max_turns
        msg_start_index = params.msg_start_index

        generator: AsyncIterator[AgentEvent] = agent.run(user_input)
        tool_call_count = 0
        tool_errors: list[str] = []
        wrapup_warned = False
        colon_stall_retries = 0

        while True:
            # Drain the current generator, collecting tool calls
            pending_tool_calls: list[ToolCall] = []

            # Collect events and extract tool calls
            async for event in self._collect_events_and_tool_calls(generator, pending_tool_calls):
                yield event

            if not pending_tool_calls:
                # Check thinking patterns and stall failures when no tools are pending
                thinking_event = self._check_thinking_pattern(agent)
                if thinking_event:
                    yield thinking_event

                stall_event = self._check_stall_failure(agent)
                if stall_event:
                    yield stall_event

                # Check for colon stall
                colon_stall_result = self._check_colon_stall(agent, colon_stall_retries)
                if colon_stall_result is not None:
                    # Colon stall occurred, update generator and retry count
                    generator, colon_stall_retries = colon_stall_result
                    continue

                # Agent finished — exit the loop
                break
            should_break, wrapup_warned, error_event = self._enforce_turn_limits(
                agent, max_turns, tool_call_count, msg_start_index, wrapup_warned
            )
            if error_event:
                yield error_event
            if should_break:
                break

            # Execute all pending tool calls (regular + delegation)
            async for event in self._process_pending_tool_calls(
                agent, pending_tool_calls, depth, tool_errors
            ):
                yield event

            tool_call_count += len(pending_tool_calls)

            # All tool results submitted — continue the agent
            generator = agent.continue_with_tool_results()

        # Store tool errors on the agent for the caller to retrieve
        if not hasattr(agent, "_delegation_tool_errors"):
            agent._delegation_tool_errors = []  # type: ignore[attr-defined]
        agent._delegation_tool_errors = tool_errors  # type: ignore[attr-defined]

        # Store final tool call count so callers can assess completion
        self._last_loop_tool_call_count = tool_call_count

    def _check_colon_stall(
        self,
        agent: Agent,
        colon_stall_retries: int,
    ) -> tuple[AsyncIterator[AgentEvent], int] | None:
        """Check for colon stall pattern and handle if detected.

        Colon-stall guard: catch ANY agent (including tech_lead)
        that ends its response with ":" - a high-confidence signal
        the agent announced work but stopped without doing it.

        Args:
            agent: The agent to check.
            colon_stall_retries: Current colon stall retry count.

        Returns:
            - None: No colon stall detected
            - Tuple: Colon stall detected, return updated generator and retry count
        """
        if colon_stall_retries >= _MAX_COLON_STALL_RETRIES:
            return None

        last_content = self._last_assistant_content(agent)
        if (
            last_content
            and last_content.strip().endswith(":")
            and len(last_content.strip()) > _COLON_STALL_MIN_LENGTH
        ):
            colon_stall_retries += 1
            agent.messages.append(
                Message(role="user", content=_COLON_STALL_NUDGE)
            )
            return agent.continue_with_tool_results(), colon_stall_retries

        return None

    async def _collect_events_and_tool_calls(
        self,
        generator: AsyncIterator[AgentEvent],
        pending_tool_calls: list[ToolCall],
    ) -> AsyncIterator[AgentEvent]:
        """Collect events from generator and extract pending tool calls.

        This method drains the generator, yields all events, and collects
        tool call requests into the pending_tool_calls list.

        Args:
            generator: Event generator from the agent.
            pending_tool_calls: List to collect tool calls into (modified in-place).

        Yields:
            AgentEvents from the generator.
        """
        try:
            async for event in generator:
                if event.type == EventType.TOOL_CALL_REQUEST:
                    pending_tool_calls.append(event.data)
                yield event
        except StopAsyncIteration:
            pass



    async def _process_pending_tool_calls(
        self,
        agent: Agent,
        pending_tool_calls: list[ToolCall],
        depth: int,
        tool_errors: list[str],
    ) -> AsyncIterator[AgentEvent]:
        """Process all pending tool calls from an agent.

        Args:
            agent: The agent that made the tool calls.
            pending_tool_calls: List of tool calls to process.
            depth: Current delegation depth.
            tool_errors: List to collect tool errors.

        Yields:
            AgentEvents from tool execution.
        """
        for tool_call in pending_tool_calls:
            if tool_call.name == _DELEGATE_TASK_TOOL:
                async for event in self._execute_delegation_tool(
                    agent, tool_call, depth, tool_errors
                ):
                    yield event
            else:
                async for event in self._execute_regular_tool(agent, tool_call, tool_errors):
                    yield event

    async def _execute_delegation_tool(
        self,
        agent: Agent,
        tool_call: ToolCall,
        depth: int,
        tool_errors: list[str],
    ) -> AsyncIterator[AgentEvent]:
        """Execute a delegation tool call.

        Args:
            agent: The agent that made the delegation.
            tool_call: The delegation tool call to execute.
            depth: Current delegation depth.
            tool_errors: List to collect tool errors (unused for delegation).

        Yields:
            AgentEvents from delegation execution.
        """
        target = tool_call.arguments.get("agent", "")
        task = tool_call.arguments.get("task", "")

        # Update delegation metrics
        self._update_delegation_metrics(target)
        self._update_tool_metrics(_DELEGATE_TASK_TOOL, tool_call.arguments, True)

        # Register delegation in ledger
        ledger_record = None
        if self.ledger:
            ledger_record = self.ledger.add_delegation(agent=target, task=task)

        yield AgentEvent(
            type=EventType.AGENT_DELEGATED,
            data={
                "from": agent.identity.id if agent.identity else "unknown",
                "to": target,
                "task": task,
            },
            source_agent="orchestrator",
        )

        # Run delegation and collect summary
        result_content = ""
        delegation_had_error = False
        delegation_status = ""
        delegation_brief = self._prepare_delegation_brief(tool_call)
        async for sub_event in self._run_delegation(target, task, delegation_brief, depth + 1):
            if sub_event.type == EventType.AGENT_COMPLETED:
                result_content = sub_event.data.get("summary", "Completed.")
                delegation_status = sub_event.data.get("status", "completed")
            if sub_event.type == EventType.ERROR:
                delegation_had_error = True
            yield sub_event

        if not result_content:
            result_content = "Delegation completed (no output)."

        # Specialist doing no work is a soft failure — inform the Tech Lead
        # but don't treat it as a hard error for ledger tracking.
        if delegation_status == "no_work_done":
            result_content = (
                f"⚠️ Agent {target} ended without making any tool calls.\n\n"
                f"{result_content}"
            )

        # Process delegation result
        self._process_delegation_result(
            agent, tool_call, result_content, delegation_had_error, ledger_record
        )

        # Yield tool result event using helper method
        yield self._yield_tool_result_event(agent, tool_call, result_content, success=True)

    async def _execute_regular_tool(
        self,
        agent: Agent,
        tool_call: ToolCall,
        tool_errors: list[str],
    ) -> AsyncIterator[AgentEvent]:
        """Execute a regular (non-delegation) tool call.

        Args:
            agent: The agent that made the tool call.
            tool_call: The tool call to execute.
            tool_errors: List to collect tool errors.

        Yields:
            AgentEvents from tool execution.
        """
        result = await agent.tool_registry.execute(tool_call.name, tool_call.arguments)
        agent.submit_tool_result(tool_call.id, result.content or "")

        # Track tool errors for delegation summaries using helper method
        if not result.success:
            self._track_tool_error(tool_errors, tool_call.name, result.content)

        # Update metrics for tool usage
        self._update_tool_metrics(tool_call.name, tool_call.arguments, result.success)

        # Yield tool result event using helper method
        yield self._yield_tool_result_event(agent, tool_call, result.content or "", result.success)

    def _prepare_delegation_context(
        self,
        target_role: str,
        brief: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Prepare context for delegation by adding handoff notes and failure context.

        Args:
            target_role: The role ID of the specialist.
            brief: Original delegation brief.

        Returns:
            Updated brief with handoff notes and failure context added.
        """
        brief = dict(brief) if brief else {}

        # Cross-delegation handoff: auto-inject recent shared_context
        # entries into the brief's background field so the specialist
        # knows what prior agents accomplished.
        if self.shared_context:
            handoff_lines = []
            for entry in self.shared_context[-RECENT_CONTEXT_ENTRIES:]:
                handoff_lines.append(f"- **{entry['agent']}**: {entry['summary'][:MAX_SUMMARY_LENGTH]}")
            handoff_notes = "### Prior agent work\n" + "\n".join(handoff_lines)
            existing_bg = brief.get("background") or ""
            brief["background"] = (
                f"{existing_bg}\n\n{handoff_notes}" if existing_bg else handoff_notes
            )

        # Inject prior failure context if the same role failed before (#17)
        if self.ledger:
            prior_failures = [
                d
                for d in self.ledger.delegations
                if d.agent == target_role and d.status == "FAILED"
            ]
            if prior_failures:
                last_fail = prior_failures[-1]
                fail_note = (
                    f"### Prior Attempt Failed\n"
                    f"A previous delegation to you for "
                    f'"{last_fail.task}" ended with status FAILED. '
                    f"Avoid repeating the same approach."
                )
                existing_bg = brief.get("background") if brief else None
                if brief is None:
                    brief = {}
                brief["background"] = f"{existing_bg}\n\n{fail_note}" if existing_bg else fail_note

        return brief

    def _process_delegation_results(
        self,
        target_role: str,
        target_agent: Agent,
        msg_start: int,
    ) -> tuple[str, dict[str, str], CompletionStatus]:
        """Process delegation results and prepare completion data.

        Args:
            target_role: The role ID of the specialist.
            target_agent: The agent that executed the delegation.
            msg_start: Index where the agent's messages started.

        Returns:
            Tuple of (summary, parsed_completion_report, completion_status)
        """
        # Build summary from the agent's conversation history, which stores
        # accumulated content correctly without streaming duplication.
        summary_parts = [
            m.content
            for m in target_agent.messages[msg_start:]
            if m.role == "assistant" and m.content
        ]
        summary = "\n\n".join(summary_parts)

        # Append tool-error digest so the Tech Lead sees what failed
        tool_errors: list[str] = getattr(target_agent, "_delegation_tool_errors", [])
        if tool_errors:
            error_digest = "\n--- ⚠️ TOOL ERRORS ---\n" + "\n".join(
                f"• {e}" for e in tool_errors[-RECENT_ERRORS_TO_SHOW:]
            )
            summary = f"{summary}\n{error_digest}"

        # Parse structured completion report from specialist output
        parsed = self._parse_completion_report(summary)

        # Assess whether the specialist actually did meaningful work
        status = self._assess_completion(target_agent)

        return summary, parsed, status

    async def _run_delegation(
        self,
        target_role: str,
        task: str,
        brief: dict[str, Any] | None,
        depth: int,
    ) -> AsyncIterator[AgentEvent]:
        """Execute a delegation to a specialist agent.

        Each specialist starts with a **clean context** -- its conversation
        history is cleared before every delegation so it operates from a
        self-contained brief rather than accumulated (and often polluted)
        prior context.

        The Tech Lead is the system of record.  All relevant information
        must flow through the structured ``brief`` fields that the Tech
        Lead populates when calling ``delegate_task``.

        Improvements in v0.2.7:
        - Enforces ``max_delegation_turns`` per specialist run.
        - Auto-injects cross-delegation handoff notes from ``shared_context``.
        - Appends tool-error digest to the summary returned to Tech Lead.
        - Parses structured completion report for richer AGENT_COMPLETED data.

        Args:
            target_role: The role ID of the specialist.
            task: The task description.
            brief: Structured delegation brief with optional keys:
                ``done_when``, ``context``, ``files``, ``background``,
                ``requirements``.
            depth: Current recursion depth.

        Yields:
            AgentEvents from the specialist agent.
        """
        # Validate delegation depth
        if self._is_delegation_depth_exceeded(depth):
            async for event in self._yield_depth_exceeded_error():
                yield event
            return

        # Get target agent with error handling
        target_agent_result = await self._get_target_agent_with_error_handling(target_role)
        if isinstance(target_agent_result, AgentEvent):
            yield target_agent_result
            async for event in self._yield_agent_not_found_completion(target_role):
                yield event
            return
        target_agent = target_agent_result

        # Start delegation
        yield AgentEvent(
            type=EventType.AGENT_STARTED, data={"agent": target_role}, source_agent="orchestrator"
        )

        # Prepare and execute delegation
        full_task, msg_start = self._prepare_delegation_execution(target_agent, target_role, brief, task)

        # Execute the agent loop
        async for event in self._execute_delegation_loop(target_agent, full_task, depth, msg_start):
            yield event

        # Finalize delegation
        async for event in self._finalize_delegation(target_role, target_agent, msg_start):
            yield event

    def _is_delegation_depth_exceeded(self, depth: int) -> bool:
        """Check if delegation depth exceeds configured limit.

        Args:
            depth: Current recursion depth.

        Returns:
            True if depth exceeds limit, False otherwise.
        """
        return depth > self.settings.agents.max_delegation_depth

    async def _yield_depth_exceeded_error(self) -> AsyncIterator[AgentEvent]:
        """Yield error events for exceeded delegation depth.

        Yields:
            ERROR and AGENT_COMPLETED events.
        """
        yield AgentEvent(
            type=EventType.ERROR,
            data=f"Error: Maximum delegation depth ({self.settings.agents.max_delegation_depth}) exceeded.",
            source_agent="orchestrator",
        )
        yield AgentEvent(
            type=EventType.AGENT_COMPLETED,
            data={"summary": "Max depth exceeded"},
            source_agent="orchestrator",
        )

    async def _get_target_agent_with_error_handling(
        self, target_role: str
    ) -> Agent | AgentEvent:
        """Get target agent with proper error handling.

        Args:
            target_role: The role ID of the specialist.

        Returns:
            Agent instance if found, otherwise AgentEvent with error.
        """
        try:
            return self.pool.get_agent(target_role)
        except ValueError as e:
            return AgentEvent(type=EventType.ERROR, data=str(e), source_agent="orchestrator")

    async def _yield_agent_not_found_completion(
        self, target_role: str
    ) -> AsyncIterator[AgentEvent]:
        """Yield completion event for agent not found error.

        Args:
            target_role: The role ID that was not found.

        Yields:
            AGENT_COMPLETED event.
        """
        yield AgentEvent(
            type=EventType.AGENT_COMPLETED,
            data={"summary": f"Agent {target_role} not found"},
            source_agent="orchestrator",
        )

    def _prepare_delegation_execution(
        self,
        target_agent: Agent,
        target_role: str,
        brief: dict[str, Any] | None,
        task: str,
    ) -> tuple[str, int]:
        """Prepare agent and context for delegation execution.

        Args:
            target_agent: The agent to execute delegation.
            target_role: The role ID of the specialist.
            brief: Structured delegation brief.
            task: The task description.

        Returns:
            Tuple of (full_task, msg_start) where:
            - full_task: Assembled task with context
            - msg_start: Starting message index for result extraction
        """
        # Clean start: wipe prior conversation so the specialist has no
        # stale context from earlier delegations. The system prompt is
        # preserved by clear_history().
        target_agent.clear_history()

        # Prepare context for delegation
        prepared_brief = self._prepare_delegation_context(target_role, brief)

        # Assemble the full task from the structured brief fields
        full_task = self._assemble_delegation_input(
            task, prepared_brief, mission=self.ledger.goal if self.ledger else None
        )

        # Record where the agent's messages start so we can extract a clean
        # summary afterwards (content events may be duplicated during streaming).
        msg_start = len(target_agent.messages)

        return full_task, msg_start

    async def _execute_delegation_loop(
        self,
        target_agent: Agent,
        full_task: str,
        depth: int,
        msg_start: int,
    ) -> AsyncIterator[AgentEvent]:
        """Execute the agent loop for delegation.

        Args:
            target_agent: The agent to execute.
            full_task: Assembled task with context.
            depth: Current recursion depth.
            msg_start: Starting message index.

        Yields:
            AgentEvents from the specialist agent.
        """
        max_turns = self.settings.agents.max_delegation_turns
        params = AgentLoopParams(
            agent=target_agent,
            input_text=full_task,
            depth=depth,
            max_turns=max_turns,
            msg_start_index=msg_start,
        )
        async for event in self._run_agent_loop(params):
            yield event

    async def _finalize_delegation(
        self,
        target_role: str,
        target_agent: Agent,
        msg_start: int,
    ) -> AsyncIterator[AgentEvent]:
        """Process delegation results and yield completion event.

        Args:
            target_role: The role ID of the specialist.
            target_agent: The agent that executed the delegation.
            msg_start: Starting message index for result extraction.

        Yields:
            AGENT_COMPLETED event with results.
        """
        # Process delegation results
        summary, parsed, status = self._process_delegation_results(
            target_role, target_agent, msg_start
        )

        # Update shared context (still tracked for Tech Lead's use, just not
        # injected into specialist prompts)
        self.shared_context.append(
            {
                "agent": target_role,
                "summary": summary[:MAX_CONTENT_LENGTH],
                "files_modified": parsed.get("files_modified", ""),
                "timestamp": datetime.now().isoformat(),
            }
        )

        yield AgentEvent(
            type=EventType.AGENT_COMPLETED,
            data={
                "agent": target_role,
                "summary": summary,
                "status": status.value,
                **parsed,
            },
            source_agent="orchestrator",
        )

    @staticmethod
    def _assemble_delegation_input(
        task: str,
        brief: dict[str, Any] | None,
        mission: str | None = None,
    ) -> str:
        """Build a self-contained input string from the structured delegation brief.

        The resulting text gives the specialist everything it needs without
        any prior conversation history.

        Args:
            task: The core task description.
            brief: Optional structured fields from the Tech Lead.
            mission: Optional high-level mission statement for context.

        Returns:
            A formatted string ready to be passed as user input to the specialist.
        """
        sections: list[str] = []

        # Mission header gives the specialist project-level context (#6)
        if mission:
            sections.append(f"## Mission\n{mission}")

        sections.append(f"## Task\n{task}")

        if not brief:
            return "\n\n".join(sections)

        if brief.get("done_when"):
            sections.append(
                f"## Done When\n{brief['done_when']}\n"
                f"_(Stop working once these conditions are met.)_"
            )

        if brief.get("requirements"):
            sections.append(f"## Requirements\n{brief['requirements']}")

        files = brief.get("files")
        if files:
            file_list = "\n".join(f"- `{f}`" for f in files)
            sections.append(f"## Relevant Files\n{file_list}")

        # Dependency chain awareness (#10)
        depends_on = brief.get("depends_on")
        if depends_on:
            if isinstance(depends_on, str):
                depends_on = [depends_on]
            dep_list = "\n".join(f"- {d}" for d in depends_on)
            sections.append(
                f"## Depends On\n{dep_list}\n"
                f"_(These tasks were completed earlier; "
                f"build on their outputs.)_"
            )

        if brief.get("background"):
            sections.append(f"## Background\n{brief['background']}")

        if brief.get("context"):
            sections.append(f"## Additional Context\n{brief['context']}")

        return "\n\n".join(sections)

    @staticmethod
    def _parse_completion_report(summary: str) -> dict[str, str]:
        """Extract structured fields from a specialist's completion report.

        Looks for the ``DELEGATION_SUMMARY_SCHEMA`` format::

            STATUS: DONE | FAILED | BLOCKED
            FILES_MODIFIED: ...
            VERIFICATION: ...

        Args:
            summary: Raw summary text from the specialist.

        Returns:
            Dict with extracted fields (may be empty if format not found).
        """
        parsed: dict[str, str] = {}
        patterns = {
            "status": r"STATUS:\s*(.+?)(?:\n|$)",
            "files_modified": r"FILES_MODIFIED:\s*(.+?)(?:\n|$)",
            "tests_run": r"TESTS_RUN:\s*(.+?)(?:\n|$)",
            "verification": r"VERIFICATION:\s*(.+?)(?:\n|$)",
            "blockers": r"BLOCKERS:\s*(.+?)(?:\n|$)",
            "handoff_notes": r"HANDOFF_NOTES:\s*(.+?)(?:\n|$)",
            "artifacts": r"ARTIFACTS:\s*(.+?)(?:\n|$)",
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, summary, re.IGNORECASE)
            if match:
                parsed[key] = match.group(1).strip()
        return parsed

    @staticmethod
    def _build_timeout_summary(agent: Agent, msg_start: int) -> str:
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

        for msg in agent.messages[msg_start:]:
            if msg.role == "assistant":
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        tools_used.append(
                            f"{tc.name}({', '.join(f'{k}={v!r}' for k, v in list(tc.arguments.items())[:MAX_TOOL_ARGUMENTS_TO_DISPLAY])})"
                        )
                        # Track file paths from common tools
                        path = tc.arguments.get("path") or tc.arguments.get("file_path")
                        if path and isinstance(path, str):
                            files_touched.add(path)
                if msg.content:
                    narration_parts.append(msg.content[:MAX_SUMMARY_LENGTH])

        lines = ["**Progress at timeout:**"]
        if tools_used:
            lines.append(f"- Tool calls made: {len(tools_used)}")
            # Show last 10 tool calls
            for t in tools_used[-RECENT_TOOLS_TO_SHOW:]:
                lines.append(f"  • {t[:MAX_TOOL_CALL_DISPLAY_LENGTH]}")
        if files_touched:
            lines.append(f"- Files touched: {', '.join(sorted(files_touched))}")
        if narration_parts:
            lines.append(f"- Last agent output: {narration_parts[-1][:MAX_NARRATION_DISPLAY_LENGTH]}")
        if not tools_used and not narration_parts:
            lines.append("- No significant progress was made.")
        return "\n".join(lines)

    def get_metrics_report(self) -> str:
        """Generate a formatted performance metrics dashboard.

        Returns:
            A formatted markdown string with performance metrics.
        """
        report_lines = ["## Performance Metrics Dashboard", ""]

        # Add efficiency metrics section
        report_lines.extend(self._generate_efficiency_metrics())
        report_lines.append("")

        # Add quality metrics section
        report_lines.extend(self._generate_quality_metrics())
        report_lines.append("")

        # Add target performance metrics section
        report_lines.extend(self._generate_target_metrics())
        report_lines.append("")

        # Add detailed statistics section
        report_lines.extend(self._generate_detailed_statistics())

        return "\n".join(report_lines)

    def _generate_efficiency_metrics(self) -> list[str]:
        """Generate the efficiency metrics section of the report."""
        lines = ["### Efficiency Metrics"]

        # Task completion time
        lines.append(self._format_task_completion_time())

        # Files accessed
        lines.append(self._format_files_accessed())

        # Tool usage
        lines.append(self._format_tool_usage())

        # Delegation rate
        lines.append(self._format_delegation_rate())

        return lines

    def _generate_quality_metrics(self) -> list[str]:
        """Generate the quality metrics section of the report."""
        lines = ["### Quality Metrics"]

        # Test results
        lines.append(self._format_test_results())

        # Code coverage
        lines.append(self._format_code_coverage())

        # Linting status
        lines.append(self._format_linting_status())

        # Documentation coverage
        lines.append(self._format_documentation_coverage())

        return lines

    def _generate_target_metrics(self) -> list[str]:
        """Generate the target performance metrics section of the report."""
        lines = ["### Target Performance Metrics"]

        # File re-reads
        lines.append(self._format_file_re_reads())

        # Delegation rate target
        lines.append(self._format_delegation_target())

        # Error rate target
        lines.append(self._format_error_rate_target())

        # Context window usage target
        lines.append(self._format_context_window_target())

        return lines

    def _generate_detailed_statistics(self) -> list[str]:
        """Generate the detailed statistics section of the report."""
        lines = ["### Detailed Statistics"]

        # Tool call breakdown using structured data
        lines.extend(self._format_tool_call_statistics())

        # Thinking metrics
        lines.append(f"- **Thinking Pattern Usage**: {self.metrics.thinking_pattern_usage}")
        lines.append(f"- **Thinking Quality Score**: {self.metrics.thinking_quality_score}/100")

        # Delegation breakdown
        delegation_by_type = self.metrics.delegation_by_type
        if any(count > 0 for count in delegation_by_type.values()):
            delegation_summary = ", ".join(
                [f"{k}: {v}" for k, v in delegation_by_type.items() if v > 0]
            )
            lines.append(f"- **Delegation by Type**: {delegation_summary}")

        return lines

    def _format_tool_call_statistics(self) -> list[str]:
        """Format tool call statistics for the report.

        Returns:
            List of formatted tool call statistic lines.
        """
        lines = []
        tools = self.metrics.tools

        # Basic tool call counts
        lines.append(f"- **Total Tool Calls**: {tools.total_tool_calls}")
        lines.append(f"- **Successful Tool Calls**: {tools.successful_tool_calls}")
        lines.append(f"- **Failed Tool Calls**: {tools.failed_tool_calls}")

        # Tool calls by category
        tool_counts = tools.get_tool_call_counts_by_category()
        for category, count in tool_counts.items():
            if count > 0:  # Only show categories with actual usage
                # Convert enum value to readable string (e.g., "read_file" -> "Read File")
                readable_name = category.value.replace("_", " ").title()
                lines.append(f"- **{readable_name} Calls**: {count}")

        return lines

    def _format_task_completion_time(self) -> str:
        """Format task completion time for the report."""
        start_time = self.metrics.performance.task_start_time
        end_time = self.metrics.performance.task_end_time

        if start_time and end_time:
            duration = end_time - start_time
            start_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time))
            end_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_time))
            return (
                f"- **Task Completion Time**: {start_str} to {end_str} = "
                f"{duration:.2f}s ({duration / 60:.2f}min)"
            )
        return "- **Task Completion Time**: Not completed yet"

    def _format_files_accessed(self) -> str:
        """Format files accessed information for the report."""
        files_accessed = self.metrics.performance.files_accessed
        total_files = len(files_accessed)
        total_accesses = sum(files_accessed.values())
        return f"- **Files Accessed**: {total_files} files, {total_accesses} total accesses"

    def _format_tool_usage(self) -> str:
        """Format tool usage information for the report."""
        tool_usage = self.metrics.performance.tool_usage_by_type
        if tool_usage:
            tool_summary = ", ".join(
                [
                    f"{k}: {v}"
                    for k, v in sorted(tool_usage.items(), key=lambda x: x[1], reverse=True)[:MAX_TOOL_USAGE_TO_DISPLAY]
                ]
            )
            return f"- **Tool Usage**: {tool_summary}"
        return "- **Tool Usage**: No tools used yet"

    def _format_delegation_rate(self) -> str:
        """Format delegation rate for the report."""
        delegation_count = self.metrics.delegation_count
        total_tasks = self.metrics.tools.total_tool_calls + delegation_count
        delegation_rate = self.metrics.performance.delegation_rate
        return f"- **Delegation Rate**: {delegation_count}/{total_tasks} = {delegation_rate:.1f}%"

    def _format_test_results(self) -> str:
        """Format test results for the report."""
        test_results = self.metrics.quality.test_results
        if test_results["total"] > 0:
            return (
                f"- **Test Results**: {test_results['passing']}/{test_results['total']} = "
                f"{test_results['percentage']:.1f}%"
            )
        return "- **Test Results**: No tests run"

    def _format_code_coverage(self) -> str:
        """Format code coverage for the report."""
        code_coverage = self.metrics.quality.code_coverage
        if code_coverage > 0:
            return f"- **Code Coverage**: {code_coverage:.1f}%"
        return "- **Code Coverage**: Not measured"

    def _format_linting_status(self) -> str:
        """Format linting status for the report."""
        linting = self.metrics.quality.linting_status
        return f"- **Linting Status**: {linting['errors']} errors, {linting['warnings']} warnings"

    def _format_documentation_coverage(self) -> str:
        """Format documentation coverage for the report."""
        doc_coverage = self.metrics.quality.documentation_coverage
        if doc_coverage > 0:
            return f"- **Documentation Coverage**: {doc_coverage:.1f}%"
        return "- **Documentation Coverage**: Not measured"

    def _format_file_re_reads(self) -> str:
        """Format file re-reads with target comparison."""
        file_re_reads = self.metrics.performance.file_re_reads
        target = PerformanceMetrics.FILE_RE_READS_TARGET
        return (
            f"- **File re-reads per task**: {file_re_reads} "
            f"(Target < {target}, 60% reduction from {PerformanceMetrics.FILE_RE_READS_BASELINE})"
        )

    def _format_delegation_target(self) -> str:
        """Format delegation rate with target comparison."""
        delegation_rate = self.metrics.performance.delegation_rate
        target = PerformanceMetrics.DELEGATION_RATE_TARGET
        status = "✅" if delegation_rate >= target else "⚠️"
        return (
            f"- **Delegation rate**: {delegation_rate:.1f}% {status} "
            f"(Target > {target}%, from current 25%)"
        )

    def _format_error_rate_target(self) -> str:
        """Format error rate with target comparison."""
        error_rate = self.metrics.performance.error_rate
        target = PerformanceMetrics.ERROR_RATE_TARGET
        status = "✅" if error_rate <= target else "⚠️"
        return f"- **Error rate**: {error_rate:.1f}% {status} (Target reduction of {target}%)"

    def _format_context_window_target(self) -> str:
        """Format context window usage with target comparison."""
        context_usage = self.metrics.performance.context_window_usage
        target = PerformanceMetrics.CONTEXT_WINDOW_TARGET
        status = "✅" if context_usage <= target else "⚠️"
        return (
            f"- **Context window usage**: {context_usage:.1f}% {status} "
            f"(Target < {target}%, from 65%)"
        )

    def get_pool(self) -> AgentPool:
        """Get the agent pool."""
        return self.pool

    def get_event_bus(self) -> EventBus:
        """Get the event bus."""
        return self.event_bus
