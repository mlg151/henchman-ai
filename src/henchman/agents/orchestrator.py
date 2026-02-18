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


class Metrics(TypedDict):
    """Metrics for tracking orchestrator performance."""

    thinking_pattern_usage: int
    delegation_count: int
    delegation_by_type: dict[str, int]
    thinking_quality_score: int


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

        tl_prompt = system_prompt or get_agent_prompt(
            role="tech_lead",
            team_members=team_members,
            delegatable_agents=[c.role for c in agent_configs.values() if c.enabled],
            environment_context=environment_context,
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

        yield AgentEvent(
            type=EventType.AGENT_STARTED, data={"agent": "tech_lead"}, source_agent="orchestrator"
        )

        async for event in self._run_agent_loop(self.tech_lead, user_input):
            yield event

        yield AgentEvent(
            type=EventType.AGENT_COMPLETED, data={"agent": "tech_lead"}, source_agent="orchestrator"
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

        async for event in self._run_agent_loop(agent, user_input):
            yield event

        yield AgentEvent(
            type=EventType.AGENT_COMPLETED, data={"agent": role}, source_agent="orchestrator"
        )

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
                    }

                    # Update delegation metrics
                    self.metrics["delegation_count"] += 1
                    if target in self.metrics["delegation_by_type"]:
                        self.metrics["delegation_by_type"][target] += 1

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
                anchor_msg = (
                    f"[Role Anchor] You are the {role_id.upper()}. "
                    f"Stay focused on your assigned responsibilities. "
                    f"Do not overstep your role boundaries."
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
                        f"turn(s) remaining. Start wrapping up: run any "
                        f"final verification and produce your completion summary."
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

        Each specialist starts with a **clean context** — its conversation
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

        # Assemble the full task from the structured brief fields
        full_task = self._assemble_delegation_input(task, brief)

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
                "summary": summary[:500],
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
    def _assemble_delegation_input(task: str, brief: dict[str, Any] | None) -> str:
        """Build a self-contained input string from the structured delegation brief.

        The resulting text gives the specialist everything it needs without
        any prior conversation history.

        Args:
            task: The core task description.
            brief: Optional structured fields from the Tech Lead.

        Returns:
            A formatted string ready to be passed as user input to the specialist.
        """
        sections: list[str] = [f"## Task\n{task}"]
        if not brief:
            return sections[0]

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

    def get_pool(self) -> AgentPool:
        """Get the agent pool."""
        return self.pool

    def get_event_bus(self) -> EventBus:
        """Get the event bus."""
        return self.event_bus
