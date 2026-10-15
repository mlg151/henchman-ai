"""Contract verification for OpenRouterProvider."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from openai.types.chat import ChatCompletionChunk

from henchman.providers.base import FinishReason, Message
from henchman.providers.openrouter import OpenRouterProvider
from tests.contracts.verify_provider import verify_provider_contract
from tests.providers.stream_helpers import SDKResponse


@pytest.mark.asyncio
async def test_openrouter_provider_satisfies_contract() -> None:
    """Verify real SDK chunk parsing, content, and usage through the adapter."""
    provider = OpenRouterProvider(api_key="test-key")

    async def mock_stream(**_kwargs: Any) -> AsyncGenerator[ChatCompletionChunk]:
        yield ChatCompletionChunk.model_validate(
            {
                "id": "completion_1",
                "created": 0,
                "object": "chat.completion.chunk",
                "model": "openai/gpt-4o-mini",
                "choices": [
                    {"index": 0, "delta": {"content": "OpenRouter"}, "finish_reason": None}
                ],
            }
        )
        yield ChatCompletionChunk.model_validate(
            {
                "id": "completion_1",
                "created": 0,
                "object": "chat.completion.chunk",
                "model": "openai/gpt-4o-mini",
                "choices": [
                    {"index": 0, "delta": {"content": " response"}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
        )

    with (
        patch.object(
            provider._client.chat.completions,
            "create",
            new=AsyncMock(side_effect=lambda **kwargs: SDKResponse(mock_stream(**kwargs))),
        ) as create,
        patch.object(SDKResponse, "close", autospec=True, side_effect=SDKResponse.close) as close,
    ):
        await verify_provider_contract(provider)
        chunks = [
            chunk
            async for chunk in provider.chat_completion_stream(
                [Message(role="user", content="Hello")]
            )
        ]

    assert create.await_count > 0
    assert close.await_count == create.await_count
    assert "".join(chunk.content or "" for chunk in chunks) == "OpenRouter response"
    assert chunks[-1].finish_reason == FinishReason.STOP
    assert chunks[-1].usage == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
