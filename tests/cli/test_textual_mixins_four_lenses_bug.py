"""Test for Four Lenses bug in textual_mixins.py.

This test demonstrates a real bug found through the Four Lenses analysis.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch
import pytest

from henchman.cli.textual_mixins import _NullProvider
from henchman.providers.base import Message, StreamChunk


class TestNullProviderBug:
    """Test the bug in _NullProvider.chat_completion_stream."""
    
    @pytest.mark.anyio
    async def test_null_provider_chat_completion_stream_returns_wrong_type(self) -> None:
        """Test that _NullProvider.chat_completion_stream has incorrect type handling.
        
        The bug: The method returns _NullAsyncIterator but __aiter__ method
        has incorrect type annotation and may not properly implement the
        async iterator protocol.
        """
        provider = _NullProvider()
        
        # Call chat_completion_stream
        messages = [Message(role="user", content="test")]
        stream = await provider.chat_completion_stream(messages)
        
        # Get async iterator
        aiter_result = stream.__aiter__()
        
        # The bug: __aiter__ returns _NullAsyncIterator but type annotation
        # says it returns _NullAsyncIterator, not AsyncIterator[StreamChunk]
        # This is a type safety violation (Phase 1 of Four Lenses)
        
        # Try to get next item - should raise RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            await aiter_result.__anext__()
        
        assert "No model provider available" in str(exc_info.value)
    
    @pytest.mark.anyio
    async def test_null_provider_chat_completion_stream_called_twice(self) -> None:
        """Test edge case: calling the stream twice.
        
        Potential bug: Each call creates a new _NullAsyncIterator instance,
        but they might share state incorrectly.
        """
        provider = _NullProvider()
        messages = [Message(role="user", content="test")]
        
        # Call twice
        stream1 = await provider.chat_completion_stream(messages)
        stream2 = await provider.chat_completion_stream(messages)
        
        # They should be different instances
        assert stream1 is not stream2
        
        # Both should raise RuntimeError
        with pytest.raises(RuntimeError):
            await stream1.__aiter__().__anext__()
        
        with pytest.raises(RuntimeError):
            await stream2.__aiter__().__anext__()