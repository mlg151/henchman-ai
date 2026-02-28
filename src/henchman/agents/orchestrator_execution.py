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
        """Run the agent loop, executing tools and intercepting delegations."""
        if params.agent is None:
            msg = "Agent must be provided in AgentLoopParams"
            raise ValueError(msg)
        agent = params.agent
        generator: AsyncIterator[AgentEvent] = agent.run(params.input_text)
        state = LoopState()
        while True:
            pending: list[ToolCall] = []
            async for event in collect_events(generator, pending):
                yield event
            if not pending:
                should_break, evts, new_gen = self._process_no_pending(agent, state)
                for evt in evts:
                    yield evt
                if should_break:
                    break
                if new_gen is not None:
                    generator = new_gen
                continue
            should_break, events = await _execute_and_check(
                self.orchestrator, agent, pending, params, state,
            )
            for evt in events:
                yield evt
            if should_break:
                break
            generator = agent.continue_with_tool_results()
        finalize_loop(self.orchestrator, agent, state)

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

        colon_result = check_colon_stall(agent, state.colon_stall_retries)
        if colon_result is not None:
            new_gen, state.colon_stall_retries = colon_result
            return False, events, new_gen

        return True, events, None

    def assess_completion(
        self: ExecutionController,
        agent: Agent,
    ) -> CompletionStatus:
        """Assess whether an agent performed meaningful work."""
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
