"""Orchestrator for multi-agent development team."""

import re
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, TypedDict

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


class Metrics(TypedDict, total=False):
    """Metrics for tracking orchestrator performance."""

    # Existing metrics (for backward compatibility)
    thinking_pattern_usage: int
    delegation_count: int
    delegation_by_type: dict[str, int]
    thinking_quality_score: int
    # Performance metrics from Performance Improvement Plan
    task_start_time: float  # Unix timestamp when task started
    task_end_time: float  # Unix timestamp when task completed
    task_duration_minutes: float  # Task duration in minutes
    files_accessed: dict[str, int]  # file path -> access count
    tool_usage_by_type: dict[str, int]  # tool name -> usage count
    delegation_rate: float  # percentage of tasks delegated

    # Quality metrics
    test_results: dict[str, Any]  # passing, total, percentage
    code_coverage: float  # percentage coverage
    linting_status: dict[str, int]  # errors, warnings counts
    documentation_coverage: float  # percentage documented

    # Target performance metrics
    file_re_reads: int  # count of file re-reads
    error_rate: float  # percentage of errors
    context_window_usage: float  # percentage of context window used

    # Additional tracking
    total_tool_calls: int
    successful_tool_calls: int
    failed_tool_calls: int
    read_file_calls: int
    write_file_calls: int
    edit_file_calls: int
    shell_calls: int
    git_ops_calls: int
    other_tool_calls: int


# Interval (in tool calls) at which role anchoring reminders are injected
_ROLE_ANCHOR_INTERVAL = 8

