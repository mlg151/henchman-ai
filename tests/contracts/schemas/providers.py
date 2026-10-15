"""Contract definition for Model Providers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable

from henchman.providers.base import Message, StreamChunk, ToolDeclaration


@runtime_checkable
class ModelProviderContract(Protocol):
    """Protocol defining the structural and behavioral contract for a ModelProvider."""

    @property
    def name(self) -> str:
        """The unique name of this provider."""
        ...

    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream a chat completion from the model.

        Behavioral Requirements:
        1. MUST yield at least one StreamChunk.
        2. SHOULD yield chunks as they become available from the underlying API.
        3. MUST handle empty message lists gracefully (either by raising an error or returning a valid response).
        4. MUST correctly map provider-specific errors to henchman.providers.base exceptions:
           - Context overflow -> ContextTooLargeError
        5. MUST yield ToolCall objects in the `tool_calls` field of StreamChunk when the model requests tools.
        6. MUST yield a FinishReason in at least one chunk (usually the last one).
        """
        ...
