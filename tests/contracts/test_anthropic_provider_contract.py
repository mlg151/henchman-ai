"""Contract verification for AnthropicProvider."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from henchman.providers.anthropic import AnthropicProvider
from tests.contracts.verify_provider import verify_provider_contract


@pytest.mark.asyncio
async def test_anthropic_provider_satisfies_contract():
    """Verify that AnthropicProvider satisfies the ModelProvider contract using mocks."""
    provider = AnthropicProvider(
        api_key="test-key",
        model="claude-3-5-sonnet",
    )

    # Mock the AsyncAnthropic client
    mock_client = MagicMock()
    provider._client = mock_client

    # Mock the messages stream
    async def mock_stream(*args, **kwargs):
        # Anthropic chunks are different, but the provider maps them to StreamChunk
        # We need to mock the response that the provider expects from the Anthropic client.

        # Anthropic provider uses `self._client.messages.stream`
        # and then iterates over the context manager's result.

        # This is more complex because of how Anthropic's SDK works.
        # For the sake of contract testing, let's mock the internal _make_api_request if possible,
        # or just mock the stream object.
        pass

    # Actually, the AnthropicProvider implementation maps Anthropic events to StreamChunk.
    # Let's mock the stream context manager.

    mock_stream_ctx = MagicMock()
    mock_stream_obj = AsyncMock()

    # Mock events that the provider iterates over
    async def mock_events():
        # Anthropic SDK events
        yield MagicMock(type="message_start", message=MagicMock(usage=MagicMock(input_tokens=10, output_tokens=0)))
        yield MagicMock(type="content_block_start", index=0, content_block=MagicMock(type="text", text=""))
        yield MagicMock(type="content_block_delta", index=0, delta=MagicMock(type="text_delta", text="Hello"))
        yield MagicMock(type="content_block_stop", index=0)
        yield MagicMock(type="message_delta", delta=MagicMock(stop_reason="end_turn", usage=MagicMock(output_tokens=5)))
        yield MagicMock(type="message_stop")

    mock_stream_obj.__aiter__.side_effect = mock_events
    mock_stream_ctx.__aenter__.return_value = mock_stream_obj

    mock_client.messages.stream.return_value = mock_stream_ctx

    # Verify the contract
    await verify_provider_contract(provider)
