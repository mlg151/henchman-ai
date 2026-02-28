"""Agent execution loop controller for the orchestrator module.

Manages the main agent loop, colon-stall detection, and completion assessment.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import Message

from .orchestrator_turns import TurnEnforcementParams
from .orchestrator_types import (
    COLON_STALL_MIN_LENGTH,
    COLON_STALL_NUDGE,
    MAX_COLON_STALL_RETRIES,
    ROLE_ANCHOR_INTERVAL,
    AgentLoopParams,
    CompletionStatus,
    LoopState,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from henchman.core.agent import Agent
    from henchman.providers.base import ToolCall


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
        """Run the agent loop, executing tools and intercepting delegations."""
        agent = _validate_agent(params)
        generator: AsyncIterator[AgentEvent] = agent.run(params.input_text)
        state = LoopState()

        while True:
            pending: list[ToolCall] = []
            async for event in _collect_events(generator, pending):
                yield event

            if not pending:
                should_break, evts, new_gen = self._process_no_pending(
                    agent, state,
                )
                for evt in evts:
                    yield evt
                if should_break:
                    break
                if new_gen is not None:
                    generator = new_gen
                continue

            async for event in self._execute_tools(agent, pending, params, state):
                yield event

            should_break, err = _check_turn_limits(agent, params, state)
            if err:
                yield err
            if should_break:
                break

            generator = agent.continue_with_tool_results()

        _finalize_loop(self.orchestrator, agent, state)

    def _process_no_pending(
        self: ExecutionController,
        agent: Agent,
        state: LoopState,
    ) -> tuple[bool, list[AgentEvent], AsyncIterator[AgentEvent] | None]:
        """Process when no tool calls are pending."""
        events: list[AgentEvent] = []

        thinking_event = self.orchestrator.validator.check_thinking_pattern(agent)
        if thinking_event:
            events.append(thinking_event)

        stall_event = self.orchestrator.validator.check_stall_failure(agent)
        if stall_event:
            events.append(stall_event)

        colon_result = _check_colon_stall(agent, state.colon_stall_retries)
        if colon_result is not None:
            new_gen, state.colon_stall_retries = colon_result
            return False, events, new_gen

        return True, events, None

    async def _execute_tools(
        self: ExecutionController,
        agent: Agent,
        pending: list[ToolCall],
        params: AgentLoopParams,
        state: LoopState,
    ) -> AsyncIterator[AgentEvent]:
        """Execute pending tool calls and update state."""
        async for event in self.orchestrator.tool_controller.process_pending_tool_calls(
            agent, pending, params.depth, state.tool_errors,
        ):
            yield event
        state.tool_call_count += len(pending)
        _inject_role_anchor(self.orchestrator, agent, state.tool_call_count)

    def assess_completion(
        self: ExecutionController,
        agent: Agent,
    ) -> CompletionStatus:
        """Assess whether an agent performed meaningful work."""
        tool_calls = getattr(self.orchestrator, "_last_loop_tool_call_count", 0)
        if getattr(agent, "_stall_failure", False):
            return CompletionStatus.STALLED
        if tool_calls == 0:
            return CompletionStatus.NO_WORK_DONE
        return CompletionStatus.COMPLETED


# ---------------------------------------------------------------------------
# Module-level helpers (extracted to reduce feature envy in classes)
# ---------------------------------------------------------------------------


def _validate_agent(params: AgentLoopParams) -> Agent:
    """Validate that an agent is provided."""
    if params.agent is None:
        msg = "Agent must be provided in AgentLoopParams"
        raise ValueError(msg)
    return params.agent


async def _collect_events(
    generator: AsyncIterator[AgentEvent],
    pending: list[ToolCall],
) -> AsyncIterator[AgentEvent]:
    """Collect events from generator and extract pending tool calls."""
    try:
        async for event in generator:
            if event.type == EventType.TOOL_CALL_REQUEST:
                pending.append(event.data)
            yield event
    except StopAsyncIteration:
        pass


def _check_turn_limits(
    agent: Agent,
    params: AgentLoopParams,
    state: LoopState,
) -> tuple[bool, AgentEvent | None]:
    """Check turn limits and return (should_break, error_event)."""
    enforcement = TurnEnforcementParams(
        agent=agent,
        max_turns=params.max_turns,
        tool_call_count=state.tool_call_count,
        msg_start_index=params.msg_start_index,
        wrapup_warned=state.wrapup_warned,
    )
    should_break, state.wrapup_warned, err = enforcement.enforce_limits()
    return should_break, err


def _finalize_loop(
    orchestrator: Any, agent: Agent, state: LoopState,
) -> None:
    """Finalize agent loop by storing state and metrics."""
    if not hasattr(agent, "_delegation_tool_errors"):
        agent._delegation_tool_errors = []  # type: ignore[attr-defined]
    agent._delegation_tool_errors = state.tool_errors  # type: ignore[attr-defined]
    orchestrator._last_loop_tool_call_count = state.tool_call_count  # noqa: SLF001


def _check_colon_stall(
    agent: Agent,
    retries: int,
) -> tuple[AsyncIterator[AgentEvent], int] | None:
    """Check for colon stall pattern and handle if detected."""
    if retries >= MAX_COLON_STALL_RETRIES:
        return None
    content = _last_assistant_content(agent)
    stripped = content.strip() if content else ""
    if stripped and stripped.endswith(":") and len(stripped) > COLON_STALL_MIN_LENGTH:
        agent.messages.append(Message(role="user", content=COLON_STALL_NUDGE))
        return agent.continue_with_tool_results(), retries + 1
    return None


def _last_assistant_content(agent: Agent) -> str:
    """Return the content of the agent's last assistant message."""
    for msg in reversed(agent.messages):
        if msg.role == "assistant" and msg.content:
            return msg.content
    return ""


def _inject_role_anchor(
    orchestrator: Any, agent: Agent, tool_call_count: int,
) -> None:
    """Inject periodic role anchoring reminder if needed."""
    if tool_call_count <= 0 or tool_call_count % ROLE_ANCHOR_INTERVAL != 0:
        return
    if not agent.identity:
        return
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
