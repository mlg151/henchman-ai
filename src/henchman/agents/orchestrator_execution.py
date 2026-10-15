"""Agent execution loop controller for the orchestrator module.

Manages the main agent loop, colon-stall detection, and completion assessment.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from henchman.core.agent_config import AgentConfig
from henchman.core.events import AgentEvent, EventType

from .orchestrator_loop import (
    assess_agent_completion,
    check_colon_stall,
    check_turn_limits,
    finalize_loop,
    has_current_turn_response,
    last_assistant_content,
    stream_tool_events,
)
from .orchestrator_types import (
    AgentLoopParams,
    CompletionRequirement,
    CompletionStatus,
    LoopState,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator

    from henchman.core.agent import Agent
    from henchman.providers.base import ToolCall


_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Backward-compatibility wrappers
# ---------------------------------------------------------------------------


# Re-export for backward compat (orchestrator.py imports this)
def _last_assistant_content(agent: Agent) -> str:
    """Return the content of the agent's last assistant message."""
    return last_assistant_content(agent)


# ---------------------------------------------------------------------------
# Execution controller
# ---------------------------------------------------------------------------


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
    ) -> AsyncGenerator[AgentEvent, None]:
        """Run the agent loop, executing tools and intercepting delegations.

        Args:
            params: Parameters for running the agent loop, including the agent
                instance, input text, and loop configuration.

        Yields:
            AgentEvent: Stream of events from the agent execution, including
                content, tool calls, and delegation events.
        """
        if params.agent is None:
            msg = "Agent must be provided in AgentLoopParams"
            raise ValueError(msg)

        with self.orchestrator.pool.claim_agent(params.agent, owner=params, running=True):
            async with closing_event_stream(self._run_claimed_agent_loop(params)) as stream:
                async for event in stream:
                    yield event

    async def _run_claimed_agent_loop(
        self, params: AgentLoopParams,
    ) -> AsyncIterator[AgentEvent]:
        """Run and settle an agent while its pool execution claim is held."""
        agent = params.agent
        generator: AsyncIterator[AgentEvent] = agent.run(params.input_text)
        state = LoopState(completion_requirement=CompletionRequirement(params.completion_requirement))

        try:
            while True:
                pending: list[ToolCall] = []
                state.response_complete = False
                failed = False
                primary_error: BaseException | None = None
                try:
                    async for event in generator:
                        if event.type == EventType.TOOL_CALL_REQUEST:
                            pending.append(event.data)
                        if event.type == EventType.ERROR:
                            failed = True
                            state.failed = True
                        yield event
                        if event.type == EventType.FINISHED:
                            reason = event.data
                            if isinstance(reason, dict):
                                reason = reason.get("finish_reason")
                            state.response_complete = (
                                reason == "stop" and not pending and has_current_turn_response(agent)
                            )
                            if reason not in ("stop", "tool_calls") or (
                                reason == "tool_calls" and not pending
                            ):
                                failed = True
                                state.failed = True
                                yield AgentEvent(
                                    type=EventType.ERROR,
                                    data=f"Agent response ended without completion: {reason}",
                                    source_agent=event.source_agent,
                                )
                        if failed:
                            break
                except BaseException as exc:
                    primary_error = exc
                    state.failed = True
                    raise
                finally:
                    await _close_stream(generator, primary_error=primary_error)

                if failed:
                    for event in _settle_unanswered_calls(agent, "Skipped after agent error"):
                        yield event
                    break

                if pending:
                    budget_events = _check_tool_round_budget(
                        agent, state, prior_tool_rounds=params.prior_tool_rounds,
                    )
                    if budget_events is not None:
                        for event in budget_events:
                            yield event
                        break
                    tool_stream = stream_tool_events(
                        self.orchestrator, agent, pending, params, state,
                    )
                    async with closing_event_stream(tool_stream) as events_stream:
                        async for event in events_stream:
                            yield event
                    should_break, limit_event = check_turn_limits(agent, params, state)
                    if limit_event is not None:
                        yield limit_event
                    if should_break:
                        break
                    generator = agent.continue_with_tool_results()
                    continue

                should_break, events, next_gen = self._process_no_pending(agent, state)
                for event in events:
                    yield event
                if should_break:
                    break
                if next_gen is not None:
                    generator = next_gen
                    continue
                if not pending:
                    break
        except BaseException:
            # Dispatch, cleanup, and cancellation can fail outside provider iteration.
            state.failed = True
            if params.depth == 0:
                self.orchestrator.last_completion_status = CompletionStatus.FAILED
            raise
        finally:
            # History may already contain the whole batch when a consumer stops
            # after only its first TOOL_CALL_REQUEST. Settle from history, not
            # just the requests that the consumer managed to observe.
            _settle_unanswered_calls(agent, "Tool execution was interrupted or cancelled.")
            finalize_loop(self.orchestrator, agent, state)

    def _process_no_pending(
        self: ExecutionController,
        agent: Agent,
        state: LoopState,
    ) -> tuple[bool, list[AgentEvent], AsyncIterator[AgentEvent] | None]:
        """Process when no tool calls are pending."""
        events: list[AgentEvent] = []

        # Validator is required for proper agent operation
        validator = self.orchestrator.validator
        if validator is None:
            raise RuntimeError(
                "Orchestrator validator is None. This is required for "
                "thinking pattern validation and stall detection. "
                "Ensure the orchestrator is properly initialized.",
            )

        # Check thinking patterns
        thinking_event = validator.check_thinking_pattern(agent)
        if thinking_event:
            events.append(thinking_event)

        # Check for stall failures
        stall_event = validator.check_stall_failure(agent)
        if stall_event:
            events.append(stall_event)

        colon_result = check_colon_stall(agent, state.colon_stall_retries)
        if colon_result is not None:
            new_gen, state.colon_stall_retries = colon_result
            return False, events, new_gen

        return True, events, None

    def assess_completion(
        self: ExecutionController,
        agent: Agent,
    ) -> CompletionStatus:
        """Assess whether an agent performed meaningful work.

        Args:
            agent: The agent instance to assess for completion status.

        Returns:
            CompletionStatus: The completion status of the agent, which can be:
                - COMPLETED: Agent performed meaningful tool calls and finished normally
                - NO_WORK_DONE: Agent stopped without making any tool calls
                - STALLED: Agent announced intent repeatedly but never acted
                - FAILED: Execution failed or the provider stopped abnormally
                - RESPONDED: A normal response satisfied a response-only requirement
        """
        return assess_agent_completion(self.orchestrator, agent)


