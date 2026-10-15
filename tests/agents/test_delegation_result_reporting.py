"""Delegation runtime outcomes stay visible to the lead and ledger."""

from collections.abc import AsyncIterator
from unittest.mock import MagicMock

import pytest

from henchman.agents.orchestrator_delegation_ctrl import DelegationController
from henchman.agents.orchestrator_types import DelegationExecutionParams
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import ToolCall


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("failed", "status 'failed'"),
        ("stalled", "status 'stalled'"),
        ("unexpected", "status 'unexpected'"),
        ("responded", "status 'responded'"),
        (None, "without reporting a completion status"),
        ("no_work_done", "without sufficient completion evidence"),
        ("timed_out", "reached the turn limit before finishing its task"),
    ],
)
@pytest.mark.parametrize("summary", [None, "", "Specialist output"])
async def test_unsuccessful_outcome_labels_lead_and_ledger(
    status: str | None, expected: str, summary: str | None,
) -> None:
    """Missing output or status cannot turn an unsuccessful run into completion."""
    completion = {"agent": "coder"}
    if status is not None:
        completion["status"] = status
    if summary is not None:
        completion["summary"] = summary
    event = AgentEvent(type=EventType.AGENT_COMPLETED, data=completion)
    controller, params = _controller([event])

    events = [event async for event in controller._run_delegation(params)]

    result = events[-1].data
    assert result["success"] is False
    assert expected in result["result"]
    assert "Delegation completed" not in result["result"]
    assert "Completed." not in result["result"]
    assert (summary or "No output returned.") in result["result"]
    controller.orchestrator.ledger.fail_delegation.assert_called_once_with(
        params.ledger_record, result["result"].removesuffix("\n\nLEDGER"),
    )
    controller.orchestrator.ledger.complete_delegation.assert_not_called()
    params.agent.submit_tool_result.assert_called_once_with(
        params.tool_call.id, result["result"],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("had_error", [False, True])
async def test_completed_status_does_not_hide_runtime_errors(had_error: bool) -> None:
    """Explicit completion succeeds only when no runtime error was observed."""
    stream = []
    if had_error:
        stream.append(AgentEvent(type=EventType.ERROR, data="Runtime failed"))
    stream.append(AgentEvent(
        type=EventType.AGENT_COMPLETED,
        data={"agent": "coder", "status": "completed", "summary": ""},
    ))
    controller, params = _controller(stream)

    events = [event async for event in controller._run_delegation(params)]

    result = events[-1].data
    assert result["success"] is not had_error
    if had_error:
        assert "ERROR: Runtime failed" in result["result"]
        assert "Delegation completed" not in result["result"]
        controller.orchestrator.ledger.fail_delegation.assert_called_once()
    else:
        assert "Delegation completed (no output)." in result["result"]
        controller.orchestrator.ledger.complete_delegation.assert_called_once()


def _controller(
    events: list[AgentEvent],
) -> tuple[DelegationController, DelegationExecutionParams]:
    async def run_delegation(_params: object) -> AsyncIterator[AgentEvent]:
        for event in events:
            yield event

    orchestrator = MagicMock()
    orchestrator.settings.agents.max_delegation_retries = 0
    orchestrator.ledger.render.return_value = "LEDGER"
    orchestrator.delegation_runner.run_delegation = run_delegation
    params = DelegationExecutionParams(
        target="coder",
        task="Implement the requested change",
        depth=0,
        tool_call=ToolCall(id="delegate-1", name="delegate_task", arguments={}),
        agent=MagicMock(),
        ledger_record=MagicMock(),
    )
    return DelegationController(orchestrator), params
