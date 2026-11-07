"""Budget exhaustion is a run boundary, including delegated provider work."""

from unittest.mock import AsyncMock

import pytest
from tests.agents.test_completion_integrity import make_orchestrator

from henchman.core.events import EventType
from henchman.core.run_budget import BudgetExceeded
from henchman.providers.base import FinishReason, StreamChunk, ToolCall


@pytest.mark.parametrize("direct", [False, True])
async def test_budget_error_propagates_and_releases_run_claim(direct):
    error = BudgetExceeded("request_limit")
    orch = make_orchestrator([error])
    events = []
    stream = orch.run_direct("explorer", "inspect") if direct else orch.run("inspect")
    with pytest.raises(BudgetExceeded) as raised:
        async for event in stream:
            events.append(event)
    assert raised.value is error
    assert orch._public_run_active is False
    assert orch.last_completion_status.value == "failed"
    assert not any(event.type == EventType.AGENT_COMPLETED for event in events)


async def test_delegation_does_not_wrap_or_retry_budget_exhaustion():
    error = BudgetExceeded("token_limit")
    delegation = StreamChunk(tool_calls=[ToolCall("delegate", "delegate_task", {
        "agent": "explorer", "task": "Inspect source",
    })], finish_reason=FinishReason.TOOL_CALLS)
    orch = make_orchestrator([delegation, error])
    orch.settings.agents.max_delegation_retries = 3
    with pytest.raises(BudgetExceeded) as raised:
        _ = [event async for event in orch.run("Inspect source")]
    assert raised.value is error
    assert orch.tech_lead.provider.chat_completion_stream.call_count == 2
    assert orch._public_run_active is False
    assert orch.ledger.delegations[0].status.value == "failed"


async def test_budget_error_during_request_preparation_is_not_summary_fallback(monkeypatch):
    orch = make_orchestrator([])
    error = BudgetExceeded("money_limit")
    monkeypatch.setattr(orch.tech_lead, "_prepare_stream_context", AsyncMock(side_effect=error))
    with pytest.raises(BudgetExceeded) as raised:
        _ = [event async for event in orch.tech_lead.run("inspect")]
    assert raised.value is error
    orch.tech_lead.provider.chat_completion_stream.assert_not_called()


async def test_agent_finished_event_retains_usage_provenance():
    orch = make_orchestrator([StreamChunk(
        content="answer", finish_reason=FinishReason.STOP,
        usage={"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        usage_source="estimated",
    )])
    events = [event async for event in orch.tech_lead.run("question")]
    finished = next(event for event in events if event.type == EventType.FINISHED)
    assert finished.data["usage_source"] == "estimated"
    assert finished.data["usage"]["total_tokens"] == 12
