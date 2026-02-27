"""Delegation execution for the orchestrator."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol

from henchman.core.events import AgentEvent, EventType

if TYPE_CHECKING:
    from henchman.agents.ledger import TaskLedger
    from henchman.agents.orchestrator import (
        AgentLoopParams,
        CompletionStatus,
        DelegationParams,
        OrchestratorMetrics,
    )
    from henchman.agents.pool import AgentPool
    from henchman.config.schema import Settings
    from henchman.core.agent import Agent

# Constants re-exported from orchestrator for delegation logic.
RECENT_CONTEXT_ENTRIES = 5
"""Number of recent shared-context entries to include in handoffs."""

MAX_SUMMARY_LENGTH = 200
"""Maximum length for summary text in handoff notes."""

RECENT_ERRORS_TO_SHOW = 10
"""Number of recent tool errors to show in delegation summaries."""

MAX_CONTENT_LENGTH = 800
"""Maximum length for shared-context summary entries."""


class AgentLoopRunner(Protocol):
    """Protocol for the agent loop callback."""

    def __call__(self, params: AgentLoopParams) -> AsyncIterator[AgentEvent]:
        """Run the agent loop.

        Args:
            params: Agent loop parameters.

        Yields:
            AgentEvents from the loop.
        """
        ...  # pragma: no cover


class DelegationRunner:
    """Executes delegations from the orchestrator to specialist agents.

    This class encapsulates the delegation workflow that was previously
    spread across 12 methods in the Orchestrator class.

    Args:
        pool: Agent pool for resolving target agents.
        settings: Application settings (max depth, max turns).
        shared_context: Shared mutable context list.
        metrics: Metrics instance for delegation counting.
        run_agent_loop: Callback to run the core agent loop.
        assess_completion: Callback to assess agent completion status.
    """

    def __init__(
        self,
        pool: AgentPool,
        settings: Settings,
        shared_context: list[dict[str, Any]],
        metrics: OrchestratorMetrics,
        run_agent_loop: AgentLoopRunner,
        assess_completion: Callable[[Agent], CompletionStatus],
    ) -> None:
        self.pool = pool
        self.settings = settings
        self.shared_context = shared_context
        self.metrics = metrics
        self._run_agent_loop = run_agent_loop
        self._assess_completion = assess_completion
        self.ledger: TaskLedger | None = None

    # -- Main entry point -----------------------------------------------------

    async def run_delegation(
        self,
        params: DelegationParams,
    ) -> AsyncIterator[AgentEvent]:
        """Execute a delegation to a specialist agent.

        Each specialist starts with a **clean context** -- its conversation
        history is cleared before every delegation so it operates from a
        self-contained brief rather than accumulated (and often polluted)
        prior context.

        Args:
            params: Delegation parameters containing target role, task,
                brief, and depth.

        Yields:
            AgentEvents from the specialist agent.
        """
        # Validate delegation depth
        if self._is_delegation_depth_exceeded(params.depth):
            async for event in self._yield_depth_exceeded_error():
                yield event
            return

        # Get target agent with error handling
        target_agent_result = await self._get_target_agent_with_error_handling(params.target_role)
        if isinstance(target_agent_result, AgentEvent):
            yield target_agent_result
            async for event in self._yield_agent_not_found_completion(params.target_role):
                yield event
            return
        params.target_agent = target_agent_result

        # Start delegation
        yield AgentEvent(
            type=EventType.AGENT_STARTED,
            data={"agent": params.target_role},
            source_agent="orchestrator",
        )

        # Prepare and execute delegation
        self._prepare_delegation_execution(params)

        # Execute the agent loop
        async for event in self._execute_delegation_loop(params):
            yield event

        # Finalize delegation
        async for event in self._finalize_delegation(params):
            yield event

    # -- Delegation sub-steps -------------------------------------------------

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
        params: DelegationParams,
    ) -> None:
        """Prepare agent and context for delegation execution.

        Mutates ``params`` in place, setting ``full_task`` and ``msg_start``.

        Args:
            params: Delegation parameters (must have ``target_agent`` set).
        """
        assert params.target_agent is not None
        target_agent = params.target_agent

        # Clean start: wipe prior conversation so the specialist has no
        # stale context from earlier delegations. The system prompt is
        # preserved by clear_history().
        target_agent.clear_history()

        # Prepare context for delegation
        prepared_brief = self._prepare_delegation_context(params.target_role, params.brief)

        # Assemble the full task from the structured brief fields
        params.full_task = self._assemble_delegation_input(
            params.task, prepared_brief, mission=self.ledger.goal if self.ledger else None
        )

        # Record where the agent's messages start so we can extract a clean
        # summary afterwards (content events may be duplicated during streaming).
        params.msg_start = len(target_agent.messages)

    async def _execute_delegation_loop(
        self,
        params: DelegationParams,
    ) -> AsyncIterator[AgentEvent]:
        """Execute the agent loop for delegation.

        Args:
            params: Delegation parameters (must have ``target_agent``,
                ``full_task``, and ``msg_start`` set).

        Yields:
            AgentEvents from the specialist agent.
        """
        from henchman.agents.orchestrator import AgentLoopParams

        max_turns = self.settings.agents.max_delegation_turns
        loop_params = AgentLoopParams(
            agent=params.target_agent,
            input_text=params.full_task,
            depth=params.depth,
            max_turns=max_turns,
            msg_start_index=params.msg_start,
        )
        async for event in self._run_agent_loop(loop_params):
            yield event

    async def _finalize_delegation(
        self,
        params: DelegationParams,
    ) -> AsyncIterator[AgentEvent]:
        """Process delegation results and yield completion event.

        Args:
            params: Delegation parameters (must have ``target_agent``
                and ``msg_start`` set).

        Yields:
            AGENT_COMPLETED event with results.
        """
        assert params.target_agent is not None
        # Process delegation results
        summary, parsed, status = self._process_delegation_results(
            params.target_role, params.target_agent, params.msg_start
        )

        # Update shared context (still tracked for Tech Lead's use, just not
        # injected into specialist prompts)
        self.shared_context.append(
            {
                "agent": params.target_role,
                "summary": summary[:MAX_CONTENT_LENGTH],
                "files_modified": parsed.get("files_modified", ""),
                "timestamp": datetime.now().isoformat(),
            }
        )

        yield AgentEvent(
            type=EventType.AGENT_COMPLETED,
            data={
                "agent": params.target_role,
                "summary": summary,
                "status": status.value,
                **parsed,
            },
            source_agent="orchestrator",
        )

    # -- Context preparation --------------------------------------------------

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

    # -- Result processing ----------------------------------------------------

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

    # -- Static helpers -------------------------------------------------------

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
