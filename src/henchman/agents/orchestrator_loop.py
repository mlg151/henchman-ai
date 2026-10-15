"""Loop helpers for the orchestrator execution module.

Pure functions that support the agent execution loop: event collection,
turn limit checks, colon stall detection, and finalization.
"""

from __future__ import annotations

import logging
import warnings
from typing import TYPE_CHECKING, Any, NoReturn

from henchman.core.agent_streaming import record_message
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import Message
from henchman.tools.base import ToolResult

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

_LOGGER = logging.getLogger(__name__)
_DELEGATION_ERRORS_ATTR = "_delegation_tool_errors"
_LAST_LOOP_TOOL_CALL_COUNT_ATTR = "_last_loop_tool_call_count"
_LAST_LOOP_SUCCESS_COUNT_ATTR = "_last_loop_success_count"
_LAST_LOOP_TIMED_OUT_ATTR = "_last_loop_timed_out"
_MESSAGES_NONE_ERROR = "agent.messages cannot be None"
_MESSAGES_TYPE_ERROR_TEMPLATE = "agent.messages must be a list, got {type_name}"

# Re-export for callers that import from this module
__all__ = [
    "assess_agent_completion",
    "check_colon_stall",
    "check_turn_limits",
    "collect_events",
    "finalize_loop",
    "has_current_turn_response",
    "inject_role_anchor",
    "last_assistant_content",
    "run_tools_and_collect",
    "stream_tool_events",
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
    # Import lazily: the execution controller imports these loop helpers.
    from .orchestrator_execution import closing_event_stream

    stream = stream_tool_events(orchestrator, agent, pending, params, state)
    async with closing_event_stream(stream) as events:
        return [event async for event in events]


async def stream_tool_events(
    orchestrator: Any,
    agent: Agent,
    pending: list[ToolCall],
    params: AgentLoopParams,
    state: LoopState,
) -> AsyncIterator[AgentEvent]:
    """Stream one tool batch, recording only the current agent's actual results."""
    from .orchestrator_execution import closing_event_stream

    tool_ctrl = orchestrator.tool_controller
    pending_by_id = {call.id: call for call in pending}
    source_agent = agent.identity.id if agent.identity else None
    state.tool_call_count += len(pending)
    stream = tool_ctrl.process_pending_tool_calls(
        agent, pending, params.depth, state.tool_errors,
    )
    async with closing_event_stream(stream) as events:
        async for event in events:
            if (
                event.type == EventType.TOOL_CALL_RESULT
                and event.data.get("tool_call_id") in pending_by_id
                and event.source_agent == source_agent
            ):
                call = pending_by_id.pop(event.data["tool_call_id"])
                success = event.data.get("success") is True
                if success:
                    state.successful_tool_call_count += 1
                turn = getattr(agent, "turn", None)
                if turn is not None:
                    content = event.data.get("result") or ""
                    error = None if success else event.data.get("error") or content
                    turn.record_tool_call(
                        call.id, call.name, call.arguments,
                        ToolResult(content=content, success=success, error=error),
                    )
            yield event

    state.tool_round_count += 1
    turn = getattr(agent, "turn", None)
    if turn is not None:
        turn.increment_iteration()
    inject_role_anchor(orchestrator, agent, state.tool_call_count)


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

    Raises:
        StopAsyncIteration: When the generator is exhausted, re-raised to signal
            to the caller that the generator has completed.
    """
    async for event in generator:
        if event.type == EventType.TOOL_CALL_REQUEST:
            pending.append(event.data)
        yield event


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
    should_break, state.wrapup_warned, state.timed_out, err = enforcement.enforce_limits()
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
    # Use the new API method if available, with fallback for backward compatibility
    try:
        agent.record_delegation_errors(state.tool_errors)
    except AttributeError:
        _record_legacy_delegation_errors(agent, state.tool_errors)

    _set_private_attr(orchestrator, _LAST_LOOP_TOOL_CALL_COUNT_ATTR, state.tool_call_count)
    _set_private_attr(orchestrator, _LAST_LOOP_SUCCESS_COUNT_ATTR, state.successful_tool_call_count)
    _set_private_attr(orchestrator, _LAST_LOOP_TIMED_OUT_ATTR, state.timed_out)
    _set_private_attr(orchestrator, "_last_loop_failed", state.failed)
    # Nested or concurrent specialists must not borrow another agent's evidence.
    _set_private_attr(agent, "_orchestrator_loop_state", state)


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

    try:
        content = last_assistant_content(agent)
    except TypeError as e:
        # If we can't get the content, we can't check for colon stall
        _LOGGER.warning("Cannot check for colon stall: %s", e)
        return None

    # Ensure content is a string before processing
    if not isinstance(content, str):
        content = str(content) if content is not None else ""

    stripped = content.strip()
    if stripped and stripped.endswith(":") and len(stripped) > COLON_STALL_MIN_LENGTH:
        record_message(
            agent.messages, Message(role="user", content=COLON_STALL_NUDGE),
            getattr(agent, "current_turn_messages", None),
        )
        return agent.continue_with_tool_results(), retries + 1
    return None


def has_current_turn_response(agent: Agent) -> bool:
    """Check the committed final answer, excluding old history and internal retries."""
    messages = getattr(agent, "current_turn_messages", None)
    if not isinstance(messages, list) or not messages:
        return False
    final = messages[-1]
    return (
        isinstance(final, Message)
        and final.role == "assistant"
        and not final.tool_calls
        and isinstance(final.content, str)
        and bool(final.content.strip())
    )


def last_assistant_content(agent: Agent) -> str:
    """Return the content of the agent's last assistant message.

    Args:
        agent: The agent whose message history to search.

    Returns:
        The content of the most recent assistant message, or an empty string
        if no assistant message with content is found.

    Raises:
        TypeError: If agent.messages is not a list or is None.
    """
    messages = _validate_agent_messages(agent.messages)

    for msg in reversed(messages):
        if msg.role == "assistant" and msg.content:
            return _coerce_message_content(msg.content)
    return ""


def _record_legacy_delegation_errors(agent: Agent, tool_errors: list[str]) -> None:
    """Store delegation errors on legacy agents that lack the new API."""
    warning_message = (
        f"Agent {agent.__class__.__name__} does not have "
        "record_delegation_errors() method. Using dynamic attribute as fallback. "
        "This may cause race conditions in concurrent execution."
    )
    warnings.warn(warning_message, DeprecationWarning, stacklevel=2)
    if not hasattr(agent, _DELEGATION_ERRORS_ATTR):
        _set_private_attr(agent, _DELEGATION_ERRORS_ATTR, [])
    _set_private_attr(agent, _DELEGATION_ERRORS_ATTR, tool_errors)


def _set_private_attr(target: Any, attr_name: str, value: Any) -> None:
    """Set a compatibility attribute without direct private-member access."""
    setattr(target, attr_name, value)


def _validate_agent_messages(messages: Any) -> list[Message]:
    """Validate ``agent.messages`` and return it as a list."""
    if messages is None:
        _raise_messages_type_error(_MESSAGES_NONE_ERROR)
    if not isinstance(messages, list):
        type_name = type(messages).__name__
        error_message = _MESSAGES_TYPE_ERROR_TEMPLATE.format(type_name=type_name)
        _raise_messages_type_error(error_message)
    return messages


def _raise_messages_type_error(message: str) -> NoReturn:
    """Raise a ``TypeError`` for invalid message containers."""
    raise TypeError(message)


def _coerce_message_content(content: Any) -> str:
    """Return message content as a string."""
    if isinstance(content, str):
        return content
    return str(content) if content is not None else ""