# How many turns before the limit to inject a wrap-up warning
_WRAPUP_WARNING_OFFSET = 3


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
        self.default_provider = default_provider
        self.provider_registry = provider_registry
        self.tool_registry = tool_registry or ToolRegistry()
        self.event_bus = event_bus or EventBus()
        self.settings = settings or Settings()
        self.environment_context = environment_context

        # Thinking and delegation metrics
        self.metrics: Metrics = {
            "thinking_pattern_usage": 0,
            "delegation_count": 0,
            "delegation_by_type": {"planner": 0, "explorer": 0, "engineer": 0},
            "thinking_quality_score": 0,  # Simple heuristic based on structure

            # Efficiency metrics
            "task_start_time": 0.0,
            "task_end_time": 0.0,
            "files_accessed": {},
            "tool_usage_by_type": {},
            "delegation_rate": 0.0,

            # Quality metrics
            "test_results": {"passing": 0, "total": 0, "percentage": 0.0},
            "code_coverage": 0.0,
            "linting_status": {"errors": 0, "warnings": 0},
            "documentation_coverage": 0.0,

            # Target performance metrics
            "file_re_reads": 0,
            "error_rate": 0.0,
            "context_window_usage": 0.0,

            # Additional tracking
            "total_tool_calls": 0,
            "successful_tool_calls": 0,
            "failed_tool_calls": 0,
            "read_file_calls": 0,
            "write_file_calls": 0,
            "edit_file_calls": 0,
            "shell_calls": 0,
            "git_ops_calls": 0,
            "other_tool_calls": 0,
        }

        # Load agent configs
        agent_configs = get_default_team()
        if self.settings.agents.agents:
            # Merge custom configs/overrides
            for role, config in self.settings.agents.agents.items():
                agent_configs[role] = config

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

        # Shared context history
        self.shared_context: list[dict[str, Any]] = []

        # Task ledger – created per run() call
        self.ledger: TaskLedger | None = None

        # Create Tech Lead agent
        # Tech Lead uses the parent tool_registry directly (not a copy)
        # so that tools added later (MCP, extensions, tests) are visible.
        # DelegateTaskTool is registered on the parent;
        # delegated agents won't see it because create_scoped_registry
        # filters by each agent's allowed_tools list.
        if not self.tool_registry.get("delegate_task"):
            self.tool_registry.register(DelegateTaskTool())

        from henchman.agents.prompts import get_agent_prompt

        team_members = [f"{c.name} ({c.role})" for c in agent_configs.values() if c.enabled]

        team_descriptions = {
            c.role: c.description or ""
            for c in agent_configs.values()
            if c.enabled
        }
        tl_prompt = system_prompt or get_agent_prompt(
            role="tech_lead",
            team_members=team_members,
            delegatable_agents=[c.role for c in agent_configs.values() if c.enabled],
            environment_context=environment_context,
            team_descriptions=team_descriptions,
        )

        from henchman.agents.identity import AgentIdentity

        tl_identity = AgentIdentity(
            id="tech_lead",
            name="Leader",
            role="tech_lead",
            description="Architect, implementer, and quality gate",
        )

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
        # Tech Lead legitimately narrates plans before delegating —
        # disable stall detection so it isn't killed for planning.
        self.tech_lead.stall_detection_enabled = False

    async def run(self, user_input: str) -> AsyncIterator[AgentEvent]:
        """Run the orchestrator with user input.

        Args:
            user_input: The user's request.

        Yields:
            AgentEvent stream from the orchestration.
        """
        # Initialize a fresh task ledger for this request
        self.ledger = TaskLedger(goal=user_input[:500])

        # Reset metrics for this run
        self._reset_metrics_for_run()

        # Set task start time
        import time
        self.metrics["task_start_time"] = time.time()

        yield AgentEvent(
            type=EventType.AGENT_STARTED, data={"agent": "tech_lead"}, source_agent="orchestrator"
        )

        event_count = 0
        async for event in self._run_agent_loop(self.tech_lead, user_input):
            event_count += 1
            yield event

        # Set task end time and calculate duration
        self.metrics["task_end_time"] = time.time()

        # Calculate final metrics
        self._calculate_final_metrics()

        yield AgentEvent(
            type=EventType.AGENT_COMPLETED, data={"agent": "tech_lead"}, source_agent="orchestrator"
        )

    def _reset_metrics_for_run(self) -> None:
        """Reset metrics for a new run while preserving structure."""

        # Reset counters but keep structure
        self.metrics["thinking_pattern_usage"] = 0
        self.metrics["delegation_count"] = 0
        self.metrics["delegation_by_type"] = {"planner": 0, "explorer": 0, "engineer": 0}
        self.metrics["thinking_quality_score"] = 0

        # Efficiency metrics
        self.metrics["task_start_time"] = 0.0
        self.metrics["task_end_time"] = 0.0
        self.metrics["task_duration_minutes"] = 0.0
        self.metrics["files_accessed"] = {}
        self.metrics["tool_usage_by_type"] = {}
        self.metrics["delegation_rate"] = 0.0

        # Quality metrics
        self.metrics["test_results"] = {"passing": 0, "total": 0, "percentage": 0.0}
        self.metrics["code_coverage"] = 0.0
        self.metrics["linting_status"] = {"errors": 0, "warnings": 0}
        self.metrics["documentation_coverage"] = 0.0

        # Target performance metrics
        self.metrics["file_re_reads"] = 0
        self.metrics["error_rate"] = 0.0
        self.metrics["context_window_usage"] = 0.0

        # Additional tracking
        self.metrics["total_tool_calls"] = 0
        self.metrics["successful_tool_calls"] = 0
        self.metrics["failed_tool_calls"] = 0
        self.metrics["read_file_calls"] = 0
        self.metrics["write_file_calls"] = 0
        self.metrics["edit_file_calls"] = 0
        self.metrics["shell_calls"] = 0
        self.metrics["git_ops_calls"] = 0
        self.metrics["other_tool_calls"] = 0

    def _calculate_final_metrics(self) -> None:
        """Calculate derived metrics after task completion."""

        # Calculate task duration
        if self.metrics["task_start_time"] and self.metrics["task_end_time"]:
            duration = self.metrics["task_end_time"] - self.metrics["task_start_time"]
            # Store duration in minutes for readability
            self.metrics["task_duration_minutes"] = duration / 60.0

        # Calculate delegation rate
        total_tasks = self.metrics["total_tool_calls"] + self.metrics["delegation_count"]
        if total_tasks > 0:
            self.metrics["delegation_rate"] = (
                self.metrics["delegation_count"] / total_tasks * 100.0
            )

        # Calculate error rate
        if self.metrics["total_tool_calls"] > 0:
            self.metrics["error_rate"] = (
                self.metrics["failed_tool_calls"] / self.metrics["total_tool_calls"] * 100.0
            )

        # Calculate test results percentage
        if self.metrics["test_results"]["total"] > 0:
            self.metrics["test_results"]["percentage"] = (
                self.metrics["test_results"]["passing"] /
                self.metrics["test_results"]["total"] * 100.0
            )

        # Calculate file re-reads
        if self.metrics["files_accessed"]:
            total_accesses = sum(self.metrics["files_accessed"].values())
            unique_files = len(self.metrics["files_accessed"])
            if unique_files > 0:
                self.metrics["file_re_reads"] = total_accesses - unique_files

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

        async for event in self._run_agent_loop(agent, user_input):
            yield event

        yield AgentEvent(
            type=EventType.AGENT_COMPLETED, data={"agent": role}, source_agent="orchestrator"
        )

    def _update_tool_metrics(self, tool_name: str, arguments: dict[str, Any], success: bool) -> None:
        """Update metrics for a tool call.

        Args:
            tool_name: Name of the tool called.
            arguments: Arguments passed to the tool.
            success: Whether the tool call was successful.
        """
        # Update total tool calls
        self.metrics["total_tool_calls"] += 1

        # Update success/failure counts
        if success:
            self.metrics["successful_tool_calls"] += 1
        else:
            self.metrics["failed_tool_calls"] += 1

        # Update tool usage by type
        if tool_name in self.metrics["tool_usage_by_type"]:
            self.metrics["tool_usage_by_type"][tool_name] += 1
        else:
            self.metrics["tool_usage_by_type"][tool_name] = 1

        # Update specific tool type counters
        if tool_name == "read_file":
            self.metrics["read_file_calls"] += 1
            # Track file access for re-read calculation
            path = arguments.get("path")
            if path:
                if path in self.metrics["files_accessed"]:
                    self.metrics["files_accessed"][path] += 1
                else:
                    self.metrics["files_accessed"][path] = 1
        elif tool_name == "write_file":
            self.metrics["write_file_calls"] += 1
            path = arguments.get("path")
            if path:
                if path in self.metrics["files_accessed"]:
                    self.metrics["files_accessed"][path] += 1
                else:
                    self.metrics["files_accessed"][path] = 1
        elif tool_name == "edit_file":
            self.metrics["edit_file_calls"] += 1
            path = arguments.get("path")
            if path:
                if path in self.metrics["files_accessed"]:
                    self.metrics["files_accessed"][path] += 1
                else:
                    self.metrics["files_accessed"][path] = 1
        elif tool_name == "shell":
            self.metrics["shell_calls"] += 1
        elif tool_name == "git_ops":
            self.metrics["git_ops_calls"] += 1
        else:
            self.metrics["other_tool_calls"] += 1

    async def _run_agent_loop(
        self,
        agent: Agent,
        user_input: str,
        depth: int = 0,
        max_turns: int = 0,
        msg_start_index: int = 0,
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
            agent: The agent to run.
            user_input: Initial input for the agent.
            depth: Current delegation depth.
            max_turns: Maximum tool-call turns (0 = unlimited).
            msg_start_index: Index into agent.messages where this run began
                (used to build a progress summary on timeout).

        Yields:
            AgentEvents from the agent loop.
        """
        generator: AsyncIterator[AgentEvent] = agent.run(user_input)
        tool_call_count = 0
        tool_errors: list[str] = []
        wrapup_warned = False

        while True:
            # Drain the current generator, collecting tool calls
            pending_tool_calls: list[ToolCall] = []

            try:
                async for event in generator:
                    if event.type == EventType.TOOL_CALL_REQUEST:
                        pending_tool_calls.append(event.data)
                        # Yield for UI display
                        yield event
                    else:
                        yield event
            except StopAsyncIteration:
                pass

            if not pending_tool_calls:
                # Thinking pattern validation for Tech Lead
                # Only check when the agent is NOT making tool calls, because
                # injecting a user message when tool_calls are pending would
                # break the assistant→tool message sequence required by the
                # OpenAI API (the injected message lands between the assistant
                # with tool_calls and the tool response messages, causing
                # repeated repair_message_sequence cycles).
                if agent is self.tech_lead and agent.messages:
                    last_message = agent.messages[-1]
                    if last_message.role == "assistant":
                        content = last_message.content or ""
                        if content.strip().startswith("THINKING:"):
                            self.metrics["thinking_pattern_usage"] += 1
                            lines = content.strip().split("\n")
                            thinking_lines = [
                                line
                                for line in lines
                                if line.strip().startswith(("1.", "2.", "3.", "4.", "5."))
                            ]
                            if len(thinking_lines) >= 3:
                                self.metrics["thinking_quality_score"] = min(
                                    100, self.metrics["thinking_quality_score"] + 5
                                )
                        elif content.strip():
                            thinking_reminder = (
                                "\n[Thinking Required] Your response must start with THINKING: "
                                "followed by your reasoning process. Please revise."
                            )
                            agent.messages.append(
                                Message(role="user", content=thinking_reminder)
                            )
                            yield AgentEvent(
                                type=EventType.THINKING_REQUIRED,
                                data="Thinking pattern missing in Tech Lead response",
                                source_agent="orchestrator",
                            )
                # Check if the agent's built-in stall detection exhausted
                # its nudge budget.  Only report for specialists — the Tech
                # Lead legitimately narrates plans.
                if agent is not self.tech_lead and agent._stall_failure:
                    role_label = agent.identity.role if agent.identity else "agent"
                    fail_msg = (
                        f"STALL FAILURE: {role_label} announced intent but "
                        f"never used tools after "
                        f"{agent._stall_nudge_count} nudges. "
                        f"The task was NOT completed."
                    )
                    agent.messages.append(Message(role="assistant", content=fail_msg))
                    yield AgentEvent(
                        type=EventType.ERROR,
                        data=fail_msg,
                        source_agent=role_label,
                    )
                # Agent finished — exit the loop
                break

            # Process all pending tool calls: execute regular tools,
            # intercept delegate_task for sub-agent routing.
            for tool_call in pending_tool_calls:
                tool_call_count += 1

                if tool_call.name == "delegate_task":
                    target = tool_call.arguments.get("agent", "")
                    task = tool_call.arguments.get("task", "")
                    # Extract structured delegation fields (incl. done_when)
                    delegation_brief: dict[str, Any] = {
                        "done_when": tool_call.arguments.get("done_when"),
                        "context": tool_call.arguments.get("context"),
                        "files": tool_call.arguments.get("files"),
                        "background": tool_call.arguments.get("background"),
                        "requirements": tool_call.arguments.get("requirements"),
                        "depends_on": tool_call.arguments.get("depends_on"),
                    }

                    # Update delegation metrics
                    self.metrics["delegation_count"] += 1
                    if target in self.metrics["delegation_by_type"]:
                        self.metrics["delegation_by_type"][target] += 1

                    # Also track as a tool call
                    self._update_tool_metrics("delegate_task", tool_call.arguments, True)

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
                    async for sub_event in self._run_delegation(
                        target, task, delegation_brief, depth + 1
                    ):
                        if sub_event.type == EventType.AGENT_COMPLETED:
                            result_content = sub_event.data.get("summary", "Completed.")
                        if sub_event.type == EventType.ERROR:
                            delegation_had_error = True
                        yield sub_event

                    if not result_content:
                        result_content = "Delegation completed (no output)."

                    # Update ledger with outcome
                    if self.ledger and ledger_record:
                        if delegation_had_error:
                            self.ledger.fail_delegation(ledger_record, result_content)
                        else:
                            self.ledger.complete_delegation(ledger_record, result_content)

                    # Append ledger snapshot so Tech Lead can re-orient
                    # (Task 9: Mission Recapitulation included in render)
                    submitted_content = result_content
                    if self.ledger:
                        submitted_content = f"{result_content}\n\n{self.ledger.render()}"

                    agent.submit_tool_result(tool_call.id, submitted_content)

                    yield AgentEvent(
                        type=EventType.TOOL_CALL_RESULT,
                        data={
                            "tool_call_id": tool_call.id,
                            "tool_name": "delegate_task",
                            "result": (result_content or "")[:500],
                            "success": True,
                        },
                        source_agent=agent.identity.id if agent.identity else None,
                    )
                else:
                    # Execute regular tool via the agent's own (scoped) registry
                    result = await agent.tool_registry.execute(tool_call.name, tool_call.arguments)
                    agent.submit_tool_result(tool_call.id, result.content or "")

                    # Track tool errors for delegation summaries
                    if not result.success:
                        tool_errors.append(
                            f"{tool_call.name}: {(result.content or 'unknown error')[:200]}"
                        )

                    # Update metrics for tool usage
                    self._update_tool_metrics(tool_call.name, tool_call.arguments, result.success)

                    yield AgentEvent(
                        type=EventType.TOOL_CALL_RESULT,
                        data={
                            "tool_call_id": tool_call.id,
                            "tool_name": tool_call.name,
                            "result": (result.content or "")[:500],
                            "success": result.success,
                        },
                        source_agent=agent.identity.id if agent.identity else None,
                    )

            # Task 5: Periodic Role Anchoring — re-inject role reminder
            if (
                tool_call_count > 0
                and tool_call_count % _ROLE_ANCHOR_INTERVAL == 0
                and agent.identity
            ):
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

            # Turn limit enforcement — inject wrap-up warning, then hard stop
            if max_turns > 0:
                remaining = max_turns - tool_call_count
                if remaining <= 0:
                    # Hard stop — build a progress summary from what the
                    # agent accomplished so the Tech Lead can continue
                    # without starting from scratch.
                    progress = self._build_timeout_summary(agent, msg_start_index)
                    timeout_msg = (
                        "[TURN LIMIT REACHED] You have used all available "
                        "turns. Here is a summary of your progress so far:\n\n"
                        f"{progress}\n\n"
                        "The Tech Lead will decide how to proceed."
                    )
                    agent.messages.append(Message(role="assistant", content=timeout_msg))
                    yield AgentEvent(
                        type=EventType.ERROR,
                        data=f"Turn limit ({max_turns}) reached for "
                        f"{agent.identity.role if agent.identity else 'agent'}",
                        source_agent="orchestrator",
                    )
                    break
                if not wrapup_warned and remaining <= _WRAPUP_WARNING_OFFSET:
                    wrapup_warned = True
                    warn_msg = (
                        f"[WRAP-UP WARNING] You have {remaining} tool-call "
                        f"turn(s) remaining. Prioritise:\n"
                        f"1. Run any final verification (tests, lint).\n"
                        f"2. Write a completion report using the "
                        f"DELEGATION_SUMMARY_SCHEMA format.\n"
                        f"3. List BLOCKERS if you cannot finish in time."
                    )
                    agent.messages.append(Message(role="user", content=warn_msg))

            # All tool results submitted — continue the agent
            generator = agent.continue_with_tool_results()

        # Store tool errors on the agent for the caller to retrieve
        if not hasattr(agent, "_delegation_tool_errors"):
            agent._delegation_tool_errors = []  # type: ignore[attr-defined]
        agent._delegation_tool_errors = tool_errors  # type: ignore[attr-defined]

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
        if depth > self.settings.agents.max_delegation_depth:
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
            return

        try:
            target_agent = self.pool.get_agent(target_role)
        except ValueError as e:
            yield AgentEvent(type=EventType.ERROR, data=str(e), source_agent="orchestrator")
            yield AgentEvent(
                type=EventType.AGENT_COMPLETED,
                data={"summary": f"Agent {target_role} not found"},
                source_agent="orchestrator",
            )
            return

        yield AgentEvent(
            type=EventType.AGENT_STARTED, data={"agent": target_role}, source_agent="orchestrator"
        )

        # Clean start: wipe prior conversation so the specialist has no
        # stale context from earlier delegations.  The system prompt is
        # preserved by clear_history().
        target_agent.clear_history()

        # Cross-delegation handoff: auto-inject recent shared_context
        # entries into the brief's background field so the specialist
        # knows what prior agents accomplished.
        brief = dict(brief) if brief else {}
        if self.shared_context:
            handoff_lines = []
            for entry in self.shared_context[-5:]:
                handoff_lines.append(f"- **{entry['agent']}**: {entry['summary'][:200]}")
            handoff_notes = "### Prior agent work\n" + "\n".join(handoff_lines)
            existing_bg = brief.get("background") or ""
            brief["background"] = (
                f"{existing_bg}\n\n{handoff_notes}" if existing_bg else handoff_notes
            )

        # Inject prior failure context if the same role failed before (#17)
        if self.ledger:
            prior_failures = [
                d for d in self.ledger.delegations
                if d.agent == target_role
                and d.status == "FAILED"
            ]
            if prior_failures:
                last_fail = prior_failures[-1]
                fail_note = (
                    f"### Prior Attempt Failed\n"
                    f"A previous delegation to you for "
                    f"\"{last_fail.task}\" ended with status FAILED. "
                    f"Avoid repeating the same approach."
                )
                existing_bg = brief.get("background") if brief else None
                if brief is None:
                    brief = {}
                brief["background"] = (
                    f"{existing_bg}\n\n{fail_note}"
                    if existing_bg
                    else fail_note
                )

        # Assemble the full task from the structured brief fields
        full_task = self._assemble_delegation_input(
            task, brief, mission=self.ledger.goal if self.ledger else None
        )

        # Record where the agent's messages start so we can extract a clean
        # summary afterwards (content events may be duplicated during streaming).
        max_turns = self.settings.agents.max_delegation_turns
        msg_start = len(target_agent.messages)
        async for event in self._run_agent_loop(
            target_agent,
            full_task,
            depth,
            max_turns=max_turns,
            msg_start_index=msg_start,
        ):
            yield event

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
                f"• {e}" for e in tool_errors[-10:]
            )
            summary = f"{summary}\n{error_digest}"

        # Parse structured completion report from specialist output
        parsed = self._parse_completion_report(summary)

        # Update shared context (still tracked for Tech Lead's use, just not
        # injected into specialist prompts)
        self.shared_context.append(
            {
                "agent": target_role,
                "summary": summary[:800],
                "files_modified": parsed.get("files_modified", ""),
                "timestamp": datetime.now().isoformat(),
            }
        )

        yield AgentEvent(
            type=EventType.AGENT_COMPLETED,
            data={
                "agent": target_role,
                "summary": summary,
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
                            f"{tc.name}({', '.join(f'{k}={v!r}' for k, v in list(tc.arguments.items())[:2])})"
                        )
                        # Track file paths from common tools
                        path = tc.arguments.get("path") or tc.arguments.get("file_path")
                        if path and isinstance(path, str):
                            files_touched.add(path)
                if msg.content:
                    narration_parts.append(msg.content[:200])

        lines = ["**Progress at timeout:**"]
        if tools_used:
            lines.append(f"- Tool calls made: {len(tools_used)}")
            # Show last 10 tool calls
            for t in tools_used[-10:]:
                lines.append(f"  • {t[:120]}")
        if files_touched:
            lines.append(f"- Files touched: {', '.join(sorted(files_touched))}")
        if narration_parts:
            lines.append(f"- Last agent output: {narration_parts[-1][:300]}")
        if not tools_used and not narration_parts:
            lines.append("- No significant progress was made.")
        return "\n".join(lines)

    def get_metrics_report(self) -> str:
        """Generate a formatted performance metrics dashboard.

        Returns:
            A formatted markdown string with performance metrics.
        """
        import time

        report_lines = [
            "## Performance Metrics Dashboard",
            "",
            "### Efficiency Metrics",
        ]

        # Task completion time
        if self.metrics.get("task_start_time") and self.metrics.get("task_end_time"):
            duration = self.metrics["task_end_time"] - self.metrics["task_start_time"]
            start_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.metrics["task_start_time"]))
            end_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.metrics["task_end_time"]))
            report_lines.append(f"- **Task Completion Time**: {start_time} to {end_time} = {duration:.2f}s ({duration/60:.2f}min)")
        else:
            report_lines.append("- **Task Completion Time**: Not completed yet")

        # Files accessed
        total_files = len(self.metrics.get("files_accessed", {}))
        total_accesses = sum(self.metrics.get("files_accessed", {}).values())
        report_lines.append(f"- **Files Accessed**: {total_files} files, {total_accesses} total accesses")

        # Tool usage
        tool_usage = self.metrics.get("tool_usage_by_type", {})
        if tool_usage:
            tool_summary = ", ".join([f"{k}: {v}" for k, v in sorted(tool_usage.items(), key=lambda x: x[1], reverse=True)[:5]])
            report_lines.append(f"- **Tool Usage**: {tool_summary}")
        else:
            report_lines.append("- **Tool Usage**: No tools used yet")

        # Delegation rate
        delegation_rate = self.metrics.get("delegation_rate", 0.0)
        # Files accessed
        total_files = len(self.metrics["files_accessed"])
        total_accesses = sum(self.metrics["files_accessed"].values())
        report_lines.append(f"- **Files Accessed**: {total_files} files, {total_accesses} total accesses")

        # Tool usage
        tool_usage = self.metrics["tool_usage_by_type"]
        if tool_usage:
            tool_summary = ", ".join([f"{k}: {v}" for k, v in sorted(tool_usage.items(), key=lambda x: x[1], reverse=True)[:5]])
            report_lines.append(f"- **Tool Usage**: {tool_summary}")
        else:
            report_lines.append("- **Tool Usage**: No tools used yet")

        # Delegation rate
        delegation_rate = self.metrics.get("delegation_rate", 0.0)
        delegation_count = self.metrics.get("delegation_count", 0)
        total_tasks = self.metrics.get("total_tool_calls", 0) + delegation_count
        report_lines.append(f"- **Delegation Rate**: {delegation_count}/{total_tasks} = {delegation_rate:.1f}%")

        report_lines.append("")
        report_lines.append("### Quality Metrics")

        # Test results
        test_results = self.metrics["test_results"]
        if test_results["total"] > 0:
            report_lines.append(f"- **Test Results**: {test_results['passing']}/{test_results['total']} = {test_results['percentage']:.1f}%")
        else:
            report_lines.append("- **Test Results**: No tests run")

        # Code coverage
        code_coverage = self.metrics["code_coverage"]
        if code_coverage > 0:
            report_lines.append(f"- **Code Coverage**: {code_coverage:.1f}%")
        else:
            report_lines.append("- **Code Coverage**: Not measured")

        # Linting status
        linting = self.metrics["linting_status"]
        report_lines.append(f"- **Linting Status**: {linting['errors']} errors, {linting['warnings']} warnings")

        # Documentation coverage
        doc_coverage = self.metrics["documentation_coverage"]
        if doc_coverage > 0:
            report_lines.append(f"- **Documentation Coverage**: {doc_coverage:.1f}%")
        else:
            report_lines.append("- **Documentation Coverage**: Not measured")

        report_lines.append("")
        report_lines.append("### Target Performance Metrics")

        # File re-reads
        file_re_reads = self.metrics["file_re_reads"]
        report_lines.append(f"- **File re-reads per task**: {file_re_reads} (Target < 1.3, 60% reduction from 3.2)")

        # Delegation rate target
        delegation_target = 40.0
        delegation_status = "✅" if delegation_rate >= delegation_target else "⚠️"
        report_lines.append(f"- **Delegation rate**: {delegation_rate:.1f}% {delegation_status} (Target > {delegation_target}%, from current 25%)")

        # Error rate
        error_rate = self.metrics["error_rate"]
        error_target = 50.0  # 50% reduction target
        error_status = "✅" if error_rate <= error_target else "⚠️"
        report_lines.append(f"- **Error rate**: {error_rate:.1f}% {error_status} (Target reduction of {error_target}%)")

        # Context window usage
        context_usage = self.metrics["context_window_usage"]
        context_target = 40.0
        context_status = "✅" if context_usage <= context_target else "⚠️"
        report_lines.append(f"- **Context window usage**: {context_usage:.1f}% {context_status} (Target < {context_target}%, from 65%)")

        report_lines.append("")
        report_lines.append("### Detailed Statistics")

        # Tool call breakdown
        report_lines.append(f"- **Total Tool Calls**: {self.metrics['total_tool_calls']}")
        report_lines.append(f"- **Successful Tool Calls**: {self.metrics['successful_tool_calls']}")
        report_lines.append(f"- **Failed Tool Calls**: {self.metrics['failed_tool_calls']}")
        report_lines.append(f"- **Read File Calls**: {self.metrics['read_file_calls']}")
        report_lines.append(f"- **Write File Calls**: {self.metrics['write_file_calls']}")
        report_lines.append(f"- **Edit File Calls**: {self.metrics['edit_file_calls']}")
        report_lines.append(f"- **Shell Calls**: {self.metrics['shell_calls']}")
        report_lines.append(f"- **Git Ops Calls**: {self.metrics['git_ops_calls']}")
        report_lines.append(f"- **Other Tool Calls**: {self.metrics['other_tool_calls']}")

        # Thinking metrics
        report_lines.append(f"- **Thinking Pattern Usage**: {self.metrics['thinking_pattern_usage']}")
        report_lines.append(f"- **Thinking Quality Score**: {self.metrics['thinking_quality_score']}/100")

        # Delegation breakdown
        delegation_by_type = self.metrics["delegation_by_type"]
        if any(count > 0 for count in delegation_by_type.values()):
            delegation_summary = ", ".join([f"{k}: {v}" for k, v in delegation_by_type.items() if v > 0])
            report_lines.append(f"- **Delegation by Type**: {delegation_summary}")

        return "\n".join(report_lines)

    def get_pool(self) -> AgentPool:
        """Get the agent pool."""
        return self.pool

    def get_event_bus(self) -> EventBus:
        """Get the event bus."""
        return self.event_bus
