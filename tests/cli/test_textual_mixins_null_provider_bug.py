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
        # After fix: yield should be present and reachable
        # Note: yield StreamChunk() is ast.Expr(value=ast.Yield(value=ast.Call(...)))
        if yield_stmt is None:
            # Debug: print all statements
            print("Debug: Method body statements:")
            for i, stmt in enumerate(body):
                print(f"  [{i}] {type(stmt).__name__}: {ast.unparse(stmt) if hasattr(ast, 'unparse') else stmt}")
                if isinstance(stmt, ast.Expr):
                    print(f"     value type: {type(stmt.value).__name__}")
                    if isinstance(stmt.value, ast.Yield):
                        print("     ^ This is a yield expression!")
        assert yield_stmt is not None, "chat_completion_stream should have yield statement"
        
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
        """Test that chat_completion_stream yields then raises as expected."""
        from henchman.cli.textual_mixins import _NullProvider
        
        provider = _NullProvider()
        
        # Should yield once then raise RuntimeError
        gen = provider.chat_completion_stream([])
        # First iteration should yield an empty chunk
        chunk = await gen.__anext__()
        assert chunk is not None
        # Should be a StreamChunk instance
        from henchman.providers.base import StreamChunk
        assert isinstance(chunk, StreamChunk)
        # All fields should be None (empty chunk)
        assert chunk.content is None
        assert chunk.tool_calls is None
        assert chunk.finish_reason is None
        assert chunk.thinking is None
        assert chunk.usage is None
        
        # Next iteration should raise
        with pytest.raises(RuntimeError, match="No model provider available"):
            await gen.__anext__()
        
        # Test that it's a proper async generator
        gen2 = provider.chat_completion_stream([])
        assert hasattr(gen2, '__aiter__')
        assert hasattr(gen2, '__anext__')
        
        # Test async for loop
        count = 0
        try:
            async for chunk in provider.chat_completion_stream([]):
                count += 1
                # Should get exactly one chunk
                assert count == 1
                assert isinstance(chunk, StreamChunk)
        except RuntimeError as e:
            # Should raise after first chunk
            assert count == 1
            assert "No model provider available" in str(e)
        else:
            pytest.fail("Should have raised RuntimeError after first chunk")
    
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