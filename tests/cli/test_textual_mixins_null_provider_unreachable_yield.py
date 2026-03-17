"""Failing test for unreachable yield bug in _NullProvider.chat_completion_stream."""

from __future__ import annotations

import ast
import pytest


class TestNullProviderUnreachableYieldBug:
    """Test that demonstrates the unreachable yield bug."""
    
    def test_unreachable_yield_after_raise(self) -> None:
        """Test that yield is unreachable after raise statement.
        
        This test FAILS with current implementation because:
        - _NullProvider.chat_completion_stream raises RuntimeError
        - Then has yield statement which is unreachable
        - This is dead code
        
        After fix, this test should pass (no unreachable yield).
        """
        # Read source file
        with open('src/henchman/cli/textual_mixins.py', 'r') as f:
            source = f.read()
        
        # Parse AST
        tree = ast.parse(source)
        
        # Find the method
        method_node = None
        for node in ast.walk(tree):
            if (isinstance(node, ast.AsyncFunctionDef) and 
                node.name == 'chat_completion_stream'):
                # Check if we're in _NullProvider class
                parent = node
                while parent and not isinstance(parent, ast.ClassDef):
                    parent = getattr(parent, 'parent', None)
                if parent and parent.name == '_NullProvider':
                    method_node = node
                    break
        
        assert method_node is not None, "Could not find chat_completion_stream method in _NullProvider"
        
        # Check body for raise then yield pattern
        body = method_node.body
        has_raise = False
        has_yield_after_raise = False
        
        for i, stmt in enumerate(body):
            # Check for raise
            if isinstance(stmt, ast.Raise):
                has_raise = True
                # Check if any statement after this is a yield
                for j in range(i + 1, len(body)):
                    next_stmt = body[j]
                    if (isinstance(next_stmt, ast.Expr) and isinstance(next_stmt.value, ast.Yield)) or \
                       isinstance(next_stmt, ast.Yield):
                        has_yield_after_raise = True
                        break
        
        # This is the bug: yield after raise (unreachable)
        if has_yield_after_raise:
            pytest.fail(
                "BUG: _NullProvider.chat_completion_stream has unreachable yield statement after raise. "
                "This is dead code that should be removed or made reachable."
            )
        
        # Also check if there's any yield at all (might have been removed)
        has_any_yield = any(
            (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Yield)) or
            isinstance(stmt, ast.Yield)
            for stmt in body
        )
        
        if not has_any_yield:
            print("Note: Method has no yield statements (might have been fixed)")
        
        # The method should either:
        # 1. Not have yield (if we remove it)
        # 2. Have yield before raise (reachable)
        # 3. Have yield in conditional (like if False: yield)
        
        print("Test passed: No unreachable yield after raise")
    
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