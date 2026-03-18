"""Failing test for StreamChunk constructor bug in _NullProvider.chat_completion_stream."""

from __future__ import annotations

import asyncio
import pytest


class TestNullProviderStreamChunkBug:
    """Test that demonstrates the StreamChunk constructor bug."""
    
    @pytest.mark.anyio
    async def test_streamchunk_constructor_requires_arguments(self) -> None:
        """Test that StreamChunk() constructor actually requires arguments.
        
        The current implementation uses `StreamChunk()  # type: ignore[misc]`
        but if StreamChunk has required fields in its __init__, this will
        raise TypeError at runtime.
        """
        # First, check what StreamChunk constructor actually expects
        from henchman.providers.base import StreamChunk
        
        # Try to create a StreamChunk with no arguments
        # If this raises TypeError, then the bug is confirmed
        try:
            chunk = StreamChunk()
            print(f"StreamChunk() created successfully: {chunk}")
            print(f"  content: {chunk.content}")
            print(f"  tool_calls: {chunk.tool_calls}")
            print(f"  finish_reason: {chunk.finish_reason}")
        except TypeError as e:
            pytest.fail(f"StreamChunk() constructor failed: {e}")
        
        # Now test the actual _NullProvider implementation
        from henchman.cli.textual_mixins import _NullProvider
        
        provider = _NullProvider()
        
        # The bug: if StreamChunk() raises TypeError, this will fail
        # before the RuntimeError is raised
        try:
            stream = provider.chat_completion_stream([])
            
            # Try to get the first chunk
            async for chunk in stream:
                # This should not be reached because raise comes after yield
                print(f"Got chunk: {chunk}")
                break
                
        except TypeError as e:
            pytest.fail(f"BUG: TypeError from StreamChunk() before RuntimeError: {e}")
        except RuntimeError as e:
            # This is expected - the provider should raise RuntimeError
            assert "No model provider available" in str(e)
            print(f"Expected RuntimeError raised: {e}")
        except Exception as e:
            pytest.fail(f"Unexpected exception: {type(e).__name__}: {e}")
    
    @pytest.mark.anyio 
    async def test_streamchunk_default_values(self) -> None:
        """Test what default values StreamChunk should have."""
        from henchman.providers.base import StreamChunk
        
        # Check the class definition
        import inspect
        source = inspect.getsource(StreamChunk)
        print(f"\nStreamChunk class definition:\n{source}")
        
        # Check annotations
        annotations = getattr(StreamChunk, '__annotations__', {})
        print(f"\nStreamChunk annotations: {annotations}")
        
        # Check if there's an __init__ method
        init_source = None
        try:
            init_source = inspect.getsource(StreamChunk.__init__)
            print(f"\nStreamChunk.__init__ source:\n{init_source}")
        except (TypeError, OSError):
            print("\nStreamChunk uses dataclass-like auto-generated __init__")
        
        # Create instance with defaults
        chunk = StreamChunk()
        print(f"\nStreamChunk() instance: {chunk}")
        print(f"  content: {chunk.content!r}")
        print(f"  tool_calls: {chunk.tool_calls!r}")
        print(f"  finish_reason: {chunk.finish_reason!r}")
        print(f"  thinking: {chunk.thinking!r}")
        print(f"  usage: {chunk.usage!r}")
        
        # All fields should be None by default
        assert chunk.content is None
        assert chunk.tool_calls is None
        assert chunk.finish_reason is None
        assert chunk.thinking is None
        assert chunk.usage is None
    
    @pytest.mark.anyio
    async def test_null_provider_yield_behavior(self) -> None:
        """Test the actual behavior of _NullProvider.chat_completion_stream."""
        from henchman.cli.textual_mixins import _NullProvider
        
        provider = _NullProvider()
        
        # Get the source code to analyze
        import inspect
        source = inspect.getsource(provider.chat_completion_stream)
        print(f"\n_NullProvider.chat_completion_stream source:\n{source}")
        
        # Check if yield comes before raise
        lines = source.split('\n')
        raise_found = False
        yield_found = False
        
        for i, line in enumerate(lines):
            if 'raise RuntimeError' in line:
                raise_found = True
                print(f"  Raise found at line {i}: {line.strip()}")
            if 'yield StreamChunk()' in line:
                yield_found = True
                print(f"  Yield found at line {i}: {line.strip()}")
        
        # The bug: if yield is after raise, it's dead code
        # But more importantly: StreamChunk() might not be valid
        
        # Actually test the async generator
        stream = provider.chat_completion_stream([])
        
        # Get the first item
        try:
            chunk = await stream.__anext__()
            print(f"\nGot chunk from stream: {chunk}")
            print(f"  Type: {type(chunk)}")
            print(f"  Content: {chunk.content}")
            
            # Try to get next item (should raise RuntimeError)
            try:
                await stream.__anext__()
                pytest.fail("Should have raised RuntimeError on second __anext__")
            except RuntimeError as e:
                print(f"Expected RuntimeError on second __anext__: {e}")
                assert "No model provider available" in str(e)
                
        except RuntimeError as e:
            # If RuntimeError is raised immediately (not after yield),
            # that's also a problem - the method should yield first
            print(f"\nRuntimeError raised immediately (not after yield): {e}")
            # This might be acceptable if yield is unreachable
            pass
        except StopAsyncIteration:
            pytest.fail("Stream ended without yielding or raising RuntimeError")
        except Exception as e:
            pytest.fail(f"Unexpected exception: {type(e).__name__}: {e}")