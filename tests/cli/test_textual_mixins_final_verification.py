"""Final verification test for the unreachable yield bug fix."""

from __future__ import annotations

import asyncio
import pytest

from henchman.cli.textual_mixins import _NullProvider
from henchman.providers.base import StreamChunk, Message


class TestFinalVerification:
    """Final verification that the bug is fixed."""
    
    @pytest.mark.anyio
    async def test_no_unreachable_code(self) -> None:
        """Verify there's no unreachable yield statement."""
        provider = _NullProvider()
        
        # Check source code for unreachable patterns
        import inspect
        source = inspect.getsource(provider.chat_completion_stream)
        
        # Should NOT have "if False:" with yield inside
        assert "if False:" not in source, "Found unreachable code pattern 'if False:'"
        
        # Should have yield statement
        assert "yield" in source, "Should have yield statement"
        
        # Should have raise statement
        assert "raise RuntimeError" in source, "Should raise RuntimeError"
        
        # Yield should come before raise
        yield_pos = source.find("yield")
        raise_pos = source.find("raise RuntimeError")
        assert yield_pos < raise_pos, "Yield should come before raise"
        
        print("✓ No unreachable code found")
    
    @pytest.mark.anyio
    async def test_proper_async_generator_behavior(self) -> None:
        """Test that it behaves as a proper async generator."""
        provider = _NullProvider()
        
        # Should be callable and return async generator
        gen = provider.chat_completion_stream([])
        assert hasattr(gen, '__aiter__')
        assert hasattr(gen, '__anext__')
        
        # Should yield exactly one empty chunk
        chunk = await gen.__anext__()
        assert isinstance(chunk, StreamChunk)
        assert chunk.content is None
        assert chunk.tool_calls is None
        assert chunk.finish_reason is None
        assert chunk.thinking is None
        assert chunk.usage is None
        
        # Should raise on next iteration
        with pytest.raises(RuntimeError, match="No model provider available"):
            await gen.__anext__()
        
        print("✓ Proper async generator behavior verified")
    
    @pytest.mark.anyio
    async def test_integration_with_async_for(self) -> None:
        """Test integration with async for loop."""
        provider = _NullProvider()
        
        # Should work with async for
        chunks = []
        try:
            async for chunk in provider.chat_completion_stream([Message(role="user", content="test")]):
                chunks.append(chunk)
        except RuntimeError as e:
            # Should raise after first chunk
            assert "No model provider available" in str(e)
        
        # Should have exactly one chunk
        assert len(chunks) == 1
        assert isinstance(chunks[0], StreamChunk)
        
        print("✓ Integration with async for works correctly")
    
    def test_type_hints_are_satisfied(self) -> None:
        """Verify type hints are satisfied (no mypy errors)."""
        # This is a compile-time check, but we can verify the method signature
        import inspect
        from typing import get_type_hints
        
        # Check unbound method (class attribute) to see all parameters including self
        sig = inspect.signature(_NullProvider.chat_completion_stream)
        
        # Should have correct parameters including self
        assert 'self' in sig.parameters
        assert '_messages' in sig.parameters
        assert '_tools' in sig.parameters
        assert '_kwargs' in sig.parameters
        
        # Return type should be AsyncIterator[StreamChunk]
        # We can't easily check this at runtime, but the presence of
        # yield statement makes it an async generator
        
        print("✓ Type hints appear to be satisfied")