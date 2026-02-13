import os

import pytest

from henchman.providers.anthropic import AnthropicProvider
from henchman.providers.base import Message


@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY not set")
@pytest.mark.anyio
async def test_anthropic_connectivity_opus_4_6():
    """Functional test for Anthropic connectivity with claude-opus-4-6.

    This test requires a valid ANTHROPIC_API_KEY environment variable.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    model = "claude-opus-4-6"
    provider = AnthropicProvider(api_key=api_key, model=model)

    assert provider.name == "anthropic"

    messages = [Message(role="user", content="Hello, respond with exactly 'ACK'")]

    response_content = ""
    async for chunk in provider.chat_completion_stream(messages):
        if chunk.content:
            response_content += chunk.content

    assert "ACK" in response_content.upper()
