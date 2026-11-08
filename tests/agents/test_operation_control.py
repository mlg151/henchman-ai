"""Uncertain effects are run controls, including delegated/background work."""

import asyncio

import pytest
from tests.agents.test_background_subagents import manager_for
from tests.agents.test_operation_runtime import build

from henchman.core.events import AgentEvent, EventType
from henchman.core.operation_recovery import OperationRecoveryError
from henchman.providers.base import FinishReason, StreamChunk, ToolCall


async def test_background_unknown_effect_latches_across_notification_cleanup():
    error = OperationRecoveryError("outcome_unknown")
    async def runner(_agent, _prompt):
        yield AgentEvent(EventType.CONTENT, "partial evidence")
        raise error
    manager = manager_for(runner)
    manager.spawn("task", role="reviewer", system_prompt="child", tools=[])
    try:
        with pytest.raises(OperationRecoveryError) as raised:
            await asyncio.wait_for(manager.wait_for_notification(), 1)
        assert raised.value is error
        manager.clear_notifications()
        with pytest.raises(OperationRecoveryError) as again:
            manager.drain_notifications()
        assert again.value is error
    finally:
        await manager.close()


async def test_delegated_unknown_effect_propagates_without_provider_retry(tmp_path):
    orchestrator, provider, tool, _ = build(tmp_path, allow_delegation=True)
    chunks = [
        StreamChunk(tool_calls=[ToolCall("delegate", "delegate_task", {"agent": "engineer", "task": "perform effect"})], finish_reason=FinishReason.TOOL_CALLS),
        StreamChunk(tool_calls=[ToolCall("effect-call", "effect", {"value": "child"})], finish_reason=FinishReason.TOOL_CALLS),
        StreamChunk(content="Should not continue", finish_reason=FinishReason.STOP),
    ]
    async def stream(messages, tools=None, **_kwargs):
        _ = messages, tools
        provider.calls += 1
        yield chunks[min(provider.calls - 1, len(chunks) - 1)]
    provider.chat_completion_stream = stream
    child = orchestrator.pool.get_agent("engineer")
    child.tool_registry = orchestrator.tool_registry
    tool.failure = ConnectionError("effect occurred, response lost")
    with pytest.raises(OperationRecoveryError):
        _ = [event async for event in orchestrator.run("perform effect")]
    assert provider.calls == 2 and tool.calls == ["child"]
    report = orchestrator.operation_runtime.report()
    assert {record.tool_name for record in report.records} == {"delegate_task", "effect"}
    assert all(record.state == "outcome_unknown" for record in report.records)


async def test_delegation_and_specialist_results_keep_separate_correlated_history(tmp_path):
    orchestrator, provider, tool, session = build(tmp_path, allow_delegation=True)
    chunks = [
        StreamChunk(tool_calls=[ToolCall("delegate", "delegate_task", {"agent": "engineer", "task": "perform effect"})], finish_reason=FinishReason.TOOL_CALLS),
        StreamChunk(tool_calls=[ToolCall("effect-call", "effect", {"value": "child"})], finish_reason=FinishReason.TOOL_CALLS),
        StreamChunk(content="Done.", finish_reason=FinishReason.STOP),
    ]
    async def stream(messages, tools=None, **_kwargs):
        _ = messages, tools
        provider.calls += 1
        yield chunks[min(provider.calls - 1, len(chunks) - 1)]
    provider.chat_completion_stream = stream
    orchestrator.pool.get_agent("engineer").tool_registry = orchestrator.tool_registry
    _ = [event async for event in orchestrator.run("perform effect")]
    report = orchestrator.operation_runtime.report()
    assert {record.tool_name for record in report.records} == {"delegate_task", "effect"}
    assert all(record.state == "completed" for record in report.records)
    child = next(binding for binding in session.operations.bindings if binding.context.tool_call_id == "effect-call")
    assert child.conversation_id is not None
    assert all(call["id"] != "effect-call" for message in session.messages for call in message.tool_calls or [])
    from henchman.core.session_data import session_from_dict
    restored, _, _, restored_session = build(tmp_path, session=session_from_dict(session.to_dict()))
    restored.operation_runtime.begin()
    assert len(restored_session.operations.observed_ids) == 2
    assert tool.calls == ["child"]


async def test_reused_specialist_keeps_each_turn_and_result_for_recovery(tmp_path):
    orchestrator, provider, tool, session = build(tmp_path, allow_delegation=True)
    chunks = [
        StreamChunk(tool_calls=[ToolCall("first", "delegate_task", {"agent": "engineer", "task": "first"})], finish_reason=FinishReason.TOOL_CALLS),
        StreamChunk(tool_calls=[ToolCall("same-id", "effect", {"value": "first"})], finish_reason=FinishReason.TOOL_CALLS),
        StreamChunk(content="First done", finish_reason=FinishReason.STOP),
        StreamChunk(tool_calls=[ToolCall("second", "delegate_task", {"agent": "engineer", "task": "second"})], finish_reason=FinishReason.TOOL_CALLS),
        StreamChunk(tool_calls=[ToolCall("same-id", "effect", {"value": "second"})], finish_reason=FinishReason.TOOL_CALLS),
        StreamChunk(content="Second done", finish_reason=FinishReason.STOP),
        StreamChunk(content="All done", finish_reason=FinishReason.STOP),
    ]
    async def stream(messages, tools=None, **_kwargs):
        _ = messages, tools
        provider.calls += 1
        yield chunks[provider.calls - 1]
    provider.chat_completion_stream = stream
    orchestrator.pool.get_agent("engineer").tool_registry = orchestrator.tool_registry
    _ = [event async for event in orchestrator.run("perform twice")]
    assert tool.calls == ["first", "second"]
    assert len(session.operations.conversations) == 2
    assert all(any(message.role == "tool" for message in item.messages) for item in session.operations.conversations)
    from henchman.core.session_data import session_from_dict
    restored, _, _, restored_session = build(tmp_path, session=session_from_dict(session.to_dict()))
    restored.operation_runtime.begin()
    assert len(restored_session.operations.observed_ids) == 4
