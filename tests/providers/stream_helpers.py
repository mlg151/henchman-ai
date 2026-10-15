"""SDK-compatible streaming responses for offline provider tests."""

from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any


class SDKResponse:
    """Expose the OpenAI SDK's async close contract around generated chunks."""

    def __init__(self, chunks: AsyncGenerator[Any]) -> None:
        self._chunks = chunks

    def __aiter__(self) -> AsyncIterator[Any]:
        return self._chunks

    async def close(self) -> None:
        await self._chunks.aclose()
