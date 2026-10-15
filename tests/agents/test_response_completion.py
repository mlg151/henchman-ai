"""Response delivery is distinct from action evidence and task verification."""

import pytest
from tests.agents.test_completion_integrity import make_orchestrator, read_chunk

from henchman.core.events import EventType
from henchman.providers.base import FinishReason, Message, StreamChunk, ToolCall


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", [
    "Hello!", "A Python generator yields items lazily.", "I will fix the bug.",
])
@pytest.mark.parametrize("direct", [False, True])
async def test_response_is_delivered_without_claiming_task_verification(answer, direct):
    orch = make_orchestrator([StreamChunk(content=answer, finish_reason=FinishReason.STOP)])
    stream = orch.run_direct("explorer", "Explain generators") if direct else orch.run("Explain generators")
    events = [event async for event in stream]
    assert not any(event.type == EventType.ERROR for event in events)
    completed = events[-1].data
    assert completed["status"] == "responded"
    assert completed["task_verified"] is False
    assert completed["evidence"] == {
        "tool_calls": 0, "successful_tool_calls": 0,
        "response_complete": True, "completion_requirement": "response",
    }
    assert orch.last_completion_status.value == "responded"


@pytest.mark.asyncio
@pytest.mark.parametrize("direct", [False, True])
async def test_explicit_actions_requirement_rejects_a_promise(direct):
    orch = make_orchestrator([StreamChunk(content="I will fix it.", finish_reason=FinishReason.STOP)])
    stream = (
        orch.run_direct("explorer", "Fix it", completion_requirement="actions")
        if direct else orch.run("Fix it", completion_requirement="actions")
    )
    events = [event async for event in stream]
    assert events[-1].data["status"] == "no_work_done"
    assert events[-1].data["task_verified"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("chunk", [
    StreamChunk(content="", finish_reason=FinishReason.STOP),
    StreamChunk(content="   ", finish_reason=FinishReason.STOP),
    StreamChunk(thinking="Private reasoning", finish_reason=FinishReason.STOP),
])
async def test_prior_answer_or_thinking_cannot_supply_current_response(chunk):
    orch = make_orchestrator([chunk])
    orch.tech_lead.messages.append(Message(role="assistant", content="Old answer"))
    events = [event async for event in orch.run("New question")]
    assert events[-1].data["status"] == "no_work_done"
    assert events[-1].data["evidence"]["response_complete"] is False


@pytest.mark.asyncio
async def test_failed_tool_apology_is_not_response_only_success():
    orch = make_orchestrator([
        StreamChunk(tool_calls=[ToolCall(id="bad", name="missing_tool", arguments={})],
                    finish_reason=FinishReason.TOOL_CALLS),
        StreamChunk(content="Sorry, that failed.", finish_reason=FinishReason.STOP),
    ])
    events = [event async for event in orch.run("Inspect source")]
    assert events[-1].data["status"] == "no_work_done"
    assert events[-1].data["evidence"]["tool_calls"] == 1
    assert events[-1].data["task_verified"] is False


@pytest.mark.asyncio
async def test_read_and_success_claim_do_not_verify_a_coding_task():
    orch = make_orchestrator([
        read_chunk(), StreamChunk(content="Fixed and verified!", finish_reason=FinishReason.STOP),
    ])
    events = [event async for event in orch.run("Fix the arithmetic bug")]
    completed = events[-1].data
    assert completed["status"] == "completed"
    assert completed["task_verified"] is False
    assert completed["evidence"]["successful_tool_calls"] == 1


@pytest.mark.asyncio
async def test_unknown_requirement_rejected_before_provider_call():
    orch = make_orchestrator([])
    with pytest.raises(ValueError, match="completion|CompletionRequirement"):
        _ = [event async for event in orch.run("Task", completion_requirement="guess")]
    orch.tech_lead.provider.chat_completion_stream.assert_not_called()


@pytest.mark.asyncio
async def test_response_state_does_not_leak_to_next_turn():
    orch = make_orchestrator([
        StreamChunk(content="Hello", finish_reason=FinishReason.STOP),
        StreamChunk(content="", finish_reason=FinishReason.STOP),
    ])
    _ = [event async for event in orch.run("Hello")]
    assert orch.last_completion_status.value == "responded"
    _ = [event async for event in orch.run("Again")]
    assert orch.last_completion_status.value == "no_work_done"


@pytest.mark.asyncio
async def test_stall_retry_cannot_reuse_discarded_intent_as_final_answer():
    orch = make_orchestrator([
        StreamChunk(content="Let me start by inspecting the code.", finish_reason=FinishReason.STOP),
        StreamChunk(content="", finish_reason=FinishReason.STOP),
    ])
    events = [event async for event in orch.run_direct("explorer", "Inspect the code")]
    assert orch.pool.get_agent("explorer").current_turn_messages[-1].content == ""
    assert events[-1].data["status"] == "no_work_done"
    assert events[-1].data["evidence"]["response_complete"] is False
