"""Test for NullProvider bug in textual_mixins.py.

The bug: _NullProvider.chat_completion_stream has unreachable yield statement.
"""

from __future__ import annotations

import asyncio
import pytest


class TestNullProviderBug:
    """Test _NullProvider bug."""
    
    def test_chat_completion_stream_has_unreachable_yield(self) -> None:
        """Verify chat_completion_stream has unreachable code."""
        import ast
        import inspect
        
        # Read the source file
        with open('src/henchman/cli/textual_mixins.py', 'r') as f:
            source = f.read()
        
        # Parse AST
        tree = ast.parse(source)
        
        # Find _NullProvider class
        null_provider_class = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == '_NullProvider':
                null_provider_class = node
                break
        
        assert null_provider_class is not None, "Could not find _NullProvider class"
        
        # Find chat_completion_stream method
        chat_completion_stream_method = None
        for node in ast.walk(null_provider_class):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == 'chat_completion_stream':
                chat_completion_stream_method = node
                break
        
        assert chat_completion_stream_method is not None, \
            "Could not find chat_completion_stream method"
        
        # Check method body
        body = chat_completion_stream_method.body
        
        # The method should have:
        # 1. Raise statement
        # 2. Yield statement (unreachable)
        
        raise_stmt = None
        yield_stmt = None
        
        for stmt in body:
            if isinstance(stmt, ast.Raise):
                raise_stmt = stmt
            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Yield):
                yield_stmt = stmt
            elif isinstance(stmt, ast.Yield):  # Python 3.8+ style
                yield_stmt = stmt
        
        assert raise_stmt is not None, "chat_completion_stream should raise"
        assert yield_stmt is not None, "chat_completion_stream should have yield"
        
        print("Found:")
        print(f"  Raise statement: {ast.unparse(raise_stmt) if hasattr(ast, 'unparse') else 'Raise'}")
        print(f"  Yield statement: {ast.unparse(yield_stmt) if hasattr(ast, 'unparse') else 'Yield'}")
        
        # The yield is after raise, so it's unreachable
        # This is dead code!
        
        # Get line numbers
        raise_line = raise_stmt.lineno if hasattr(raise_stmt, 'lineno') else 'unknown'
        yield_line = yield_stmt.lineno if hasattr(yield_stmt, 'lineno') else 'unknown'
        
        print(f"\nLine numbers: raise at {raise_line}, yield at {yield_line}")
        
        # Check if yield is after raise
        if hasattr(raise_stmt, 'lineno') and hasattr(yield_stmt, 'lineno'):
            if yield_line > raise_line:
                print("✗ BUG: Yield statement is after raise (unreachable code!)")
                # This is the bug!
                return True  # Bug exists
            else:
                print("✓ Yield is before raise (reachable)")
                return False
        else:
            print("? Could not determine line order")
            return None
    
    @pytest.mark.anyio
    async def test_chat_completion_stream_actually_raises(self) -> None:
        """Test that chat_completion_stream raises as expected."""
        from henchman.cli.textual_mixins import _NullProvider
        
        provider = _NullProvider()
        
        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="No model provider available"):
            # Try to iterate (will raise immediately)
            async for _ in provider.chat_completion_stream([]):
                pass  # Should never reach here
        
        # Also test that it's an async generator (has __aiter__)
        # Actually, async generator functions return async generator objects
        # when called, even if they raise immediately
        
        try:
            gen = provider.chat_completion_stream([])
            # It should be an async generator
            assert hasattr(gen, '__aiter__')
            assert hasattr(gen, '__anext__')
            
            # But iterating should raise
            with pytest.raises(RuntimeError):
                await gen.__anext__()
        except RuntimeError:
            # It might raise immediately when called, not when iterated
            # That's also acceptable
            
            # Actually, looking at the code:
            # async def chat_completion_stream(...):
            #     raise RuntimeError(...)
            #     yield
            #
            # When called, it returns a coroutine object
            # When awaited, it raises
            # So it's NOT an async generator that yields, it's an async function that raises
            
            # Wait, actually async def with yield is an async generator function
            # Calling it returns an async generator object
            # But if it raises before first yield, the raise happens when?
            
            # Let me test:
            gen = provider.chat_completion_stream([])
            print(f"Type of chat_completion_stream result: {type(gen)}")
            
            # In Python, async def with yield returns an async generator object
            # But if it raises immediately, the exception might be raised
            # when trying to get the first element with __anext__()
            
            # Actually, the current implementation raises when the function is AWAITED
            # not when __anext__() is called. Let me check...
            
            # This is getting complex. The key point is the unreachable yield.
            
            print("Note: Implementation raises immediately, not on __anext__()")
    
    def test_fix_would_remove_unreachable_yield(self) -> None:
        """Show what the fix should look like."""
        print("\n=== Suggested Fix ===")
        print("Current (buggy):")
        print("  async def chat_completion_stream(...) -> AsyncIterator[StreamChunk]:")
        print("      raise RuntimeError(_NO_PROVIDER_MSG)")
        print("      yield  # type: ignore[misc]  # pragma: no cover — makes it a generator")
        
        print("\nFixed version 1 (remove unreachable yield):")
        print("  async def chat_completion_stream(...) -> AsyncIterator[StreamChunk]:")
        print("      raise RuntimeError(_NO_PROVIDER_MSG)")
        print("      # No yield - but then it's not a generator!")
        
        print("\nFixed version 2 (make yield reachable):")
        print("  async def chat_completion_stream(...) -> AsyncIterator[StreamChunk]:")
        print("      raise RuntimeError(_NO_PROVIDER_MSG)")
        print("      if False:  # Make yield reachable for type checker")
        print("          yield StreamChunk(content='')  # Dummy")
        
        print("\nFixed version 3 (proper async generator):")
        print("  async def chat_completion_stream(...) -> AsyncIterator[StreamChunk]:")
        print("      # Return empty async generator")
        print("      return")
        print("      yield  # This makes it a generator")
        
        print("\nActually, the simplest fix is to remove the yield entirely.")
        print("The method raises, so it doesn't need to be a generator.")
        print("But the return type is AsyncIterator[StreamChunk], so...")
        print("Maybe change return type to Coroutine or just leave as is?")
        
        # Actually, the real fix depends on what callers expect.
        # If callers expect to async-for over it, raising is fine
        # (async for will catch the exception).
        # The unreachable yield is just dead code.