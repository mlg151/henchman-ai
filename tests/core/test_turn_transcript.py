"""Current-turn evidence survives context compaction and interruption."""

from collections.abc import AsyncIterator

import pytest

from henchman.core.agent import Agent
from henchman.core.events import EventType
from henchman.providers.base import FinishReason, Message, ModelProvider, StreamChunk, ToolCall


class TranscriptProvider(ModelProvider):
    """Replay scripted responses without external requests."""

    name = "transcript-test"

    def __init__(self, responses: list[list[StreamChunk]]) -> None:
        self.responses = iter(responses)

    async def chat_completion_stream(self, messages, tools=None, **kwargs) -> AsyncIterator[StreamChunk]:
        for chunk in next(self.responses):
            yield chunk


@pytest.mark.asyncio
async def test_current_turn_preserves_full_tool_evidence_across_compaction() -> None:
    call = ToolCall(id="read", name="read_file", arguments={"path": "output.txt"})
    provider = TranscriptProvider([
        [StreamChunk(thinking="Read output", tool_calls=[call], finish_reason=FinishReason.TOOL_CALLS)],
        [StreamChunk(content="Done.", finish_reason=FinishReason.STOP)],
    ])
    agent = Agent(provider, max_tokens=1000, intelligent_context=False, summarize_dropped=False)
    agent.stall_detection_enabled = False
    assert agent.current_turn_messages == []
    _ = [event async for event in agent.run("Inspect the output")]
    original = "complete test evidence\n" * 1000
    agent.submit_tool_result("read", original)
    events = [event async for event in agent.continue_with_tool_results()]

    assert any(event.type == EventType.CONTEXT_COMPACTED for event in events)
    assert next(message.content for message in agent.history if message.role == "tool") != original
    transcript = agent.current_turn_messages
    assert [message.role for message in transcript] == ["user", "assistant", "tool", "assistant"]
    assert transcript[1].reasoning_content == "Read output"
    assert transcript[2].content == original
    assert transcript[3].content == "Done."


@pytest.mark.asyncio
async def test_transcript_tool_arguments_are_detached_from_history_and_events() -> None:
    call = ToolCall(id="edit", name="edit_file", arguments={"changes": [{"text": "original"}]})
    agent = Agent(TranscriptProvider([
        [StreamChunk(tool_calls=[call], finish_reason=FinishReason.TOOL_CALLS)],
    ]))
    events = [event async for event in agent.run("Edit")]
    request = next(event.data for event in events if event.type == EventType.TOOL_CALL_REQUEST)
    request.arguments["changes"][0]["text"] = "mutated"
    agent.history[-1].tool_calls[0].arguments["extra"] = True

    assert agent.current_turn_messages[-1].tool_calls[0].arguments == {
        "changes": [{"text": "original"}],
    }


@pytest.mark.asyncio
async def test_interrupted_partial_response_preserves_thinking_and_content() -> None:
    agent = Agent(TranscriptProvider([[
        StreamChunk(thinking="Considering evidence"),
        StreamChunk(content="Partial answer"),
        StreamChunk(content="Unseen", finish_reason=FinishReason.STOP),
    ]]))
    stream = agent.run("Investigate")
    assert (await anext(stream)).type == EventType.THOUGHT
    assert (await anext(stream)).type == EventType.CONTENT
    await stream.aclose()

    assert agent.current_turn_messages == [
        Message(role="user", content="Investigate"),
        Message(role="assistant", content="Partial answer\n\n[Response interrupted.]",
                reasoning_content="Considering evidence"),
    ]
    assert agent.current_turn_messages[-1] is not agent.history[-1]


@pytest.mark.asyncio
async def test_new_run_resets_current_turn_and_clear_history_clears_it() -> None:
    agent = Agent(TranscriptProvider([
        [StreamChunk(content="First", finish_reason=FinishReason.STOP)],
        [StreamChunk(content="Second", finish_reason=FinishReason.STOP)],
    ]))
    agent.stall_detection_enabled = False
    _ = [event async for event in agent.run("One")]
    _ = [event async for event in agent.run("Two")]

    assert agent.current_turn_messages == [
        Message(role="user", content="Two"), Message(role="assistant", content="Second"),
    ]
    assert any(message.content == "One" for message in agent.history)
    agent.clear_history()
    assert agent.current_turn_messages == []


@pytest.mark.asyncio
async def test_stall_nudge_is_in_current_turn_transcript(monkeypatch) -> None:
    agent = Agent(TranscriptProvider([
        [StreamChunk(content="I will inspect", finish_reason=FinishReason.STOP)],
        [StreamChunk(content="Result", finish_reason=FinishReason.STOP)],
    ]))
    nudges = iter(["Please act", None])

    async def check(*_args, **_kwargs):
        return next(nudges)

    monkeypatch.setattr(agent._stall, "check", check)
    _ = [event async for event in agent.run("Inspect")]

    assert [message.content for message in agent.current_turn_messages] == [
        "Inspect", "I will inspect", "Please act", "Result",
    ]
