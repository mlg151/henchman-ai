"""Test for unused type ignore bug in textual_mixins.py.

The bug: _NullProvider.chat_completion_stream has an unused type: ignore[misc] comment.
"""

from __future__ import annotations

import ast
import pytest


class TestUnusedTypeIgnoreBug:
    """Test for unused type ignore comment bug."""
    
    def test_unused_type_ignore_comment_exists(self) -> None:
        """Test that detects the unused type ignore comment.
        
        This test will FAIL with current implementation because:
        - Line 142 has `type: ignore[misc]` comment
        - After fix, the comment should be removed
        - This test checks for its presence
        """
        # Read the source file
        with open('src/henchman/cli/textual_mixins.py', 'r') as f:
            lines = f.readlines()
        
        # Check line 142 (1-indexed, so index 141 in 0-indexed)
        if len(lines) > 141:
            line_142 = lines[141].rstrip()
            print(f"Line 142: {line_142}")
            
            # Check if line contains type: ignore[misc]
            if 'type: ignore[misc]' in line_142:
                print("✗ BUG: Found unused type: ignore[misc] comment on line 142")
                print("  This comment is unnecessary since StreamChunk() is type-safe")
                print("  The comment could hide real type errors in future changes")
                
                # Also check what's on the line
                if 'yield StreamChunk()' in line_142:
                    print("  The line yields StreamChunk(), which is valid (all fields have defaults)")
                    print("  The type ignore comment should be removed")
                
                # Test fails because bug exists
                pytest.fail("Unused type: ignore[misc] comment found on line 142")
            else:
                print("✓ Good: No type: ignore[misc] comment on line 142")
                # Test passes - bug is fixed
        else:
            pytest.fail("File doesn't have 142 lines")
    
    def test_streamchunk_constructor_is_type_safe(self) -> None:
        """Verify that StreamChunk() is actually type-safe.
        
        This test confirms that the fix is correct - StreamChunk()
        should work without type ignores.
        """
        from henchman.providers.base import StreamChunk
        
        # This should work without type errors
        chunk = StreamChunk()
        assert chunk is not None
        assert chunk.content is None
        assert chunk.tool_calls is None
        assert chunk.finish_reason is None
        assert chunk.thinking is None
        assert chunk.usage is None
        
        # Also test with explicit None values
        chunk2 = StreamChunk(content=None, tool_calls=None, finish_reason=None)
        assert chunk2 is not None
        
        print("✓ StreamChunk() is type-safe - no type ignore needed")
    
    def test_null_provider_stream_works_without_type_ignore(self) -> None:
        """Bug is fixed: _NullProvider.chat_completion_stream raises on first iteration.

        The method is async def, must be awaited to get the async iterable,
        then raises RuntimeError immediately on first __anext__ call.
        """
        from henchman.cli.textual_mixins import _NullProvider
        
        provider = _NullProvider()
        
        import asyncio
        
        async def test():
            # Must await the coroutine to get the async iterable
            gen = await provider.chat_completion_stream([])
            # First iteration should raise RuntimeError immediately
            with pytest.raises(RuntimeError, match="No model provider available"):
                await gen.__anext__()
        
        # Run the async test
        asyncio.run(test())
        
        print("OK: _NullProvider.chat_completion_stream works correctly (raises immediately)")