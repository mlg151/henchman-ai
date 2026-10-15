"""The shared team loop bounds batches and records each agent's own work."""

import asyncio
from collections.abc import AsyncIterator
from functools import partial
from unittest.mock import MagicMock

import pytest

from henchman.agents.orchestrator import Orchestrator
from henchman.agents.orchestrator_types import AgentLoopParams
from henchman.core.events import EventType
from henchman.providers.base import FinishReason, ModelProvider, StreamChunk, ToolCall
from henchman.tools.base import Tool, ToolResult
from henchman.utils.validation import validate_message_sequence


class RecordedTool(Tool):
    name = "read_file"
    description = "Record test operations"

    def __init__(self, *, fail: bool = False, block_at: int | None = None) -> None:
        self.calls = 0
        self.fail = fail
        self.block_at = block_at
        self.blocked = asyncio.Event()

    async def execute(self, **params: object) -> ToolResult:
        self.calls += 1
        if self.calls == self.block_at:
            self.blocked.set()
            await asyncio.Event().wait()
        return ToolResult(
            "Read failed" if self.fail else "Read contents", success=not self.fail,
            error="Read failed" if self.fail else None,
        )


def _batch(*ids: str) -> StreamChunk:
    return StreamChunk(tool_calls=[
        ToolCall(id=call_id, name="read_file", arguments={"path": f"{call_id}.py"})
        for call_id in ids
    ], finish_reason=FinishReason.TOOL_CALLS)


def _orchestrator(chunks: list[StreamChunk], tool: RecordedTool) -> Orchestrator:
    provider = MagicMock(spec=ModelProvider)
    provider.estimate_input_tokens.side_effect = partial(ModelProvider.estimate_input_tokens, provider)
    provider.prepare_output_budget.side_effect = partial(ModelProvider.prepare_output_budget, provider)
    queue = iter(chunks)

    async def stream(*_args: object, **_kwargs: object) -> AsyncIterator[StreamChunk]:
        yield next(queue)

    provider.chat_completion_stream.side_effect = stream
    orch = Orchestrator(default_provider=provider)
    orch.settings.agents.max_delegation_retries = 0
    orch.tool_registry.register(tool)
    return orch


@pytest.mark.parametrize("direct", [False, True])
async def test_round_budget_executes_two_batches_then_balances_every_rejected_request(direct):
    tool = RecordedTool()
    orch = _orchestrator([
        _batch("one", "two"), _batch("three", "four"), _batch("five", "six"),
        StreamChunk(content="Finished", finish_reason=FinishReason.STOP),
    ], tool)
    agent = orch.pool.get_agent("explorer") if direct else orch.tech_lead
    agent.base_tool_iterations = 2
    stream = orch.run_direct("explorer", "Read source") if direct else orch.run("Read source")

    events = [event async for event in stream]

    assert tool.calls == 4
    assert agent.provider.chat_completion_stream.call_count == 3
    assert agent.turn.iteration == 2
    assert agent.turn.tool_count == 4
    assert agent.turn.tool_call_ids == {"one", "two", "three", "four"}
    results = [event.data for event in events if event.type == EventType.TOOL_CALL_RESULT]
    assert [result["tool_call_id"] for result in results] == [
        "one", "two", "three", "four", "five", "six",
    ]
    assert [result["success"] for result in results] == [True] * 4 + [False] * 2
    assert all("limit" in result["result"].lower() for result in results[-2:])
    assert events[-1].data["status"] == "timed_out"
    assert orch.last_completion_status.value == "timed_out"
    validate_message_sequence(agent.messages)


async def test_final_answer_is_allowed_after_last_permitted_tool_round():
    tool = RecordedTool()
    orch = _orchestrator([
        _batch("one"), _batch("two"),
        StreamChunk(content="Source inspected", finish_reason=FinishReason.STOP),
    ], tool)
    orch.tech_lead.base_tool_iterations = 2

    events = [event async for event in orch.run("Read source")]

    assert events[-1].data["status"] == "completed"
    assert not any(event.type == EventType.ERROR for event in events)
    assert tool.calls == 2
    assert orch.tech_lead.turn.iteration == 2
    assert orch.tech_lead.turn.tool_count == 2


async def test_failed_tool_is_recorded_without_claiming_success():
    tool = RecordedTool(fail=True)
    orch = _orchestrator([
        _batch("failed"), StreamChunk(content="Read failed", finish_reason=FinishReason.STOP),
    ], tool)

    events = [event async for event in orch.run("Read source")]

    assert events[-1].data["status"] == "no_work_done"
    assert orch.tech_lead.turn.iteration == 1
    assert orch.tech_lead.turn.tool_count == 1
    assert orch.tech_lead.turn.errors_seen == ["Read failed"]


