"""Test for dead code bug in _NullProvider.chat_completion_stream."""

from __future__ import annotations

import ast
import inspect
import pytest


class TestNullProviderDeadCodeBug:
    """Test that demonstrates the dead code bug in _NullProvider."""
    
    def _make_null_provider(self):
        """Create a _NullProvider instance."""
        from henchman.cli.textual_mixins import _NullProvider
        return _NullProvider()
    
    def test_no_unreachable_code_in_chat_completion_stream(self) -> None:
        """Test that chat_completion_stream has no unreachable yield statements.
        
        This test FAILS with the current implementation because:
        - _NullProvider.chat_completion_stream has `if False: yield StreamChunk()`
        - The `yield` statement is unreachable (dead code)
        - This violates clean code principles
        
        After fix, this test should PASS (no unreachable yield).
        """
        from henchman.cli.textual_mixins import _NullProvider
        
        # Get source code and dedent it
        source = inspect.getsource(_NullProvider.chat_completion_stream)
        
        # Remove common leading whitespace
        import textwrap
        source = textwrap.dedent(source)
        
        # Parse AST to find unreachable code
        tree = ast.parse(source)
        
        # Look for If nodes with test=Constant(value=False)
        unreachable_yields = []
        
        class DeadCodeFinder(ast.NodeVisitor):
            def visit_If(self, node: ast.If) -> None:
                # Check if this is `if False:`
                if (isinstance(node.test, ast.Constant) and 
                    node.test.value is False):
                    # Check for yield statements inside
                    for stmt in node.body:
                        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Yield):
                            unreachable_yields.append((node.lineno, node.col_offset))
                self.generic_visit(node)
        
        finder = DeadCodeFinder()
        finder.visit(tree)
        
        # The test FAILS if there are unreachable yields
        assert len(unreachable_yields) == 0, (
            f"Found {len(unreachable_yields)} unreachable yield statements in "
            f"_NullProvider.chat_completion_stream. This is dead code that should be removed. "
            f"Locations: {unreachable_yields}"
        )
    
    @pytest.mark.anyio
    async def test_chat_completion_stream_raises_immediately(self) -> None:
        """Test that chat_completion_stream raises RuntimeError immediately.
        
        This should still work after the fix.
        """
        provider = self._make_null_provider()
        with pytest.raises(RuntimeError, match="No model provider available"):
            stream = provider.chat_completion_stream([])
            # Try to iterate - should raise immediately
            async for _ in stream:
                pytest.fail("Should not yield anything before raising")
    
    def test_method_still_async_generator_after_fix(self) -> None:
        """Test that the method is still an async generator after fix.
        
        Even after removing dead code, the method should still be
        recognized as an async generator for type checking.
        """
        from henchman.cli.textual_mixins import _NullProvider
        import asyncio
        
        provider = _NullProvider()
        
        # Check it's a coroutine function
        import inspect
        result = provider.chat_completion_stream([])
        
        # Should be an async generator
        assert inspect.isasyncgen(result), (
            "chat_completion_stream should return an async generator"
        )