"""Loop helpers for the orchestrator execution module.

Pure functions that support the agent execution loop: event collection,
turn limit checks, colon stall detection, and finalization.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import Message

from .orchestrator_anchoring import (
    assess_agent_completion,
    inject_role_anchor,
)
from .orchestrator_turns import TurnEnforcementParams
from .orchestrator_types import (
    COLON_STALL_MIN_LENGTH,
    COLON_STALL_NUDGE,
    MAX_COLON_STALL_RETRIES,
    AgentLoopParams,
    LoopState,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from henchman.core.agent import Agent
    from henchman.providers.base import ToolCall

# Re-export for callers that import from this module
__all__ = [
    "assess_agent_completion",
    "check_colon_stall",
    "check_turn_limits",
    "collect_events",
    "finalize_loop",
    "inject_role_anchor",
    "last_assistant_content",
    "run_tools_and_collect",
]


# ---------------------------------------------------------------------------
# Tool execution and event collection
# ---------------------------------------------------------------------------


async def run_tools_and_collect(
    orchestrator: Any,
    agent: Agent,
    pending: list[ToolCall],
    params: AgentLoopParams,
    state: LoopState,
) -> list[AgentEvent]:
    """Execute pending tool calls and collect events.

    Args:
        orchestrator: The orchestrator instance containing tool controller.
        agent: The agent instance to process tool calls for.
        pending: List of pending tool calls to execute.
        params: Agent loop parameters including depth and other settings.
        state: Current loop state including tool errors and call count.

    Returns:
        list[AgentEvent]: List of events generated during tool execution.
    """
    tool_ctrl = orchestrator.tool_controller
    events = [
        event
        async for event in tool_ctrl.process_pending_tool_calls(
            agent,
            pending,
            params.depth,
            state.tool_errors,
        )
    ]
    state.tool_call_count += len(pending)
    inject_role_anchor(orchestrator, agent, state.tool_call_count)
    return events


async def collect_events(
    generator: AsyncIterator[AgentEvent],
    pending: list[ToolCall],
) -> AsyncIterator[AgentEvent]:
    """Collect events from generator and extract pending tool calls.

    Args:
        generator: Async iterator yielding AgentEvent objects from agent execution
        pending: List to accumulate tool call requests encountered during iteration

    Yields:
        AgentEvent: Each event from the generator, with tool call requests
            also added to the pending list
    """
    try:
        async for event in generator:
            if event.type == EventType.TOOL_CALL_REQUEST:
                pending.append(event.data)
            yield event
    except StopAsyncIteration:
        pass


# ---------------------------------------------------------------------------
# Turn limit enforcement
# ---------------------------------------------------------------------------


def check_turn_limits(
    agent: Agent,
    params: AgentLoopParams,
    state: LoopState,
) -> tuple[bool, AgentEvent | None]:
    """Check turn limits and return (should_break, error_event).

    Args:
        agent: The agent whose turn limits to check.
        params: Agent loop parameters containing max_turns and msg_start_index.
        state: Loop state containing tool_call_count and wrapup_warned flag.

    Returns:
        Tuple of (should_break, error_event) where:
        - should_break: True if the loop should terminate due to turn limits
        - error_event: AgentEvent with error message if limits exceeded, None otherwise
    """
    enforcement = TurnEnforcementParams(
        agent=agent,
        max_turns=params.max_turns,
        tool_call_count=state.tool_call_count,
        msg_start_index=params.msg_start_index,
        wrapup_warned=state.wrapup_warned,
    )
    should_break, state.wrapup_warned, err = enforcement.enforce_limits()
    return should_break, err


def finalize_loop(
    orchestrator: Any,
    agent: Agent,
    state: LoopState,
) -> None:
    """Finalize agent loop by storing state and metrics.

    Args:
        orchestrator: The orchestrator instance managing the agent execution.
        agent: The agent whose loop is being finalized.
        state: The current loop state containing metrics and errors.

    Returns:
        None
    """
    if not hasattr(agent, "_delegation_tool_errors"):
        agent._delegation_tool_errors = []  # type: ignore[attr-defined]  # noqa: SLF001
    agent._delegation_tool_errors = state.tool_errors  # type: ignore[attr-defined]  # noqa: SLF001
    orchestrator._last_loop_tool_call_count = state.tool_call_count  # noqa: SLF001


# ---------------------------------------------------------------------------
# Colon-stall detection
# ---------------------------------------------------------------------------


def check_colon_stall(
    agent: Agent,
    retries: int,
) -> tuple[AsyncIterator[AgentEvent], int] | None:
    """Check for colon stall pattern and handle if detected.

    Args:
        agent: The agent to check for colon stall patterns.
        retries: Current number of colon stall retry attempts.

    Returns:
        A tuple of (agent event iterator, incremented retry count) if a colon
        stall is detected and retries haven't exceeded the maximum, otherwise
        None. The colon stall pattern occurs when an agent's response ends with
        a colon but doesn't continue with further content, indicating it may be
        stuck waiting for the user to continue.
    """
    if retries >= MAX_COLON_STALL_RETRIES:
        return None
    content = last_assistant_content(agent)
    stripped = content.strip() if content else ""
    if stripped and stripped.endswith(":") and len(stripped) > COLON_STALL_MIN_LENGTH:
        agent.messages.append(Message(role="user", content=COLON_STALL_NUDGE))
        return agent.continue_with_tool_results(), retries + 1
    return None


def last_assistant_content(agent: Agent) -> str:
    """Return the content of the agent's last assistant message.

    Args:
        agent: The agent whose message history to search.

    Returns:
        The content of the most recent assistant message, or an empty string
        if no assistant message with content is found.
    """
    for msg in reversed(agent.messages):
        if msg.role == "assistant" and msg.content:
            return msg.content
    return ""