def _check_tool_round_budget(
    agent: Agent, state: LoopState, *, prior_tool_rounds: int = 0,
) -> list[AgentEvent] | None:
    """Reject a new tool batch after the finite per-agent round budget is spent."""
    limit = getattr(agent, "base_tool_iterations", AgentConfig().base_tool_iterations)
    if type(limit) is not int or limit < 0:
        raise ValueError("base_tool_iterations must be a nonnegative integer")
    if prior_tool_rounds + state.tool_round_count < limit:
        return None
    state.timed_out = True
    reason = f"Tool iteration limit ({limit}) reached"
    return [
        AgentEvent(
            type=EventType.ERROR, data=reason,
            source_agent=agent.identity.id if agent.identity else None,
        ),
        *_settle_unanswered_calls(agent, reason),
    ]


@asynccontextmanager
async def closing_event_stream(
    stream: AsyncIterator[AgentEvent],
) -> AsyncIterator[AsyncIterator[AgentEvent]]:
    """Close a forwarded stream without masking consumer errors or cancellation."""
    primary_error: BaseException | None = None
    try:
        yield stream
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        await _close_stream(stream, primary_error=primary_error)


async def _close_stream(
    generator: AsyncIterator[AgentEvent],
    *,
    primary_error: BaseException | None,
) -> None:
    """Close an owned iterator without replacing its primary exception."""
    close = getattr(generator, "aclose", None)
    if close is None:
        return
    try:
        await close()
    except BaseException:
        if primary_error is None:
            raise
        _LOGGER.warning("Agent stream cleanup failed during interruption", exc_info=True)


def _settle_unanswered_calls(agent: Agent, reason: str) -> list[AgentEvent]:
    """Balance the active assistant/tool block without losing completed results."""
    answered: set[str | None] = set()
    for message in reversed(agent.messages):
        if message.role == "tool":
            answered.add(message.tool_call_id)
            continue
        if message.role != "assistant" or not message.tool_calls:
            return []
        events = []
        for call in message.tool_calls:
            if call.id in answered:
                continue
            agent.submit_tool_result(call.id, reason)
            answered.add(call.id)
            events.append(AgentEvent(
                type=EventType.TOOL_CALL_RESULT,
                data={
                    "tool_call_id": call.id, "tool_name": call.name,
                    "result": reason, "success": False,
                },
                source_agent=agent.identity.id if agent.identity else None,
            ))
        return events
    return []
