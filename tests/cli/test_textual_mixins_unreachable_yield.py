"""Test for unreachable yield bug in _NullProvider.chat_completion_stream."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from henchman.cli.textual_mixins import _NullProvider


def test_null_provider_chat_completion_stream_no_unreachable_yield() -> None:
    """Test that _NullProvider.chat_completion_stream has no unreachable yield.
    
    This test will FAIL on the original code because it has `if False: yield StreamChunk()`
    which is unreachable code. After fixing, the test should PASS.
    """
    # Get the source code of the method
    source = inspect.getsource(_NullProvider.chat_completion_stream)
    
    # Dedent the source code
    import textwrap
    source = textwrap.dedent(source)
    
    # Parse the AST
    tree = ast.parse(source)
    
    # Check for yield statements
    yield_statements = []
    
    class YieldVisitor(ast.NodeVisitor):
        def visit_Yield(self, node: ast.Yield) -> None:
            yield_statements.append(node)
    
    YieldVisitor().visit(tree)
    
    # If there are yield statements, check if they're reachable
    if yield_statements:
        # Check for if False: pattern
        # Look for If nodes with test being Constant(value=False)
        unreachable_yields = []
        
        class IfFalseVisitor(ast.NodeVisitor):
            def visit_If(self, node: ast.If) -> None:
                # Check if test is Constant(value=False)
                if isinstance(node.test, ast.Constant) and node.test.value is False:
                    # Check if this If contains any yield statements
                    for yield_node in yield_statements:
                        # Simple check: if yield is in the if body
                        # This is approximate but works for our case
                        if (node.lineno <= yield_node.lineno <= node.end_lineno):
                            unreachable_yields.append(yield_node)
                self.generic_visit(node)
        
        IfFalseVisitor().visit(tree)
        
        # Fail if there are unreachable yields
        if unreachable_yields:
            pytest.fail(
                f"_NullProvider.chat_completion_stream has {len(unreachable_yields)} "
                f"unreachable yield statement(s) inside 'if False:' blocks. "
                f"This is dead code that should be removed."
            )
    
    # Also check that the method still raises RuntimeError
    provider = _NullProvider()
    
    # This should raise RuntimeError when iterated
    async def test_raises() -> None:
        with pytest.raises(RuntimeError, match="No model provider available"):
            stream = await provider.chat_completion_stream([])
            async for _ in stream:
                pass
    
    # Run the async test
    import asyncio
    asyncio.run(test_raises())


if __name__ == "__main__":
    # Run the test
    test_null_provider_chat_completion_stream_no_unreachable_yield()
    print("Test passed!")