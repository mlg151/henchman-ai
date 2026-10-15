"""Exercise provider-to-agent streaming with realistic offline SDK responses."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock

import pytest
from openai._models import construct_type
from openai.types.chat import ChatCompletionChunk

from henchman.core.agent import Agent
from henchman.core.agent_streaming import StreamContext, StreamState, generate_stream_events
from henchman.core.events import EventType
from henchman.providers.base import FinishReason, Message
from henchman.providers.deepseek import DeepSeekProvider
from henchman.providers.ollama import OllamaProvider
from henchman.providers.openai_compat import OpenAICompatibleProvider
from henchman.providers.openrouter import OpenRouterProvider
from tests.providers.stream_helpers import SDKResponse


def response_chunk(
    delta: dict[str, Any],
    finish_reason: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Build a wire-format completion chunk, without mocking SDK attributes."""
    return {
        "id": "completion-1",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "test-model",
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        **extra,
    }


def tool_delta(arguments: str, *, index: int = 0, initial: bool = True) -> dict[str, Any]:
    """Build initial tool metadata or an argument continuation."""
    call: dict[str, Any] = {"index": index, "function": {"arguments": arguments}}
    if initial:
        call.update(id=f"call-{index}", type="function")
        call["function"]["name"] = "write_file"
    return {"tool_calls": [call]}


@pytest.fixture(params=["openrouter", "openai_compat", "deepseek", "ollama"])
async def stream_provider(
    request: pytest.FixtureRequest,
) -> AsyncIterator[tuple[OpenAICompatibleProvider, list[dict[str, Any]]]]:
    """Use real providers, substituting only the external SDK request."""
    factories = {
        "openrouter": lambda: OpenRouterProvider(api_key="test"),
        "openai_compat": lambda: OpenAICompatibleProvider(
            "test", "https://test.invalid/v1", "test-model"
        ),
        "deepseek": lambda: DeepSeekProvider(api_key="test"),
        "ollama": OllamaProvider,
    }
    provider = factories[request.param]()
    payloads: list[dict[str, Any]] = []

    async def stream() -> AsyncIterator[ChatCompletionChunk]:
        for payload in payloads:
            # The SDK's default parser permits provider-specific finish reasons.
            yield construct_type(type_=ChatCompletionChunk, value=payload)

    provider._client.chat.completions.create = AsyncMock(side_effect=lambda **_kwargs: SDKResponse(stream()))
    try:
        yield provider, payloads
    finally:
        await provider._client.close()


async def collect_events(provider: OpenAICompatibleProvider):
    context = StreamContext(provider, [Message(role="user", content="Edit the file")], [], [])
    state = StreamState()
    async with asyncio.timeout(5):
        events = [event async for event in generate_stream_events(context, state, compacted=False)]
    return events, context, state


@pytest.mark.parametrize(
    "arguments",
    [
        '{"path":',
        "[]",
        "null",
        '"text"',
        "42",
        '{"value": NaN}',
        '{"value": Infinity}',
        '{"value": -Infinity}',
    ],
)
async def test_invalid_tool_arguments_never_reach_dispatch(stream_provider, arguments):
    provider, payloads = stream_provider
    payloads.extend([response_chunk(tool_delta(arguments)), response_chunk({}, "tool_calls")])
    events, context, _ = await collect_events(provider)
    assert any(event.type == EventType.ERROR for event in events)
    assert not any(event.type == EventType.TOOL_CALL_REQUEST for event in events)
    assert context.history == []


@pytest.mark.parametrize("reason", ["length", "content_filter", "stop"])
async def test_incomplete_tools_are_not_saved_as_completed_calls(stream_provider, reason):
    provider, payloads = stream_provider
    payloads.extend([response_chunk(tool_delta('{"path":')), response_chunk({}, reason)])
    events, context, state = await collect_events(provider)
    assert not any(event.type == EventType.TOOL_CALL_REQUEST for event in events)
    assert not state.tool_calls
    assert all(not message.tool_calls for message in context.history)


async def test_fragmented_parallel_calls_dispatch_once_with_final_usage(stream_provider):
    provider, payloads = stream_provider
    usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    payloads.extend(
        [
            response_chunk(tool_delta('{"path": "a')),
            response_chunk(tool_delta('{"path": "b.py"}', index=1)),
            response_chunk(tool_delta('.py"}', initial=False)),
            response_chunk({}, "tool_calls"),
            response_chunk({}, "tool_calls", usage=usage),
        ]
    )
    events, context, state = await collect_events(provider)
    calls = [event.data for event in events if event.type == EventType.TOOL_CALL_REQUEST]
    assert [(call.id, call.arguments) for call in calls] == [
        ("call-0", {"path": "a.py"}),
        ("call-1", {"path": "b.py"}),
    ]
    assert len(context.history) == 1
    assert state.usage == usage
    assert events[-1].data == {"finish_reason": "tool_calls", "usage": usage}


