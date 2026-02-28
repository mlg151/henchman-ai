"""Agent execution loop controller for the orchestrator.

Manages turn enforcement, colon-stall detection, and the main agent loop.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import Message

from .orchestrator_components import TimeoutSummaryBuilder
from .orchestrator_types import (
    COLON_STALL_MIN_LENGTH,
    COLON_STALL_NUDGE,
    MAX_COLON_STALL_RETRIES,
    ROLE_ANCHOR_INTERVAL,
    WRAPUP_WARNING_OFFSET,
    AgentLoopParams,
    CompletionStatus,
    LoopState,
)

if TYPE_CHECKING:
    from henchman.core.agent import Agent
    from henchman.providers.base import ToolCall


@dataclass
class TurnEnforcementParams:
    """Parameters for enforcing turn limits.

    Encapsulates parameters for turn limits to address Primitive Obsession.
    """

    agent: Agent
    max_turns: int
    tool_call_count: int
    msg_start_index: int
    wrapup_warned: bool

    def enforce_limits(
        self: TurnEnforcementParams,
    ) -> tuple[bool, bool, AgentEvent | None]:
        """Enforce turn limits with warnings and hard stops.

        Returns:
            Tuple of (should_break, new_wrapup_warned, error_event).
        """
        if self.max_turns <= 0:
            return False, self.wrapup_warned, None

        remaining = self.max_turns - self.tool_call_count

        if remaining <= 0:
            return self._handle_turn_limit_reached()

        if not self.wrapup_warned and remaining <= WRAPUP_WARNING_OFFSET:
            return self._handle_wrapup_warning(remaining)

        return False, self.wrapup_warned, None

    def _handle_turn_limit_reached(
        self: TurnEnforcementParams,
    ) -> tuple[bool, bool, AgentEvent | None]:
        """Handle case when turn limit has been reached."""
        progress = TimeoutSummaryBuilder.build_summary(
            self.agent, self.msg_start_index,
        )
        timeout_msg = (
            "[TURN LIMIT REACHED] You have used all available "
            "turns. Here is a summary of your progress so far:\n\n"
            f"{progress}\n\n"
            "The Tech Lead will decide how to proceed."
        )
        self.agent.messages.append(
            Message(role="assistant", content=timeout_msg),
        )

        role_label = self.agent.identity.role if self.agent.identity else "agent"
        error_event = AgentEvent(
            type=EventType.ERROR,
            data=f"Turn limit ({self.max_turns}) reached for {role_label}",
            source_agent="orchestrator",
        )
        return True, self.wrapup_warned, error_event

    def _handle_wrapup_warning(
        self: TurnEnforcementParams,
        remaining: int,
    ) -> tuple[bool, bool, AgentEvent | None]:
        """Handle wrap-up warning when turns are running low."""
        warn_msg = (
            f"[WRAP-UP WARNING] You have {remaining} tool-call "
            f"turn(s) remaining. Prioritise:\n"
            f"1. Run any final verification (tests, lint).\n"
            f"2. Write a completion report using the "
            f"DELEGATION_SUMMARY_SCHEMA format.\n"
            f"3. List BLOCKERS if you cannot finish in time."
        )
        self.agent.messages.append(Message(role="user", content=warn_msg))
        return False, True, None


class ExecutionController:
    """Manages agent execution loops and state."""

    def __init__(self: ExecutionController, orchestrator: Any) -> None:
        """Initialize the ExecutionController.

        Args:
            orchestrator: The parent orchestrator instance.
        """
        self.orchestrator = orchestrator

    async def run_agent_loop(
        self: ExecutionController,
        params: AgentLoopParams,
    ) -> AsyncIterator[AgentEvent]:
        """Handle the run loop for an agent, executing tools and intercepting delegations."""
        agent = _validate_agent(params)
        generator: AsyncIterator[AgentEvent] = agent.run(params.input_text)
        state = LoopState()

        while True:
            # Phase 1: Collect events and extract pending tool calls
            pending: list[ToolCall] = []
            async for event in _collect_events_and_tool_calls(generator, pending):
                yield event

            # Phase 2: Handle case with no pending tools
            if not pending:
                should_break, events, new_gen = await self._process_no_pending(
                    agent, state, generator,
                )
                for event in events:
                    yield event
                if should_break:
                    break
                if new_gen is not None:
                    generator = new_gen
                continue

            # Phase 3: Execute pending tools and update state
            async for event in self._execute_pending_tools(agent, pending, params, state):
                yield event

            # Phase 4: Check turn limits
            should_break, error_event = self._check_and_handle_turn_limits(
                agent, params, state,
            )
            if error_event:
                yield error_event
            if should_break:
                break

            # Phase 5: Continue with tool results for next iteration
            generator = agent.continue_with_tool_results()

        self._finalize_agent_loop(agent, state)

    async def _process_no_pending(
        self: ExecutionController,
        agent: Agent,
        state: LoopState,
        generator: AsyncIterator[AgentEvent],
    ) -> tuple[bool, list[AgentEvent], AsyncIterator[AgentEvent] | None]:
        """Process the case when no tool calls are pending.

        Returns:
            Tuple of (should_break, events_to_yield, new_generator).
        """
        should_continue, events, colon_result = await self._handle_no_pending_tools(
            agent, state,
        )

        if not should_continue:
            return True, events, None

        if colon_result is not None:
            new_gen, state.colon_stall_retries = colon_result
            return False, events, new_gen

        return False, events, None

    def _check_and_handle_turn_limits(
        self: ExecutionController,
        agent: Agent,
        params: AgentLoopParams,
        state: LoopState,
    ) -> tuple[bool, AgentEvent | None]:
        """Check turn limits and handle if reached.

        Returns:
            Tuple of (should_break, error_event).
        """
        enforcement = TurnEnforcementParams(
            agent=agent,
            max_turns=params.max_turns,
            tool_call_count=state.tool_call_count,
            msg_start_index=params.msg_start_index,
            wrapup_warned=state.wrapup_warned,
        )
        should_break, state.wrapup_warned, error_event = enforcement.enforce_limits()
        if error_event or should_break:
            return should_break, error_event
        return False, None

    def _finalize_agent_loop(
        self: ExecutionController,
        agent: Agent,
        state: LoopState,
    ) -> None:
        """Finalize agent loop by storing state and metrics."""
        if not hasattr(agent, "_delegation_tool_errors"):
            agent._delegation_tool_errors = []  # type: ignore[attr-defined]
        agent._delegation_tool_errors = state.tool_errors  # type: ignore[attr-defined]
        self.orchestrator._last_loop_tool_call_count = state.tool_call_count  # noqa: SLF001

    async def _handle_no_pending_tools(
        self: ExecutionController,
        agent: Agent,
        state: LoopState,
    ) -> tuple[bool, list[AgentEvent], tuple[AsyncIterator[AgentEvent], int] | None]:
        """Handle case when no tool calls are pending.

        Returns:
            Tuple of (should_continue, events_to_yield, colon_stall_result)
            where should_continue is True if loop should continue, False to break.
        """
        events: list[AgentEvent] = []

        # Check thinking patterns
        thinking_event = self.orchestrator.validator.check_thinking_pattern(agent)
        if thinking_event:
            events.append(thinking_event)

        # Check stall failures
        stall_event = self.orchestrator.validator.check_stall_failure(agent)
        if stall_event:
            events.append(stall_event)

        # Check for colon stall
        colon_result = _check_colon_stall(agent, state.colon_stall_retries)
        if colon_result is not None:
            return True, events, colon_result

        # Agent finished (with or without events)
        if events:
            return False, events, None
        return False, [], None

    async def _execute_pending_tools(
        self: ExecutionController,
        agent: Agent,
        pending_tool_calls: list[ToolCall],
        params: AgentLoopParams,
        state: LoopState,
    ) -> AsyncIterator[AgentEvent]:
        """Execute all pending tool calls and update state."""
        async for event in self.orchestrator.tool_controller.process_pending_tool_calls(
            agent, pending_tool_calls, params.depth, state.tool_errors,
        ):
            yield event

        state.tool_call_count += len(pending_tool_calls)
        _inject_role_anchor(self.orchestrator, agent, state.tool_call_count)

    def assess_completion(
        self: ExecutionController,
        agent: Agent,
    ) -> CompletionStatus:
        """Assess whether an agent performed meaningful work."""
        tool_calls = getattr(
            self.orchestrator, "_last_loop_tool_call_count", 0,
        )

        if getattr(agent, "_stall_failure", False):
            return CompletionStatus.STALLED

        if tool_calls == 0:
            return CompletionStatus.NO_WORK_DONE

        return CompletionStatus.COMPLETED

    def enforce_turn_limits(
        self: ExecutionController,
        params: TurnEnforcementParams,
    ) -> tuple[bool, bool, AgentEvent | None]:
        """Enforce turn limits with warnings and hard stops."""
        return params.enforce_limits()

    def check_colon_stall(
        self: ExecutionController,
        agent: Agent,
        colon_stall_retries: int,
    ) -> tuple[AsyncIterator[AgentEvent], int] | None:
        """Check for colon stall pattern and handle if detected."""
        return _check_colon_stall(agent, colon_stall_retries)


# ---------------------------------------------------------------------------
# Module-level helpers (extracted to reduce feature envy in classes)
# ---------------------------------------------------------------------------


def _validate_agent(params: AgentLoopParams) -> Agent:
    """Validate that an agent is provided in the parameters."""
    if params.agent is None:
        msg = "Agent must be provided in AgentLoopParams"
        raise ValueError(msg)
    return params.agent


async def _collect_events_and_tool_calls(
    generator: AsyncIterator[AgentEvent],
    pending_tool_calls: list[ToolCall],
) -> AsyncIterator[AgentEvent]:
    """Collect events from generator and extract pending tool calls."""
    try:
        async for event in generator:
            if event.type == EventType.TOOL_CALL_REQUEST:
                pending_tool_calls.append(event.data)
            yield event
    except StopAsyncIteration:
        pass


def _check_colon_stall(
    agent: Agent,
    colon_stall_retries: int,
) -> tuple[AsyncIterator[AgentEvent], int] | None:
    """Check for colon stall pattern and handle if detected."""
    if colon_stall_retries >= MAX_COLON_STALL_RETRIES:
        return None

    content = _last_assistant_content(agent)
    stripped = content.strip() if content else ""
    if (
        stripped
        and stripped.endswith(":")
        and len(stripped) > COLON_STALL_MIN_LENGTH
    ):
        agent.messages.append(Message(role="user", content=COLON_STALL_NUDGE))
        return agent.continue_with_tool_results(), colon_stall_retries + 1

    return None


def _last_assistant_content(agent: Agent) -> str:
    """Return the content of the agent's last assistant message."""
    for msg in reversed(agent.messages):
        if msg.role == "assistant" and msg.content:
            return msg.content
    return ""


def _inject_role_anchor(
    orchestrator: Any,
    agent: Agent,
    tool_call_count: int,
) -> None:
    """Inject periodic role anchoring reminder if needed."""
    if (
        tool_call_count > 0
        and tool_call_count % ROLE_ANCHOR_INTERVAL == 0
        and agent.identity
    ):
        role_id = agent.identity.role or agent.identity.id
        mission_note = ""
        ledger = orchestrator.ledger
        if ledger:
            recap = ledger.mission_recap()
            if recap:
                mission_note = f" Mission: {recap}"
        anchor_msg = (
            f"[Role Anchor] You are the {role_id.upper()}. "
            f"Stay focused on your assigned responsibilities. "
            f"Do not overstep your role boundaries.{mission_note}"
        )
        agent.messages.append(Message(role="user", content=anchor_msg))
