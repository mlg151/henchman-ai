"""Continuation safety failures stop nested work instead of becoming model data."""

import asyncio
from types import SimpleNamespace

import pytest
from tests.agents.test_background_subagents import manager_for
from tests.agents.test_completion_integrity import make_orchestrator

from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import FinishReason, Message, StreamChunk, ToolCall
from henchman.providers.continuation import ProviderContinuationError
from henchman.tools.base import Tool, ToolKind
from henchman.tools.registry import ToolRegistry
from henchman.utils.compaction import CompactionResult, _attempt_summarization


@pytest.mark.parametrize("direct", [True, False])
async def test_public_run_propagates_continuation_control_and_releases_claim(direct):
    error = ProviderContinuationError("unavailable_continuation")
    orchestrator = make_orchestrator([error])
    stream = orchestrator.run_direct("explorer", "Inspect") if direct else orchestrator.run("Inspect")
    with pytest.raises(ProviderContinuationError) as raised:
        _ = [event async for event in stream]
    assert raised.value is error
    assert not orchestrator._public_run_active
    assert orchestrator.last_completion_status.value == "failed"


async def test_delegation_cannot_wrap_or_retry_incompatible_continuation():
    error = ProviderContinuationError("incompatible_continuation")
    orchestrator = make_orchestrator([StreamChunk(tool_calls=[ToolCall("delegate", "delegate_task", {
        "agent": "explorer", "task": "Inspect",
    })], finish_reason=FinishReason.TOOL_CALLS), error])
    orchestrator.settings.agents.max_delegation_retries = 3
    with pytest.raises(ProviderContinuationError) as raised:
        _ = [event async for event in orchestrator.run("Inspect")]
    assert raised.value is error
    assert orchestrator.tech_lead.provider.chat_completion_stream.call_count == 2


async def test_background_continuation_control_survives_notification_cleanup():
    error = ProviderContinuationError("unavailable_continuation")
    async def runner(_agent, _prompt):
        yield AgentEvent(EventType.CONTENT, "visible partial evidence")
        raise error
    manager = manager_for(runner)
    manager.spawn("Inspect", role="reviewer", system_prompt="child", tools=[])
    try:
        with pytest.raises(ProviderContinuationError) as raised:
            await asyncio.wait_for(manager.wait_for_notification(), 1)
        assert raised.value is error
        manager.clear_notifications()
        with pytest.raises(ProviderContinuationError) as again:
            manager.drain_notifications()
        assert again.value is error
    finally:
        await manager.close()


async def test_summary_cannot_hide_incomplete_continuation_in_a_fallback():
    error = ProviderContinuationError("incomplete_continuation")
    async def stream(**_kwargs):
        raise error
        yield
    with pytest.raises(ProviderContinuationError) as raised:
        await _attempt_summarization(CompactionResult(messages=[]), [Message("user", "Earlier work")],
                                     SimpleNamespace(chat_completion_stream=stream))
    assert raised.value is error


@pytest.mark.parametrize("parallel", [True, False])
async def test_registry_cannot_turn_continuation_control_into_a_tool_result(parallel):
    error = ProviderContinuationError("incompatible_continuation")
    class FailedProviderTool(Tool):
        name = "inspect"
        description = "Inspect"
        kind = ToolKind.READ
        parameters = {"type": "object", "properties": {}, "additionalProperties": False}
        async def execute(self, **_params):
            raise error
    registry = ToolRegistry()
    registry.register(FailedProviderTool())
    with pytest.raises(ProviderContinuationError) as raised:
        if parallel:
            await registry.execute_batch([("inspect", {})])
        else:
            await registry.execute("inspect", {})
    assert raised.value is error