async def test_usage_only_chunk_survives_empty_choices(stream_provider):
    provider, payloads = stream_provider
    usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    payloads.extend(
        [response_chunk({"content": "Done"}, "stop"), response_chunk({}, choices=[], usage=usage)]
    )
    events, _, state = await collect_events(provider)
    assert state.usage == usage
    assert events[-1].data == {"finish_reason": "stop", "usage": usage}


async def test_text_on_finish_chunk_is_not_lost(stream_provider):
    provider, payloads = stream_provider
    payloads.extend(
        [response_chunk({"content": "Hello "}), response_chunk({"content": "world"}, "stop")]
    )
    events, context, _ = await collect_events(provider)
    assert (
        "".join(event.data for event in events if event.type == EventType.CONTENT) == "Hello world"
    )
    assert context.history[0].content == "Hello world"


@pytest.mark.parametrize("field", ["reasoning", "reasoning_content"])
async def test_reasoning_survives_tool_turn_and_next_request(stream_provider, field):
    """Both text dialects must survive streaming, history and tool continuation."""
    provider, payloads = stream_provider
    payloads.extend(
        [
            response_chunk({field: "Inspect the existing "}),
            response_chunk({field: "helper first."}),
            response_chunk(tool_delta('{"path": "helper.py"}')),
            response_chunk({}, "tool_calls"),
        ]
    )
    agent = Agent(provider=provider)
    events = [event async for event in agent.run("Inspect helper.py")]
    assert not any(event.type == EventType.ERROR for event in events)
    assert "".join(event.data for event in events if event.type == EventType.THOUGHT) == (
        "Inspect the existing helper first."
    )
    assert agent.messages[-1].reasoning_content == "Inspect the existing helper first."
    agent.submit_tool_result("call-0", "Existing helper found")
    payloads[:] = [response_chunk({"content": "Done"}, "stop")]
    continued = [event async for event in agent.continue_with_tool_results()]
    assert not any(event.type == EventType.ERROR for event in continued)
    sent = provider._client.chat.completions.create.call_args.kwargs["messages"]
    assistant = next(message for message in sent if message.get("tool_calls"))
    assert assistant["reasoning_content"] == "Inspect the existing helper first."
    assert assistant["tool_calls"][0]["id"] == "call-0"
    assert sent[-1]["tool_call_id"] == "call-0"


@pytest.mark.parametrize(
    ("delta", "expected"),
    [
        ({"reasoning_content": "legacy", "reasoning": "normalized"}, "legacy"),
        ({"reasoning_content": None, "reasoning": "normalized"}, "normalized"),
        ({"reasoning_content": "", "reasoning": "normalized"}, "normalized"),
        ({"content": "No reasoning"}, None),
    ],
)
async def test_reasoning_aliases_emit_one_text_value(stream_provider, delta, expected):
    """Prefer existing text without concatenating duplicate provider aliases."""
    provider, payloads = stream_provider
    payloads.append(response_chunk(delta, "stop"))
    events, context, _ = await collect_events(provider)
    assert not any(event.type == EventType.ERROR for event in events)
    assert [event.data for event in events if event.type == EventType.THOUGHT] == (
        [expected] if expected is not None else []
    )
    assert context.history[0].reasoning_content == expected


async def test_midstream_error_is_not_successful_assistant_history(stream_provider):
    provider, payloads = stream_provider
    payloads.extend(
        [
            response_chunk({"content": "Starting"}),
            response_chunk({}, "error", error={"code": "server_error", "message": "Disconnected"}),
        ]
    )
    events, context, state = await collect_events(provider)
    assert any(event.type == EventType.ERROR for event in events)
    assert context.history == []
    assert state.finish_reason != FinishReason.STOP


async def test_stream_without_finish_reason_reports_interruption(stream_provider):
    provider, payloads = stream_provider
    payloads.append(response_chunk({"content": "Partial response"}))
    events, context, _ = await collect_events(provider)
    assert any(event.type == EventType.ERROR for event in events)
    assert context.history == []


async def test_transport_failure_reaches_agent_error_event(stream_provider):
    provider, _ = stream_provider

    provider._client.chat.completions.create = AsyncMock(side_effect=ConnectionError("offline"))
    events, context, _ = await collect_events(provider)
    assert any(event.type == EventType.ERROR for event in events)
    assert context.history == []
    assert not any(event.type == EventType.CONTENT for event in events)


async def test_agent_does_not_retry_failed_partial_response_as_a_stall(stream_provider):
    provider, payloads = stream_provider
    payloads.append(response_chunk({"content": "Let me start by editing the file."}))
    agent = Agent(provider=provider)
    events = [event async for event in agent.run("Edit the file")]
    assert len([event for event in events if event.type == EventType.ERROR]) == 1
    assert [message.content for message in agent.messages if message.role == "user"] == [
        "Edit the file"
    ]
