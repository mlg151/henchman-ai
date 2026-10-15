"""Malformed tool identities must never reach tool execution or saved history."""

from __future__ import annotations

import pytest

from henchman.core.agent import Agent
from henchman.core.events import EventType
from henchman.providers.base import FinishReason, ModelProvider, StreamChunk, ToolCall


@pytest.mark.asyncio
@pytest.mark.parametrize("calls", [
    [],
    [ToolCall(id="", name="edit_file", arguments={})],
    [ToolCall(id=" ", name="edit_file", arguments={})],
    [ToolCall(id="call-1", name="", arguments={})],
    [ToolCall(id="call-1", name=" ", arguments={})],
    [ToolCall(id="duplicate", name="edit_file", arguments={}),
     ToolCall(id="duplicate", name="pytest_run", arguments={})],
])
async def test_invalid_tool_batch_reports_error_before_dispatch(calls: list[ToolCall]) -> None:
    class InvalidBatchProvider(ModelProvider):
        name = "invalid-batch"

        async def chat_completion_stream(self, messages, tools=None, **kwargs):
            yield StreamChunk(tool_calls=calls, finish_reason=FinishReason.TOOL_CALLS)

    agent = Agent(provider=InvalidBatchProvider())
    events = [event async for event in agent.run("Repair the module")]

    assert any(event.type == EventType.ERROR for event in events)
    assert not any(event.type == EventType.TOOL_CALL_REQUEST for event in events)
    assert not any(message.tool_calls for message in agent.messages)
