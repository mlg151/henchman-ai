"""Orchestrator for multi-agent development team."""

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum
from typing import Any

from henchman.agents.delegation import DelegationRunner
from henchman.agents.ledger import TaskLedger
from henchman.agents.metrics import (
    PERCENTAGE_MULTIPLIER as PERCENTAGE_MULTIPLIER,
)
from henchman.agents.metrics import (
    SECONDS_PER_MINUTE as SECONDS_PER_MINUTE,
)
from henchman.agents.metrics import (
    OrchestratorMetrics as OrchestratorMetrics,
)
from henchman.agents.metrics import (
    PerformanceMetrics as PerformanceMetrics,
)
from henchman.agents.metrics import (
    QualityMetrics as QualityMetrics,
)
from henchman.agents.metrics import (
    ToolCategory as ToolCategory,
)
from henchman.agents.metrics import (
    ToolMetrics as ToolMetrics,
)
from henchman.agents.metrics import (
    _categorize_tool as _categorize_tool,
)
from henchman.agents.metrics_reporter import MetricsReporter
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

    # Fields populated during delegation execution
    target_agent: Agent | None = None
    """Resolved agent instance (set by _run_delegation)."""

    full_task: str = ""
    """Assembled task with context (set by _prepare_delegation_execution)."""

    msg_start: int = 0
    """Starting message index for result extraction (set by _prepare_delegation_execution)."""


MAX_USER_INPUT_LENGTH = 500
"""Maximum length for user input truncation."""

MAX_ERROR_MESSAGE_LENGTH = 200
"""Maximum length for error message truncation."""

MAX_SUMMARY_LENGTH = 200
"""Maximum length for summary text truncation."""

MAX_STALL_NUDGES = 10
"""Maximum number of stall nudges before marking as stalled."""

RECENT_TOOLS_TO_SHOW = 10
"""Number of recent tool calls to show in timeout summaries."""

MAX_TOOL_CALL_DISPLAY_LENGTH = 120
"""Maximum length for displaying tool call names in summaries."""

MAX_NARRATION_DISPLAY_LENGTH = 300
"""Maximum length for displaying narration in timeout summaries."""

MAX_TOOL_ARGUMENTS_TO_DISPLAY = 2
"""Maximum number of tool arguments to show in summaries."""


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
        self._initialize_delegation_runner()

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

        # Reporter for formatted metrics output
        self._reporter = MetricsReporter(self.metrics)

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

    def _initialize_delegation_runner(self) -> None:
        """Initialize the delegation runner with shared state and callbacks."""
        self._delegation_runner = DelegationRunner(
            pool=self.pool,
            settings=self.settings,
            shared_context=self.shared_context,
            metrics=self.metrics,
            run_agent_loop=self._run_agent_loop,
            assess_completion=self._assess_completion,
        )

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
        self._delegation_runner.ledger = self.ledger

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
        params = DelegationParams(
            target_role=target,
            task=task,
            brief=delegation_brief,
            depth=depth + 1,
        )
        async for sub_event in self._run_delegation(params):
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

        Delegates to :class:`DelegationRunner`.

        Args:
            target_role: The role ID of the specialist.
            brief: Original delegation brief.

        Returns:
            Updated brief with handoff notes and failure context added.
        """
        return self._delegation_runner._prepare_delegation_context(target_role, brief)

    def _process_delegation_results(
        self,
        target_role: str,
        target_agent: Agent,
        msg_start: int,
    ) -> tuple[str, dict[str, str], CompletionStatus]:
        """Process delegation results and prepare completion data.

        Delegates to :class:`DelegationRunner`.

        Args:
            target_role: The role ID of the specialist.
            target_agent: The agent that executed the delegation.
            msg_start: Index where the agent's messages started.

        Returns:
            Tuple of (summary, parsed_completion_report, completion_status)
        """
        return self._delegation_runner._process_delegation_results(
            target_role, target_agent, msg_start
        )

    async def _run_delegation(
        self,
        params: DelegationParams,
    ) -> AsyncIterator[AgentEvent]:
        """Execute a delegation to a specialist agent.

        Delegates to :class:`DelegationRunner`.

        Args:
            params: Delegation parameters containing target role, task,
                brief, and depth.

        Yields:
            AgentEvents from the specialist agent.
        """
        async for event in self._delegation_runner.run_delegation(params):
            yield event

    @staticmethod
    def _assemble_delegation_input(
        task: str,
        brief: dict[str, Any] | None,
        mission: str | None = None,
    ) -> str:
        """Build a self-contained input string from the structured delegation brief.

        Delegates to :class:`DelegationRunner`.

        Args:
            task: The core task description.
            brief: Optional structured fields from the Tech Lead.
            mission: Optional high-level mission statement for context.

        Returns:
            A formatted string ready to be passed as user input to the specialist.
        """
        return DelegationRunner._assemble_delegation_input(task, brief, mission)

    @staticmethod
    def _parse_completion_report(summary: str) -> dict[str, str]:
        """Extract structured fields from a specialist's completion report.

        Delegates to :class:`DelegationRunner`.

        Args:
            summary: Raw summary text from the specialist.

        Returns:
            Dict with extracted fields (may be empty if format not found).
        """
        return DelegationRunner._parse_completion_report(summary)

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
        return self._reporter.get_metrics_report()

    def get_pool(self) -> AgentPool:
        """Get the agent pool."""
        return self.pool

    def get_event_bus(self) -> EventBus:
        """Get the event bus."""
        return self.event_bus
