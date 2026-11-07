"""Delegation controller for the orchestrator module.

Manages the execution of delegation tool calls and result processing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from henchman.core.events import AgentEvent, EventType
from henchman.core.operation_recovery import OperationRecoveryError, project_operation_result
from henchman.core.runtime_operations import current_operation_run, tool_result_from_operation

from .ledger import DelegationStatus
from .orchestrator_components import OrchestratorComponent
from .orchestrator_events import (
    create_delegation_event,
    create_tool_result_event,
    extract_brief_fields,
    get_completion_requirement,
    update_ledger,
)
from .orchestrator_execution import closing_event_stream
from .orchestrator_types import (
    DELEGATE_TASK_TOOL,
    CompletionRequirement,
    DelegationExecutionParams,
    DelegationParams,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from henchman.core.agent import Agent
    from henchman.providers.base import ToolCall


# ---------------------------------------------------------------------------
# Per-delegation state accumulator
# ---------------------------------------------------------------------------


@dataclass
class _StreamState:
    """Mutable accumulator for a single delegation's streaming results.

    Using a per-call dataclass instead of instance fields makes
    DelegationController safe for concurrent / re-entrant use.

    Attributes:
        result_content: The summary text from the AGENT_COMPLETED event.
        had_error: True if any ERROR event was emitted during the delegation.
        error_message: The content of the first ERROR event emitted.
        status: The status string from the AGENT_COMPLETED event.
    """

    result_content: str = field(default="")
    had_error: bool = field(default=False)
    error_message: str = field(default="")
    status: str = field(default="")
    completion_requirement: CompletionRequirement = CompletionRequirement.ACTIONS
    evidence: dict[str, Any] | None = None

    @property
    def succeeded(self) -> bool:
        """Accept a tool-free response only when the caller requested one."""
        return not self.had_error and (
            self.status == "completed"
            or (
                self.status == "responded"
                and self.completion_requirement == CompletionRequirement.RESPONSE
            )
        )


def _format_delegation_result(target: str, state: _StreamState) -> str:
    """Combine specialist output with the observed runtime outcome."""
    result = state.result_content or (
        "Delegation completed (no output)." if state.succeeded else "No output returned."
    )
    result += "\n\nTask verification: not established by runtime execution."
    if state.had_error:
        error = state.error_message or "Delegation encountered a runtime error."
        result = f"❌ ERROR: {error}\n\n{result}"

    if state.status == "completed" or state.succeeded:
        return result
    if state.status == "no_work_done":
        warning = f"Agent {target} ended without sufficient completion evidence."
    elif state.status == "timed_out":
        warning = (
            f"Agent {target} reached the turn limit before finishing its task."
        )
    elif state.status:
        warning = f"Agent {target} ended with status '{state.status}'."
    else:
        warning = f"Agent {target} ended without reporting a completion status."
    return f"⚠️ {warning}\n\n{result}"


# ---------------------------------------------------------------------------
# Delegation controller — manages delegation tool execution
# ---------------------------------------------------------------------------


class DelegationController(OrchestratorComponent):
    """Manages delegation tool execution and result processing."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute_delegation_tool(
        self: DelegationController,
        agent: Agent,
        tool_call: ToolCall,
        depth: int,
    ) -> AsyncIterator[AgentEvent]:
        """Execute a delegation tool call.

        Records metrics, creates a ledger entry, then streams the
        delegated agent run back to the caller.

        Args:
            agent: The agent that initiated the delegation.
            tool_call: The tool call containing delegation parameters.
            depth: The current delegation depth (for recursion tracking).

        Yields:
            AgentEvent: Stream of events from the delegated agent execution.
        """
        tc_args = tool_call.arguments
        target = tc_args.get("agent", "")
        task = tc_args.get("task", "")
        run = current_operation_run()
        invocation = run.capture_call(agent, tool_call) if run is not None else None
        permit = None
        if invocation is not None:
            operation = invocation.prepare(tool_call.name, tc_args, "effectful")
            if operation.state == "completed" and operation.result is not None:
                agent.submit_tool_result(tool_call.id, tool_result_from_operation(operation.result))
                yield create_tool_result_event(agent, tool_call, operation.result.content, success=operation.result.success)
                return
            permit = invocation.start()
            if permit is None:
                raise OperationRecoveryError("operation_already_dispatched")

        def on_result(content: str, success: bool) -> str:
            if invocation is None or permit is None:
                return content
            projected = project_operation_result(content, success, redactor=invocation.run.session.evidence_redactor)
            invocation.complete(permit, projected)
            return projected.content

        self.metrics.delegation_count += 1
        if target in self.metrics.delegation_by_type:
            self.metrics.delegation_by_type[target] += 1
        self.metrics.update_tool_metrics(
            DELEGATE_TASK_TOOL,
            tc_args,
            success=True,
        )

        ledger = self.orchestrator.ledger
        ledger_record = ledger.add_delegation(agent=target, task=task) if ledger else None

        params = DelegationExecutionParams(
            target=target,
            task=task,
            depth=depth,
            tool_call=tool_call,
            agent=agent,
            ledger_record=ledger_record,
        )
        try:
            yield create_delegation_event(agent, target, task)
            stream = self._run_delegation(params, on_result=on_result) if invocation is not None else self._run_delegation(params)
            async with closing_event_stream(stream) as events:
                async for event in events:
                    yield event
        except BaseException as exc:
            if invocation is not None and permit is not None:
                invocation.cancel_after_error(exc)
            record = params.ledger_record
            if ledger and record and record.status == DelegationStatus.PENDING:
                ledger.fail_delegation(record, "Delegation interrupted before completion.")
            raise

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_delegation(
        self: DelegationController,
        params: DelegationExecutionParams,
        *, on_result: Callable[[str, bool], str] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Execute delegation and yield result event.

        Args:
            params: Execution parameters for this delegation.

        Yields:
            AgentEvent: Events from the delegated agent, followed by a
                tool-result event once the delegation completes.
        """
        max_retries = self.orchestrator.settings.agents.max_delegation_retries
        final_state = _StreamState()

        target = params.target
        task = params.task
        agent = params.agent
        tool_call = params.tool_call

        for attempt in range(max_retries + 1):
            state = _StreamState()
            stream = self._stream_delegation(params, state)
            async with closing_event_stream(stream) as events:
                async for sub_event in events:
                    yield sub_event

            result = _format_delegation_result(target, state)

            # Update ledger now so _inject_failure_context can see it on retry
            update_ledger(
                self.orchestrator.ledger,
                params.ledger_record,
                result,
                had_error=not state.succeeded,
            )
            final_state = state

            if not state.had_error or attempt >= max_retries:
                break

            # Create a fresh ledger record for the next attempt
            ledger = self.orchestrator.ledger
            if ledger:
                params.ledger_record = ledger.add_delegation(
                    agent=target, task=task,
                )

        final_result = _format_delegation_result(target, final_state)

        submitted = final_result
        ledger = self.orchestrator.ledger
        if ledger:
            submitted = f"{final_result}\n\n{ledger.render()}"

        if on_result is not None:
            submitted = on_result(submitted, final_state.succeeded)
        agent.submit_tool_result(tool_call.id, submitted)
        event = create_tool_result_event(
            agent, tool_call, submitted, success=final_state.succeeded,
        )
        event.data.update({"task_verified": False, "evidence": final_state.evidence})
        yield event

    async def _stream_delegation(
        self: DelegationController,
        params: DelegationExecutionParams,
        state: _StreamState,
    ) -> AsyncIterator[AgentEvent]:
        """Stream events from the delegation runner into *state*.

        Args:
            params: Execution parameters for this delegation.
            state: Mutable accumulator that captures completion data
                and error flags as events arrive.

        Yields:
            AgentEvent: Raw events from the specialist agent.
        """
        try:
            brief = extract_brief_fields(params.tool_call.arguments)
            state.completion_requirement = get_completion_requirement(brief)
        except ValueError as exc:
            state.had_error = True
            state.error_message = str(exc)
            yield AgentEvent(type=EventType.ERROR, data=str(exc))
            return
        delegation_params = DelegationParams(
            target_role=params.target,
            task=params.task,
            brief=brief,
            depth=params.depth + 1,
        )

        runner = self.orchestrator.delegation_runner
        stream = runner.run_delegation(delegation_params)
        async with closing_event_stream(stream) as events:
            async for sub_event in events:
                if (
                    sub_event.type == EventType.AGENT_COMPLETED
                    and sub_event.data.get("agent") == params.target
                ):
                    data = sub_event.data
                    state.result_content = data.get("summary", "")
                    state.status = data.get("status", "")
                    state.evidence = data.get("evidence")
                if sub_event.type == EventType.ERROR:
                    state.had_error = True
                    if not state.error_message:
                        state.error_message = str(sub_event.data)
                yield sub_event
