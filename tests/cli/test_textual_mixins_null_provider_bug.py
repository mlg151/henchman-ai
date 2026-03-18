"""Failing test for _NullProvider bug in chat_completion_stream."""

from __future__ import annotations

import asyncio
import pytest


class TestNullProviderBug:
    """Test that demonstrates a real bug in _NullProvider.chat_completion_stream."""
    
    @pytest.mark.anyio
    async def test_null_provider_yields_before_raising(self) -> None:
        """Test that _NullProvider yields a chunk before raising RuntimeError.
        
        This is actually a bug because:
        1. The method yields StreamChunk() first
        2. Then raises RuntimeError on next iteration
        3. Callers might not expect to receive a chunk before the error
        4. The chunk has all None fields, which could confuse callers
        
        The correct behavior should be to raise RuntimeError immediately
        without yielding anything, or to yield an error chunk.
        """
        from henchman.cli.textual_mixins import _NullProvider
        
        provider = _NullProvider()
        
        # Create the async generator
        stream = provider.chat_completion_stream([])
        
        # Get the first item - this should NOT yield a chunk!
        # It should raise RuntimeError immediately
        try:
            chunk = await stream.__anext__()
            # If we get here, we got a chunk instead of an exception
            # This is the bug!
            print(f"BUG: Got chunk instead of exception: {chunk}")
            print(f"  content: {chunk.content}")
            print(f"  tool_calls: {chunk.tool_calls}")
            print(f"  finish_reason: {chunk.finish_reason}")
            
            # Now try to get next item - should raise RuntimeError
            try:
                await stream.__anext__()
                pytest.fail("Should have raised RuntimeError on second __anext__")
            except RuntimeError as e:
                print(f"RuntimeError raised on second __anext__: {e}")
                # This is expected but too late - we already yielded a chunk
                
            # Mark test as failed to show the bug
            pytest.fail(
                "BUG: _NullProvider.chat_completion_stream yields a chunk "
                "before raising RuntimeError. Callers might process the empty "
                "chunk thinking it's valid output."
            )
            
        except RuntimeError as e:
            # This is the CORRECT behavior - raise immediately
            print(f"CORRECT: RuntimeError raised immediately: {e}")
            assert "No model provider available" in str(e)
            return  # Test passes
        
        except StopAsyncIteration:
            pytest.fail("Stream ended without yielding or raising RuntimeError")
        except Exception as e:
            pytest.fail(f"Unexpected exception: {type(e).__name__}: {e}")
    
    @pytest.mark.anyio
    async def test_null_provider_contract_violation(self) -> None:
        """Test that _NullProvider violates async generator contract.
        
        An async generator that yields and then raises is unusual.
        Most callers expect either:
        1. Yield items until StopAsyncIteration
        2. Raise exception immediately (no yields)
        
        The current implementation is a hybrid that could confuse callers.
        """
        from henchman.cli.textual_mixins import _NullProvider
        
        provider = _NullProvider()
        
        # Check what the method signature promises
        import inspect
        sig = inspect.signature(provider.chat_completion_stream)
        print(f"Method signature: {sig}")
        print(f"Return type: {sig.return_annotation}")
        
        # The method returns AsyncIterator[StreamChunk]
        # This suggests it should yield StreamChunk objects
        # But it yields one empty chunk then raises RuntimeError
        # This is confusing API design
        
        # Test with a simple async for loop
        stream = provider.chat_completion_stream([])
        
        chunks = []
        try:
            async for chunk in stream:
                chunks.append(chunk)
        except RuntimeError as e:
            print(f"RuntimeError caught in async for: {e}")
            print(f"Chunks yielded before error: {len(chunks)}")
            
        # The bug: we got 1 chunk before the error
        # This could cause callers to process the empty chunk
        # as if it were valid model output
        if len(chunks) > 0:
            pytest.fail(
                f"BUG: Async for loop received {len(chunks)} chunks "
                "before RuntimeError. Empty chunks could be misinterpreted "
                "as valid model output."
            )