"""Agent execution loop controller for the orchestrator module.

Manages the main agent loop, colon-stall detection, and completion assessment.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .orchestrator_loop import (
    assess_agent_completion,
    check_colon_stall,
    check_turn_limits,
    collect_events,
    finalize_loop,
    last_assistant_content,
    run_tools_and_collect,
)
from .orchestrator_types import (
    AgentLoopParams,
    CompletionStatus,
    LoopState,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from henchman.core.agent import Agent
    from henchman.core.events import AgentEvent
    from henchman.providers.base import ToolCall


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
    ) -> AsyncIterator[AgentEvent]:
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

        agent = params.agent
        generator: AsyncIterator[AgentEvent] = agent.run(params.input_text)
        state = LoopState()

        while True:
            pending: list[ToolCall] = []
            generator_exhausted = False
            try:
                async for event in collect_events(generator, pending):
                    yield event
            except StopAsyncIteration:
                generator_exhausted = True

            # Decide next action based on pending tool calls
            should_break, events, next_gen = await self._step_loop(
                agent, pending, params, state, generator_exhausted,
            )

            for evt in events:
                yield evt

            if should_break:
                break

            if next_gen is not None:
                generator = next_gen
                continue

            # If no tools and no new generator, we're done
            if not pending:
                break

        finalize_loop(self.orchestrator, agent, state)

    async def _step_loop(
        self: ExecutionController,
        agent: Agent,
        pending: list[ToolCall],
        params: AgentLoopParams,
        state: LoopState,
        generator_exhausted: bool,
    ) -> tuple[bool, list[AgentEvent], AsyncIterator[AgentEvent] | None]:
        """Determine next step in the agent loop.

        Returns:
            Tuple of (should_break, events, next_generator).
        """
        if not pending:
            return self._process_no_pending(agent, state)

        # Execute tools and check limits
        should_break, events = await _execute_and_check(
            self.orchestrator,
            agent,
            pending,
            params,
            state,
        )

        if should_break:
            return True, events, None

        return False, events, agent.continue_with_tool_results()


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
        """
        return assess_agent_completion(self.orchestrator, agent)


async def _execute_and_check(
    orchestrator: Any,
    agent: Agent,
    pending: list[ToolCall],
    params: AgentLoopParams,
    state: LoopState,
) -> tuple[bool, list[AgentEvent]]:
    """Execute tools and check turn limits, returning events."""
    events = await run_tools_and_collect(orchestrator, agent, pending, params, state)
    should_break, err = check_turn_limits(agent, params, state)
    if err:
        events.append(err)
    return should_break, events
