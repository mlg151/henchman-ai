"""Provider usage snapshots retain provenance and cache accounting offline."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from anthropic.types import RawMessageDeltaEvent, RawMessageStartEvent
from openai._models import construct_type
from openai.types.chat import ChatCompletionChunk

from henchman.providers.anthropic import AnthropicProvider
from henchman.providers.base import Message, StreamChunk
from henchman.providers.deepseek import DeepSeekProvider
from henchman.providers.ollama import OllamaProvider
from henchman.providers.openai_compat import OpenAICompatibleProvider
from henchman.providers.openrouter import OpenRouterProvider
from henchman.providers.usage import UsageReport
from tests.providers.stream_helpers import SDKResponse
from tests.providers.test_stream_safety import response_chunk


def test_usage_distinguishes_missing_zero_and_estimated_counts() -> None:
    assert StreamChunk().usage_source == "unknown"
    assert StreamChunk(usage={"prompt_tokens": 0}).usage_source == "reported"
    estimated = StreamChunk(usage={"prompt_tokens": 12}, usage_source="estimated")
    assert estimated.usage_source == "estimated"
    assert UsageReport().total_tokens is None
    assert UsageReport(prompt_tokens=0, completion_tokens=0, source="reported").total_tokens == 0
    assert UsageReport(prompt_tokens=12, source="estimated").completion_tokens is None


@pytest.mark.parametrize("bad", [-1, True, 1.2])
def test_usage_rejects_invalid_counts(bad: object) -> None:
    with pytest.raises(ValueError, match="nonnegative integer"):
        UsageReport(prompt_tokens=bad, source="reported")


async def test_compatible_final_usage_preserves_cache_and_reasoning() -> None:
    provider = OpenAICompatibleProvider("test", "https://test.invalid/v1", "test")

    async def stream() -> AsyncIterator[ChatCompletionChunk]:
        for payload in [
            response_chunk({"content": "Done"}, "stop"),
            response_chunk({}, choices=[], usage={
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
                "prompt_tokens_details": {"cached_tokens": 60, "cache_write_tokens": 10},
                "completion_tokens_details": {"reasoning_tokens": 8},
            }),
        ]:
            yield construct_type(type_=ChatCompletionChunk, value=payload)

    provider._client.chat.completions.create = AsyncMock(return_value=SDKResponse(stream()))
    try:
        chunks = [chunk async for chunk in provider.chat_completion_stream([Message("user", "Go")])]
    finally:
        await provider._client.close()
    assert chunks[-1].usage == {
        "prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120,
        "cached_tokens": 60, "cache_creation_tokens": 10, "reasoning_tokens": 8,
    }
    assert chunks[-1].usage_source == "reported"
    assert chunks[0].usage_source == "unknown"


def test_compatible_partial_usage_does_not_invent_missing_counts() -> None:
    from henchman.providers.openai_compat import _extract_usage_from_chunk

    chunk = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=23, completion_tokens=None))
    assert _extract_usage_from_chunk(chunk) == {"prompt_tokens": 23}
    assert _extract_usage_from_chunk(SimpleNamespace(usage=None)) is None


@pytest.mark.parametrize("kind", ["compatible", "deepseek", "openrouter", "ollama"])
@pytest.mark.parametrize("options", ["default", None, {"include_usage": False}, {"include_usage": True}])
async def test_usage_request_kwargs_for_each_compatible_adapter(kind, options) -> None:
    factories = {
        "compatible": lambda **opts: OpenAICompatibleProvider("test", "https://test.invalid/v1", "test", **opts),
        "deepseek": lambda **opts: DeepSeekProvider(api_key="test", **opts),
        "openrouter": lambda **opts: OpenRouterProvider(api_key="test", **opts),
        "ollama": lambda **opts: OllamaProvider(**opts),
    }
    provider = factories[kind](**({} if options == "default" else {"stream_options": options}))

    async def stream() -> AsyncIterator[ChatCompletionChunk]:
        yield ChatCompletionChunk.model_validate(response_chunk({"content": "Done"}, "stop"))

    create = AsyncMock(return_value=SDKResponse(stream()))
    provider._client.chat.completions.create = create
    try:
        _ = [chunk async for chunk in provider.chat_completion_stream([Message("user", "Go")])]
        expected = {
            "model": provider.default_model,
            "messages": [{"role": "user", "content": "Go"}],
            "stream": True,
        }
        if options is not None:
            expected["stream_options"] = {"include_usage": True} if options == "default" else options
        create.assert_awaited_once_with(**expected)
    finally:
        await provider._client.close()


async def test_compatible_partial_snapshots_preserve_prior_fields() -> None:
    provider = OpenAICompatibleProvider("test", "https://test.invalid/v1", "test")

    async def stream() -> AsyncIterator[ChatCompletionChunk]:
        for payload in [
            response_chunk({"content": "Done"}, "stop", usage={"prompt_tokens": 100, "completion_tokens": 1}),
            response_chunk({}, choices=[], usage={"completion_tokens": 7}),
        ]:
            yield construct_type(type_=ChatCompletionChunk, value=payload)

    provider._client.chat.completions.create = AsyncMock(return_value=SDKResponse(stream()))
    try:
        chunks = [chunk async for chunk in provider.chat_completion_stream([Message("user", "Go")])]
    finally:
        await provider._client.close()
    assert chunks[-1].usage == {"prompt_tokens": 100, "completion_tokens": 7, "total_tokens": 107}


async def test_anthropic_usage_combines_cache_and_cumulative_output() -> None:
    provider = AnthropicProvider(api_key="test")
    start = RawMessageStartEvent.model_validate({
        "type": "message_start",
        "message": {
            "id": "msg-1", "type": "message", "role": "assistant", "model": "test",
            "content": [], "stop_reason": None, "stop_sequence": None,
            "usage": {
                "input_tokens": 30, "cache_read_input_tokens": 60,
                "cache_creation_input_tokens": 10, "output_tokens": 1,
            },
        },
    })
    middle = RawMessageDeltaEvent.model_validate({
        "type": "message_delta", "delta": {"stop_reason": None, "stop_sequence": None},
        "usage": {"output_tokens": 4},
    })
    final = RawMessageDeltaEvent.model_validate({
        "type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
        "usage": {"output_tokens": 7},
    })

    async def events() -> AsyncIterator[object]:
        for event in (start, middle, final):
            yield event

    @asynccontextmanager
    async def stream() -> AsyncIterator[AsyncIterator[object]]:
        yield events()

    try:
        with patch.object(provider._client.messages, "stream", return_value=stream()) as send:
            chunks = [chunk async for chunk in provider.chat_completion_stream([Message("user", "Go")])]
            send.assert_called_once_with(
                model=provider.default_model, messages=[{"role": "user", "content": "Go"}], max_tokens=8192,
            )
    finally:
        await provider._client.close()
    snapshots = [chunk.usage for chunk in chunks if chunk.usage is not None]
    assert snapshots[0]["completion_tokens"] == 1
    assert snapshots[-1] == {
        "prompt_tokens": 100, "completion_tokens": 7, "total_tokens": 107,
        "cached_tokens": 60, "cache_creation_tokens": 10,
    }
    assert chunks[-1].usage_source == "reported"
