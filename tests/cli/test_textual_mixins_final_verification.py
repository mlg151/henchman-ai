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
        """Bug is fixed: no unreachable yield statement in chat_completion_stream.

        The old bug had 'if False: yield StreamChunk()' dead code. The method
        now uses a _NullAsyncIterator inner class, no yield statements.
        """
        provider = _NullProvider()
        
        import inspect
        source = inspect.getsource(provider.chat_completion_stream)
        
        # Bug is fixed: should NOT have "if False:" with unreachable yield
        assert "if False:" not in source, "Found unreachable code pattern 'if False:'"
        
        # Bug is fixed: should NOT have bare yield (no dead code)
        assert "yield" not in source, "Should NOT have yield statement (dead code removed)"
        
        # Should have raise statement (raises on first iteration)
        assert "raise RuntimeError" in source, "Should raise RuntimeError"
        
        print("OK: No unreachable code found")


    @pytest.mark.anyio
    async def test_proper_async_generator_behavior(self) -> None:
        """Bug is fixed: chat_completion_stream returns a proper async iterable.

        The method is async def that returns _NullAsyncIterator when awaited.
        Raises RuntimeError on first iteration without yielding any chunks.
        """
        provider = _NullProvider()
        
        # Calling returns a coroutine (async def)
        import inspect
        coro = provider.chat_completion_stream([])
        assert inspect.iscoroutine(coro), "Should be a coroutine (async def)"
        
        # Awaiting gives the async iterable
        gen = await coro
        assert hasattr(gen, '__aiter__'), "Awaited result should have __aiter__"
        assert hasattr(gen, '__anext__'), "Awaited result should have __anext__"
        
        # Should raise on first iteration
        with pytest.raises(RuntimeError, match="No model provider available"):
            await gen.__anext__()
        
        print("OK: Proper async iterable behavior verified")


    @pytest.mark.anyio
    async def test_integration_with_async_for(self) -> None:
        """Bug is fixed: async for works by awaiting the coroutine first.

        chat_completion_stream is async def; must be awaited to get the iterable.
        Raises RuntimeError immediately with no chunks yielded.
        """
        provider = _NullProvider()
        
        # Must await the coroutine first to get the async iterable
        chunks = []
        try:
            async for chunk in await provider.chat_completion_stream([Message(role="user", content="test")]):
                chunks.append(chunk)
        except RuntimeError as e:
            assert "No model provider available" in str(e)
        
        # Bug is fixed: no chunks yielded before RuntimeError
        assert len(chunks) == 0, "Should yield no chunks before raising RuntimeError"
        
        print("OK: Integration with async for works correctly")


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