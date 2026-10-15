"""Reusable verification suite for Model Providers."""

from __future__ import annotations

from henchman.providers.base import Message, ModelProvider, StreamChunk
from tests.contracts.schemas.providers import ModelProviderContract


async def verify_provider_contract(provider: ModelProvider) -> None:
    """Verify that a provider instance satisfies the ModelProviderContract."""
    assert isinstance(provider, ModelProviderContract)
    assert hasattr(provider, "name")
    assert isinstance(provider.name, str)

    # Test chat_completion_stream with simple input
    messages = [Message(role="user", content="Hello")]

    chunks = []
    async for chunk in provider.chat_completion_stream(messages):
        assert isinstance(chunk, StreamChunk)
        chunks.append(chunk)

    assert len(chunks) > 0, "Provider yielded no chunks"

    # Verify that at least one chunk has a finish reason if it's a complete stream
    # (Note: some providers might only yield finish_reason in the very last chunk)
    has_finish_reason = any(chunk.finish_reason is not None for chunk in chunks)
    assert has_finish_reason, "No chunk contained a finish_reason"

    # Verify content accumulation
    content = "".join(chunk.content for chunk in chunks if chunk.content)
    assert len(content) > 0 or any(chunk.tool_calls for chunk in chunks), "Provider yielded neither content nor tool calls"
