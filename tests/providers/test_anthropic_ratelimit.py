"""Tests for Anthropic provider rate limiting."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.providers.anthropic import AnthropicProvider, RateLimitError
from henchman.providers.base import FinishReason, Message


@pytest.mark.asyncio
async def test_anthropic_rate_limit_initialization():
    """Test that AnthropicProvider initializes with the correct rate limit."""
    provider = AnthropicProvider(api_key="test", tokens_per_minute=100)
    assert provider._rate_limiter.tokens_per_minute == 100


@pytest.mark.asyncio
async def test_anthropic_rate_limiting_delays():
    """Test that AnthropicProvider actually delays when limit is reached."""
    # Set a very low rate limit
    limit = 50
    messages = [Message(role="user", content="Hello world")]
    # "Hello world" is about 2 tokens + overhead, let's say 10 tokens total estimate

    # Mock the anthropic client
    with patch("henchman.providers.anthropic.AsyncAnthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        provider = AnthropicProvider(api_key="test", tokens_per_minute=limit)

        # Mock the stream
        mock_stream = AsyncMock()

        async def mock_aiter():
            if False:
                yield None

        mock_stream.__aenter__.return_value = mock_aiter()
        mock_client.messages.stream.return_value = mock_stream

        _start_time = time.time()

        # First call should be fast
        async for _ in provider.chat_completion_stream(messages):
            pass

        # Manually add a lot of usage to trigger limit
        await provider._rate_limiter.add_usage(limit - 5)

        # Second call should wait
        # We need to ensure the wait is triggered.
        # The input tokens for "Hello world" will likely be > 5.

        async for _ in provider.chat_completion_stream(messages):
            pass

        _end_time = time.time()

        # It should have waited at least a bit, but since we are using actual time.time()
        # and asyncio.sleep(), and our RateLimiter waits until capacity is available,
        # it might wait for a full minute if we don't mock time.
        # But for this test, let's just check that it didn't finish instantly if we use a small enough limit.

        # Actually, let's mock asyncio.sleep to verify it's called
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            # Reset rate limiter usage
            provider._rate_limiter.usage.clear()
            await provider._rate_limiter.add_usage(limit - 1)

            async for _ in provider.chat_completion_stream(messages):
                pass

            assert mock_sleep.called


@pytest.mark.asyncio
async def test_anthropic_rate_limit_retry():
    """Test that AnthropicProvider retries on RateLimitError."""
    limit = 100
    messages = [Message(role="user", content="Hello")]

    with patch("henchman.providers.anthropic.AsyncAnthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        provider = AnthropicProvider(api_key="test", tokens_per_minute=limit, max_retries=2)

        # Setup mock stream for successful call
        mock_stream = AsyncMock()

        async def mock_aiter():
            yield MagicMock(
                type="content_block_delta", delta=MagicMock(type="text_delta", text="Success")
            )
            yield MagicMock(type="message_delta", delta=MagicMock(stop_reason="end_turn"))

        mock_stream.__aenter__.return_value = mock_aiter()

        # First call fails, second succeeds
        # Anthropic SDK RateLimitError needs a message and response
        error_response = MagicMock()
        error_response.status_code = 429
        rate_limit_error = RateLimitError(
            message="Rate limit hit", response=error_response, body={}
        )

        mock_client.messages.stream.side_effect = [rate_limit_error, mock_stream]

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            chunks = []
            async for chunk in provider.chat_completion_stream(messages):
                chunks.append(chunk)

            assert mock_client.messages.stream.call_count == 2
            assert mock_sleep.call_count == 1
            assert any(c.content == "Success" for c in chunks)
            assert any(c.finish_reason == FinishReason.STOP for c in chunks)
