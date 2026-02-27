"""Delegation manager for handling agent task delegation.

This module extracts delegation-related functionality from the Orchestrator
class to address the Large Class code smell and improve separation of concerns.
"""

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from henchman.agents.ledger import TaskLedger
from henchman.agents.pool import AgentPool
from henchman.config.schema import Settings
from henchman.core.agent import Agent
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import Message, ToolCall


class DelegationManager:
    """Manages delegation of tasks to specialist agents.

    This class handles all delegation-related logic extracted from the
    Orchestrator class to improve maintainability and separation of concerns.
    """

    def __init__(
        self,
        pool: AgentPool,
        settings: Settings,
        shared_context: list[dict[str, Any]],
        ledger: TaskLedger | None = None,
    ) -> None:
        """Initialize the delegation manager.

        Args:
            pool: Agent pool for accessing specialist agents.
            settings: Application settings for delegation configuration.
            shared_context: Shared context history for cross-delegation handoff notes.
            ledger: Optional task ledger for tracking delegation records.
        """
        self.pool = pool
        self.settings = settings
        self._shared_context = shared_context
        self.ledger = ledger

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

    def _prepare_delegation_context(
        self, target_role: str, brief: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Prepare context for delegation by adding handoff notes and failure context.

        Args:
            target_role: The role of the agent being delegated to.
            brief: Optional structured delegation brief.

        Returns:
            Updated delegation context.
        """
        context = brief.copy() if brief else {}

        # Add cross-delegation handoff notes from shared context
        if self._shared_context:
            recent_entries = self._shared_context[-5:]  # Show last 5 entries
            handoff_lines = []
            for entry in recent_entries:
                summary = entry.get("summary", "No summary")
                handoff_lines.append(f"- **{entry.get('agent', 'unknown')}**: {summary[:200]}")
            if handoff_lines:
                handoff_notes = "### Prior agent work\n" + "\n".join(handoff_lines)
                existing_bg = context.get("background")
                if existing_bg:
                    context["background"] = f"{existing_bg}\n\n{handoff_notes}"
                else:
                    context["background"] = handoff_notes

        # Add recent tool errors if any exist in shared context
        recent_errors = [
            entry.get("error", "")
            for entry in self._shared_context
            if entry.get("type") == "tool_error"
        ]
        if recent_errors:
            error_digest = "\n".join(f"- {err[:200]}" for err in recent_errors[-5:])
            if "context" not in context:
                context["context"] = ""
            context["context"] += f"\n\n## Recent tool errors to avoid:\n{error_digest}"

        return context

    @staticmethod
    def _assemble_delegation_input(
        task: str, brief: dict[str, Any] | None, mission: str | None
    ) -> str:
        """Build a self-contained input string from the structured delegation brief.

        Args:
            task: The task description.
            brief: Structured delegation brief.
            mission: Optional mission statement.

        Returns:
            Complete delegation input string.
        """
        parts = []

        # Mission statement (if provided)
        if mission:
            parts.append(f"## Mission\n{mission}\n")

        # Task description
        parts.append(f"## Task\n{task}\n")

        # Done-when condition
        if brief and brief.get("done_when"):
            parts.append(f"## Done When\n{brief['done_when']}\n")

        # Context
        if brief and brief.get("context"):
            parts.append(f"## Context\n{brief['context']}\n")

        # Files to work with
        if brief and brief.get("files"):
            files_list = "\n".join(f"- {f}" for f in brief["files"])
            parts.append(f"## Files\n{files_list}\n")

        # Background
        if brief and brief.get("background"):
            parts.append(f"## Background\n{brief['background']}\n")

        # Requirements
        if brief and brief.get("requirements"):
            parts.append(f"## Requirements\n{brief['requirements']}\n")

        # Dependencies
        if brief and brief.get("depends_on"):
            parts.append(f"## Depends On\n{brief['depends_on']}\n")

        return "\n".join(parts)

    @staticmethod
    def _parse_completion_report(summary: str) -> dict[str, str]:
        """Extract structured fields from a specialist's completion report.

        Args:
            summary: Completion report text.

        Returns:
            Dictionary with parsed fields.
        """
        parsed: dict[str, str] = {}

        # Look for common section headers
        lines = summary.split("\n")
        current_section = ""
        current_content: list[str] = []

        for line in lines:
            line = line.strip()
            if line.startswith("## "):
                # Save previous section
                if current_section and current_content:
                    parsed[current_section] = "\n".join(current_content).strip()
                # Start new section
                current_section = line[3:].lower().replace(" ", "_")
                current_content = []
            elif current_section:
                current_content.append(line)

        # Save last section
        if current_section and current_content:
            parsed[current_section] = "\n".join(current_content).strip()

        return parsed

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
            Error event followed by completion event.
        """
        yield AgentEvent(
            type=EventType.ERROR,
            data={
                "message": (
                    "Delegation depth limit exceeded. "
                    "Check for infinite delegation loops."
                )
            },
            source_agent="orchestrator",
        )
        yield AgentEvent(
            type=EventType.AGENT_COMPLETED,
            data={
                "agent": "orchestrator",
                "status": "depth_exceeded",
                "summary": "Delegation depth limit exceeded.",
            },
            source_agent="orchestrator",
        )

    async def _get_target_agent_with_error_handling(
        self, target_role: str
    ) -> Agent | AgentEvent:
        """Get target agent with proper error handling.

        Args:
            target_role: Role of the target agent.

        Returns:
            Agent instance or error event.
        """
        try:
            return self.pool.get_agent(target_role)
        except KeyError:
            return AgentEvent(
                type=EventType.ERROR,
                data={
                    "message": f"Agent '{target_role}' not found in pool. "
                    "Check agent configuration."
                },
                source_agent="orchestrator",
            )

    async def _yield_agent_not_found_completion(
        self, target_role: str
    ) -> AsyncIterator[AgentEvent]:
        """Yield completion event for agent not found error.

        Args:
            target_role: Role of the target agent.

        Yields:
            Completion event.
        """
        yield AgentEvent(
            type=EventType.AGENT_COMPLETED,
            data={
                "agent": target_role,
                "status": "not_found",
                "summary": f"Agent '{target_role}' not found.",
            },
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
            target_agent: Target agent instance.
            target_role: Role of the target agent.
            brief: Structured delegation brief.
            task: Task description.

        Returns:
            Tuple of (full_task_input, message_start_index).
        """
        # Clear agent history for fresh context
        target_agent.clear_history()

        # Prepare enhanced context
        enhanced_brief = self._prepare_delegation_context(target_role, brief)

        # Get mission from ledger if available
        mission = None
        if self.ledger and hasattr(self.ledger, 'goal'):
            mission = self.ledger.goal

        # Assemble complete task input
        full_task = self._assemble_delegation_input(task, enhanced_brief, mission)

        # Record starting message index
        msg_start = len(target_agent.messages)

        return full_task, msg_start

    def _process_delegation_results(
        self, target_role: str, target_agent: Agent, msg_start: int
    ) -> tuple[str, dict[str, str], str]:
        """Process delegation results and prepare completion data.

        Args:
            target_role: Role of the target agent.
            target_agent: Target agent instance.
            msg_start: Starting message index.

        Returns:
            Tuple of (summary, parsed_fields, completion_status).
        """
        # Build summary from agent's work
        summary = self._build_timeout_summary(target_agent, msg_start)

        # Parse structured completion report
        parsed = self._parse_completion_report(summary)

        # Determine completion status
        assistant_messages = [
            m for m in target_agent.messages[msg_start:] if m.role == "assistant"
        ]
        if not assistant_messages:
            status = "no_work_done"
        else:
            last_assistant = assistant_messages[-1]
            status = "completed" if last_assistant.tool_calls else "no_work_done"

        return summary, parsed, status

    @staticmethod
    def _build_timeout_summary(agent: Agent, msg_start: int) -> str:
        """Build a progress summary from the agent's work so far.

        Args:
            agent: The agent to summarize.
            msg_start: Starting message index.

        Returns:
            Progress summary text.
        """
        messages = agent.messages[msg_start:]
        if not messages:
            return "No work performed."

        # Collect assistant messages and tool calls
        assistant_content: list[str] = []
        tool_calls: list[str] = []

        for msg in messages:
            if msg.role == "assistant":
                if msg.content:
                    assistant_content.append(msg.content)
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_calls.append(f"- {tc.name}: {tc.arguments}")

        # Build summary
        parts = []
        if assistant_content:
            parts.append("## Work Performed")
            parts.extend(assistant_content[-3:])  # Last 3 assistant messages

        if tool_calls:
            parts.append("## Tools Used")
            parts.extend(tool_calls[-10:])  # Last 10 tool calls

        return "\n\n".join(parts)

    async def run_delegation(
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

        Args:
            target_role: The role ID of the specialist.
            task: The task description.
            brief: Structured delegation brief.
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
            type=EventType.AGENT_STARTED,
            data={"agent": target_role},
            source_agent="orchestrator",
        )

        # Prepare and execute delegation
        full_task, msg_start = self._prepare_delegation_execution(
            target_agent, target_role, brief, task
        )

        # Execute the agent loop
        async for event in target_agent.run(full_task):
            yield event

        # Check for stall failure
        if getattr(target_agent, "_stall_failure", False):
            role_label = target_agent.identity.role if target_agent.identity else "agent"
            stall_nudge_count = getattr(target_agent, "_stall_nudge_count", 0)
            fail_msg = (
                f"STALL FAILURE: {role_label} announced intent but "
                f"never used tools after {stall_nudge_count} nudges. "
                f"The task was NOT completed."
            )
            # Add failure message to agent's history (matching original behavior)
            target_agent.messages.append(Message(role="assistant", content=fail_msg))
            yield AgentEvent(
                type=EventType.ERROR,
                data=fail_msg,
                source_agent=role_label,
            )

        # Finalize delegation
        async for event in self._finalize_delegation(target_role, target_agent, msg_start):
            yield event

    async def _finalize_delegation(
        self, target_role: str, target_agent: Agent, msg_start: int
    ) -> AsyncIterator[AgentEvent]:
        """Process delegation results and yield completion event.

        Args:
            target_role: Role of the target agent.
            target_agent: Target agent instance.
            msg_start: Starting message index.

        Yields:
            Completion event.
        """
        summary, parsed, status = self._process_delegation_results(
            target_role, target_agent, msg_start
        )

        # Record in shared context
        self._shared_context.append(
            {
                "agent": target_role,
                "summary": summary[:500] if summary else "",
                "status": status,
                "timestamp": datetime.now().isoformat(),
            }
        )

        # Record in ledger if available
        if self.ledger:
            # Note: TaskLedger doesn't have record_completion method
            # This appears to be dead code or needs implementation
            # For now, we'll comment it out to fix the type error
            # self.ledger.record_completion(
            #     agent=target_role,
            #     status=status,
            #     summary=summary[:500] if summary else "",
            #     parsed_fields=parsed,
            # )
            pass

        yield AgentEvent(
            type=EventType.AGENT_COMPLETED,
            data={
                "agent": target_role,
                "status": status,
                "summary": summary,
                **parsed,
            },
            source_agent="orchestrator",
        )