async def test_parent_and_specialist_record_only_their_own_calls_with_reused_ids():
    delegate = StreamChunk(tool_calls=[ToolCall(
        id="shared", name="delegate_task", arguments={"agent": "explorer", "task": "Read source"},
    )], finish_reason=FinishReason.TOOL_CALLS)
    tool = RecordedTool()
    orch = _orchestrator([
        delegate, _batch("shared", "child-extra"),
        StreamChunk(content="Source inspected", finish_reason=FinishReason.STOP),
        StreamChunk(content="Specialist finished", finish_reason=FinishReason.STOP),
    ], tool)

    _ = [event async for event in orch.run("Inspect source")]

    child = orch.pool.get_agent("explorer")
    assert orch.tech_lead.turn.tool_count == 1
    assert orch.tech_lead.turn.tool_call_ids == {"shared"}
    assert orch.tech_lead.turn.iteration == 1
    assert child.turn.tool_count == 2
    assert child.turn.tool_call_ids == {"shared", "child-extra"}
    assert child.turn.iteration == 1


async def test_delegated_specialist_has_its_own_round_budget():
    delegate = StreamChunk(tool_calls=[ToolCall(
        id="delegate", name="delegate_task", arguments={"agent": "explorer", "task": "Read source"},
    )], finish_reason=FinishReason.TOOL_CALLS)
    tool = RecordedTool()
    orch = _orchestrator([
        delegate, _batch("one"), _batch("two"), _batch("three"),
        StreamChunk(content="The specialist reached its limit", finish_reason=FinishReason.STOP),
    ], tool)
    child = orch.pool.get_agent("explorer")
    child.base_tool_iterations = 2

    events = [event async for event in orch.run("Inspect source")]

    assert tool.calls == 2
    assert child.turn.iteration == 2
    assert child.turn.tool_count == 2
    assert orch.tech_lead.turn.iteration == 1
    assert orch.tech_lead.turn.tool_count == 1
    child_completion = next(
        event for event in events if event.type == EventType.AGENT_COMPLETED
        and event.data["agent"] == "explorer"
    )
    assert child_completion.data["status"] == "timed_out"
    assert events[-1].data["status"] == "no_work_done"
    validate_message_sequence(child.messages)


async def test_zero_round_budget_balances_requests_without_executing_them():
    tool = RecordedTool()
    orch = _orchestrator([_batch("one", "two")], tool)
    orch.tech_lead.base_tool_iterations = 0

    events = [event async for event in orch.run("Read source")]

    assert tool.calls == 0
    assert orch.tech_lead.turn.iteration == 0
    assert orch.tech_lead.turn.tool_count == 0
    results = [event for event in events if event.type == EventType.TOOL_CALL_RESULT]
    assert len(results) == 2
    assert all(event.data["success"] is False for event in results)
    assert events[-1].data["status"] == "timed_out"
    validate_message_sequence(orch.tech_lead.messages)


async def test_specialist_call_cap_remains_distinct_from_round_cap():
    tool = RecordedTool()
    orch = _orchestrator([_batch("one")], tool)
    agent = orch.pool.get_agent("explorer")
    agent.base_tool_iterations = 25

    events = [event async for event in orch.execution_controller.run_agent_loop(
        AgentLoopParams(agent=agent, input_text="Read source", depth=1, max_turns=1),
    )]

    assert tool.calls == 1
    assert agent.turn.iteration == 1
    assert orch._assess_completion(agent).value == "timed_out"
    assert any(event.type == EventType.ERROR and "Turn limit (1)" in event.data for event in events)


async def test_cancelled_batch_keeps_completed_call_evidence_and_balances_unexecuted_calls():
    tool = RecordedTool(block_at=2)
    orch = _orchestrator([_batch("one", "two", "three")], tool)

    async def consume():
        return [event async for event in orch.run("Read source")]

    task = asyncio.create_task(consume())
    await asyncio.wait_for(tool.blocked.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert tool.calls == 2
    assert orch.tech_lead.turn.tool_count == 1
    assert orch.tech_lead.turn.tool_call_ids == {"one"}
    assert orch.tech_lead.turn.iteration == 0
    results = [message for message in orch.tech_lead.messages if message.role == "tool"]
    assert [message.tool_call_id for message in results] == ["one", "two", "three"]
    assert results[0].content == "Read contents"
    assert all("interrupt" in message.content.lower() for message in results[1:])
    validate_message_sequence(orch.tech_lead.messages)
