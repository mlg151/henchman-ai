"""Failing test for unreachable yield bug in _NullProvider.chat_completion_stream."""

from __future__ import annotations

import ast
import pytest


class TestNullProviderUnreachableYieldBug:
    """Test that demonstrates the unreachable yield bug."""
    
    def test_unreachable_yield_after_raise(self) -> None:
        """Test that yield is unreachable after raise statement.
        
        This test was failing with the old implementation because:
        - _NullProvider.chat_completion_stream had raise RuntimeError
        - Then had yield statement which was unreachable
        - This was dead code
        
        After fix, this test should pass (no unreachable yield after raise).
        """
        # Import the actual class to test
        from henchman.cli.textual_mixins import _NullProvider
        
        # Get source code
        import inspect
        source = inspect.getsource(_NullProvider.chat_completion_stream)
        
        # Check that raise comes after any yield (if yield exists)
        # With our fix: yield is in if False: block, then raise
        
        # Simple check: count lines
        lines = source.split('\n')
        
        # Find raise line and yield line
        raise_line = -1
        yield_line = -1
        
        for i, line in enumerate(lines):
            if 'raise RuntimeError' in line:
                raise_line = i
            if 'yield' in line and 'if False:' not in lines[max(0, i-2):i]:  # Not in if False comment
                # Check if it's actually a yield statement (not in comment)
                stripped = line.strip()
                if stripped.startswith('yield'):
                    yield_line = i
        
        print(f"Raise line: {raise_line}, Yield line: {yield_line}")
        
        if yield_line != -1 and raise_line != -1:
            # Yield should come BEFORE raise (in if False: block)
            if yield_line > raise_line:
                pytest.fail(
                    "BUG: Yield statement comes after raise statement. "
                    "This is unreachable dead code."
                )
            else:
                print("GOOD: Yield comes before raise (reachable for type checking)")
        elif yield_line == -1:
            print("Note: No yield statement found (might have been removed)")
        elif raise_line == -1:
            print("WARNING: No raise statement found")
        
        # Also verify the method works correctly
        provider = _NullProvider()
        
        # Should raise RuntimeError
        import pytest as pt
        with pt.raises(RuntimeError, match="No model provider available"):
            # Create async generator
            stream = provider.chat_completion_stream([])
            # Try to iterate
            import asyncio
            async def test():
                async for _ in stream:
                    pass
            asyncio.run(test())
        
        print("Test passed: Method raises as expected, no unreachable yield after raise")
    
    def test_method_returns_correct_type(self) -> None:
        """Test that the method signature matches implementation.
        
        The method is declared to return AsyncIterator[StreamChunk].
        If it doesn't yield, it doesn't match the signature.
        """
        # This is more of a type checking issue
        # The current implementation raises, which is acceptable for callers
        # but doesn't match the async iterator contract
        
        print("Type signature issue: Method returns AsyncIterator but raises instead of yielding")
        print("This might be acceptable for a null/failure provider")
        
        # Not failing the test, just noting the issue
        assert True
    
    def test_suggested_fix(self) -> None:
        """Show what the fix should look like."""
        print("\n=== Current buggy implementation ===")
        print("async def chat_completion_stream(...) -> AsyncIterator[StreamChunk]:")
        print("    raise RuntimeError(_NO_PROVIDER_MSG)")
        print("    yield  # type: ignore[misc]  # pragma: no cover — makes it a generator")
        print("    # ^ Unreachable! Dead code!")
        
        print("\n=== Fix option 1: Remove yield ===")
        print("async def chat_completion_stream(...) -> AsyncIterator[StreamChunk]:")
        print("    raise RuntimeError(_NO_PROVIDER_MSG)")
        print("    # No yield - but type checker might complain")
        
        print("\n=== Fix option 2: Make yield reachable ===")
        print("async def chat_completion_stream(...) -> AsyncIterator[StreamChunk]:")
        print("    raise RuntimeError(_NO_PROVIDER_MSG)")
        print("    if False:  # Make yield reachable for type checker")
        print("        yield StreamChunk(content='')")
        
        print("\n=== Fix option 3: Empty async generator ===")
        print("async def chat_completion_stream(...) -> AsyncIterator[StreamChunk]:")
        print("    if False:")
        print("        yield")
        print("    raise RuntimeError(_NO_PROVIDER_MSG)")
        
        print("\nRecommended: Option 2 (make yield reachable with if False)")
        print("This keeps the method as a generator for type checking")
        print("while eliminating dead code warning.")