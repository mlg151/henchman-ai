"""Regression coverage for safe native Anthropic tool-call streams."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import patch

import pytest
from anthropic.types import (
    RawContentBlockDeltaEvent,
    RawContentBlockStartEvent,
    RawContentBlockStopEvent,
    RawMessageDeltaEvent,
    RawMessageStopEvent,
    RawMessageStreamEvent,
)

from henchman.core.agent import Agent
from henchman.core.events import EventType
from henchman.providers.anthropic import AnthropicProvider
from henchman.providers.base import FinishReason, Message, StreamChunk


@asynccontextmanager
async def _tool_stream(
    arguments: str,
    stop_reason: str = "tool_use",
) -> AsyncIterator[AsyncIterator[RawMessageStreamEvent]]:
    """Replace the external SDK stream with a native tool-use event sequence."""

    async def events() -> AsyncIterator[RawMessageStreamEvent]:
        yield RawContentBlockStartEvent.model_validate(
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {
                    "type": "tool_use",
                    "id": "call_1",
                    "name": "inspect",
                    "input": {},
                },
            }
        )
        if arguments:
            yield RawContentBlockDeltaEvent.model_validate(
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "input_json_delta", "partial_json": arguments},
                }
            )
        yield RawContentBlockStopEvent(type="content_block_stop", index=0)
        yield RawMessageDeltaEvent.model_validate(
            {
                "type": "message_delta",
                "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                "usage": {"output_tokens": 10},
            }
        )
        yield RawMessageStopEvent(type="message_stop")

    yield events()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments",
    ['{"path":', "[]", "null", '{"value":NaN}', '{"value":Infinity}', '{"value":-Infinity}'],
)
async def test_invalid_tool_arguments_raise_without_dispatch(arguments: str) -> None:
    """Invalid input cannot be replaced by empty arguments or passed to tools."""
    provider = AnthropicProvider(api_key="test-key")
    chunks: list[StreamChunk] = []
    with (
        patch.object(provider._client.messages, "stream", return_value=_tool_stream(arguments)),
        pytest.raises(ValueError),
    ):
        async for chunk in provider.chat_completion_stream([Message(role="user", content="Go")]):
            chunks.append(chunk)
    assert not any(chunk.tool_calls for chunk in chunks)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments",
    ['{"path":', "[]", "null", '{"value":NaN}', '{"value":Infinity}', '{"value":-Infinity}'],
)
async def test_agent_reports_invalid_anthropic_call_without_tool_request(arguments: str) -> None:
    """Native adapter validation reaches the agent's error channel."""
    provider = AnthropicProvider(api_key="test-key")
    agent = Agent(provider=provider)
    with patch.object(provider._client.messages, "stream", return_value=_tool_stream(arguments)):
        events = [event async for event in agent.run("Inspect the project")]
    assert any(event.type == EventType.ERROR for event in events)
    assert not any(event.type == EventType.TOOL_CALL_REQUEST for event in events)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments, expected", [("", {}), ("{}", {}), ('{"path":"a.py"}', {"path": "a.py"})]
)
async def test_complete_object_arguments_are_preserved(
    arguments: str,
    expected: dict[str, Any],
) -> None:
    """Empty argumentless tools and complete JSON objects remain callable."""
    provider = AnthropicProvider(api_key="test-key")
    with patch.object(provider._client.messages, "stream", return_value=_tool_stream(arguments)):
        chunks = [
            chunk
            async for chunk in provider.chat_completion_stream([Message(role="user", content="Go")])
        ]
    calls = [call for chunk in chunks for call in chunk.tool_calls or []]
    assert len(calls) == 1
    assert calls[0].id == "call_1"
    assert calls[0].arguments == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("arguments", ['{"path":', '{"path":"a.py"}'])
async def test_truncated_turn_never_dispatches_pending_tool(arguments: str) -> None:
    """Even parseable arguments are withheld when the turn hits its token limit."""
    provider = AnthropicProvider(api_key="test-key")
    with patch.object(
        provider._client.messages,
        "stream",
        return_value=_tool_stream(arguments, "max_tokens"),
    ):
        chunks = [
            chunk
            async for chunk in provider.chat_completion_stream([Message(role="user", content="Go")])
        ]
    assert chunks[-1].finish_reason == FinishReason.LENGTH
    assert not any(chunk.tool_calls for chunk in chunks)
