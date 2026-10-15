"""SDK response lifetime across supported streaming adapters."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from anthropic import RateLimitError as AnthropicRateLimitError
from anthropic.types import RawContentBlockDeltaEvent, RawMessageDeltaEvent
from openai import RateLimitError as OpenAIRateLimitError
from openai.types.chat import ChatCompletionChunk

from henchman.providers.anthropic import AnthropicProvider
from henchman.providers.base import FinishReason, Message, ModelProvider
from henchman.providers.deepseek import DeepSeekProvider
from henchman.providers.ollama import OllamaProvider
from henchman.providers.openai_compat import OpenAICompatibleProvider
from henchman.providers.openrouter import OpenRouterProvider


class ResponseBody:
    """An SDK stream whose lifetime is independently observable."""

    def __init__(self, *, native: bool) -> None:
        self.native = native
        self.closed = False
        self.waiting = asyncio.Event()
        self.mode = "success"
        self.close_error = False
        self.stream_error: Exception = ConnectionError("transport interrupted")

    async def __aiter__(self) -> AsyncIterator[Any]:
        if self.native:
            first = {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": "Partial"},
            }
            last = {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                "usage": {"output_tokens": 1},
            }
        else:
            first = self._compatible_chunk({"content": "Partial"})
            last = self._compatible_chunk({}, "stop")
        yield self._parse(first)
        if self.mode == "wait":
            self.waiting.set()
            await asyncio.Event().wait()
        if self.mode == "error":
            raise self.stream_error
        yield self._parse(last)

    def _parse(self, payload: dict[str, Any]) -> Any:
        if self.native:
            event_type = (
                RawContentBlockDeltaEvent
                if payload["type"] == "content_block_delta"
                else RawMessageDeltaEvent
            )
            return event_type.model_validate(payload)
        return ChatCompletionChunk.model_validate(payload)

    @staticmethod
    def _compatible_chunk(
        delta: dict[str, Any], finish_reason: str | None = None
    ) -> dict[str, Any]:
        return {
            "id": "response-1",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "test-model",
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }

    async def close(self) -> None:
        self.closed = True
        if self.close_error:
            raise RuntimeError("cleanup failed")


@pytest.fixture(params=["openrouter", "openai_compat", "deepseek", "ollama", "anthropic"])
async def streaming_transport(
    request: pytest.FixtureRequest,
) -> AsyncIterator[tuple[ModelProvider, ResponseBody]]:
    """Exercise real adapters with SDK events and observable response cleanup."""
    factories = {
        "openrouter": lambda: OpenRouterProvider(api_key="test"),
        "openai_compat": lambda: OpenAICompatibleProvider(
            "test", "https://test.invalid/v1", "test-model"
        ),
        "deepseek": lambda: DeepSeekProvider(api_key="test"),
        "ollama": OllamaProvider,
        "anthropic": lambda: AnthropicProvider(api_key="test"),
    }
    provider = factories[request.param]()
    body = ResponseBody(native=request.param == "anthropic")

    @asynccontextmanager
    async def native_stream() -> AsyncIterator[ResponseBody]:
        try:
            yield body
        finally:
            await body.close()

    target = provider._client.messages if body.native else provider._client.chat.completions
    replacement = (
        patch.object(target, "stream", return_value=native_stream())
        if body.native
        else patch.object(target, "create", AsyncMock(return_value=body))
    )
    try:
        with replacement:
            yield provider, body
    finally:
        await provider._client.close()


async def test_partial_stream_close_releases_sdk_response(streaming_transport) -> None:
    provider, body = streaming_transport
    stream = provider.chat_completion_stream([Message(role="user", content="Go")])
    try:
        assert (await anext(stream)).content == "Partial"
        assert not body.closed
    finally:
        await stream.aclose()
    assert body.closed


async def test_cancellation_releases_response_and_propagates(streaming_transport) -> None:
    provider, body = streaming_transport
    body.mode = "wait"
    stream = provider.chat_completion_stream([Message(role="user", content="Go")])
    assert (await anext(stream)).content == "Partial"
    pending = asyncio.create_task(anext(stream))
    try:
        async with asyncio.timeout(5):
            await body.waiting.wait()
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert body.closed
    finally:
        pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)
        await stream.aclose()


async def test_stream_failure_releases_response_and_preserves_error(streaming_transport) -> None:
    provider, body = streaming_transport
    body.mode = "error"
    stream = provider.chat_completion_stream([Message(role="user", content="Go")])
    assert (await anext(stream)).content == "Partial"
    with pytest.raises(ConnectionError, match="transport interrupted"):
        await anext(stream)
    assert body.closed


async def test_completed_stream_releases_response_and_preserves_chunks(streaming_transport) -> None:
    provider, body = streaming_transport
    chunks = [
        chunk
        async for chunk in provider.chat_completion_stream([Message(role="user", content="Go")])
    ]
    assert chunks[0].content == "Partial"
    assert chunks[-1].finish_reason == FinishReason.STOP
    assert body.closed


async def test_close_failure_does_not_replace_explicit_stop(streaming_transport, caplog) -> None:
    provider, body = streaming_transport
    body.close_error = True
    stream = provider.chat_completion_stream([Message(role="user", content="Go")])
    assert (await anext(stream)).content == "Partial"
    await stream.aclose()
    assert body.closed
    assert "cleanup failed" in caplog.text


async def test_close_failure_does_not_replace_cancellation(streaming_transport, caplog) -> None:
    provider, body = streaming_transport
    body.mode = "wait"
    body.close_error = True
    stream = provider.chat_completion_stream([Message(role="user", content="Go")])
    assert (await anext(stream)).content == "Partial"
    pending = asyncio.create_task(anext(stream))
    try:
        async with asyncio.timeout(5):
            await body.waiting.wait()
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert body.closed
        assert "cleanup failed" in caplog.text
    finally:
        pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)
        await stream.aclose()


async def test_close_failure_after_completion_is_visible(streaming_transport) -> None:
    provider, body = streaming_transport
    body.close_error = True
    with pytest.raises(RuntimeError, match="cleanup failed"):
        _ = [
            chunk
            async for chunk in provider.chat_completion_stream([Message(role="user", content="Go")])
        ]
    assert body.closed


@pytest.mark.parametrize("error_kind", ["transport", "protocol", "rate_limit"])
async def test_cleanup_failure_preserves_primary_error(
    streaming_transport, caplog, error_kind: str
) -> None:
    provider, body = streaming_transport
    body.mode = "error"
    body.close_error = True
    if error_kind == "protocol":
        body.stream_error = ValueError("malformed stream event")
    elif error_kind == "rate_limit":
        error_type = AnthropicRateLimitError if body.native else OpenAIRateLimitError
        body.stream_error = error_type(
            "rate limited",
            response=httpx.Response(429, request=httpx.Request("POST", "https://test.invalid")),
            body=None,
        )
        if body.native:
            provider.max_retries = 0
    stream = provider.chat_completion_stream([Message(role="user", content="Go")])
    assert (await anext(stream)).content == "Partial"
    with pytest.raises(type(body.stream_error)) as raised:
        await anext(stream)
    assert raised.value is body.stream_error
    assert body.closed
    assert "cleanup failed" in caplog.text


async def test_native_rate_limit_retries_after_secondary_cleanup_failure(caplog) -> None:
    provider = AnthropicProvider(api_key="test", max_retries=1)
    failed = ResponseBody(native=True)
    failed.mode = "error"
    failed.close_error = True
    failed.stream_error = AnthropicRateLimitError(
        "rate limited",
        response=httpx.Response(429, request=httpx.Request("POST", "https://test.invalid")),
        body=None,
    )
    completed = ResponseBody(native=True)
    responses = iter([failed, completed])

    @asynccontextmanager
    async def native_stream(**_kwargs) -> AsyncIterator[ResponseBody]:
        body = next(responses)
        try:
            yield body
        finally:
            await body.close()

    try:
        with (
            patch.object(provider._client.messages, "stream", side_effect=native_stream),
            patch("henchman.providers.anthropic.asyncio.sleep", new=AsyncMock()),
        ):
            chunks = [
                chunk
                async for chunk in provider.chat_completion_stream(
                    [Message(role="user", content="Go")]
                )
            ]
        assert chunks[-1].finish_reason == FinishReason.STOP
        assert failed.closed and completed.closed
        assert "cleanup failed" in caplog.text
    finally:
        await provider._client.close()


async def test_cleanup_failure_is_visible_inside_callers_error_handler(streaming_transport) -> None:
    provider, body = streaming_transport
    body.close_error = True
    try:
        raise ValueError("unrelated earlier failure")
    except ValueError:
        with pytest.raises(RuntimeError, match="cleanup failed"):
            _ = [
                chunk
                async for chunk in provider.chat_completion_stream(
                    [Message(role="user", content="Go")]
                )
            ]
    assert body.closed
