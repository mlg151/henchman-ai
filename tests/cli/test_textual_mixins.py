"""Tests for Henchman CLI textual mixins."""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from typing import AsyncIterator, List

from henchman.cli.textual_mixins import _InitMixin, _NullProvider
from henchman.tools.base import ConfirmationRequest
from henchman.providers.base import Message, StreamChunk
import inspect

class TestTextualConfirmAttributeErrorBug:
    """Test that _textual_confirm handles initialization state correctly."""

    @pytest.mark.anyio
    async def test_textual_confirm_without_init_raises_runtime_error(self) -> None:
        """Test _textual_confirm raises RuntimeError when state not initialized.
        
        This prevents AttributeError by checking initialization first.
        """
        # Create an instance without calling _init_confirm_state
        obj = MagicMock(spec=_InitMixin)
        
        # Don't initialize the state attributes
        # obj._confirm_lock, obj._confirm_counter, obj._confirm_futures don't exist
        
        # Create a mock request
        request = MagicMock(spec=ConfirmationRequest)
        request.tool_name = "test_tool"
        request.arguments = {}
        request.kind = "EXECUTE"
        
        # Get the method bound to our mock object
        # We can't bind easily, so we call it as unbound method passing self
        confirm_method = _InitMixin._textual_confirm
        
        # This should raise RuntimeError because initialization check fails
        with pytest.raises(RuntimeError) as exc_info:
            await confirm_method(obj, request)
        
        # Verify it's the expected error message
        assert "_textual_confirm called before _init_confirm_state()" in str(exc_info.value)
    
    @pytest.mark.anyio 
    async def test_textual_confirm_with_init_works(self) -> None:
        """Test _textual_confirm works when state is properly initialized."""
        # Create an instance
        obj = MagicMock(spec=_InitMixin)
        
        # Initialize the state as the real code would
        obj._confirm_lock = asyncio.Lock()
        obj._confirm_counter = 0
        obj._confirm_futures = {}
        
        # Mock the screen pushing (will raise CancelledError to exit early)
        obj.push_screen = MagicMock(side_effect=asyncio.CancelledError())
        
        # Create a mock request
        request = MagicMock(spec=ConfirmationRequest)
        request.tool_name = "test_tool"
        request.arguments = {}
        request.kind = "EXECUTE"
        
        # Get the method
        confirm_method = _InitMixin._textual_confirm
        
        # This should raise CancelledError (from our mock), not AttributeError
        with pytest.raises(asyncio.CancelledError):
            await confirm_method(obj, request)

import ast
import textwrap

class TestTextualConfirmCallbackRaceBug:
    """Test that demonstrates the race condition in _textual_confirm callback."""
    
    @pytest.mark.anyio
    async def test_callback_creates_task_for_lock_race(self) -> None:
        """Test that _callback does NOT create a task for lock acquisition.
        
        Fix verification: _callback should not try to acquire async lock from sync context.
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        # Get the actual source code
        source = inspect.getsource(_InitMixin._textual_confirm)
        
        # The fix: _callback should not try to acquire async lock from sync context
        # It should just pop directly without lock/task creation
        assert 'asyncio.create_task(remove_from_dict())' not in source, (
            "Fix verification: _callback should NOT use asyncio.create_task() for lock acquisition"
        )

class TestCancelledErrorBug:
    """Test that asyncio.CancelledError is handled correctly."""

    @pytest.mark.anyio
    async def test_cancelled_error_propagated(self) -> None:
        """Test that asyncio.CancelledError is propagated correctly."""
        # Create a mock mixin instance
        mixin = MagicMock(spec=_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 0
        mixin._confirm_lock = asyncio.Lock()
        
        # Mock push_screen to raise CancelledError
        mixin.push_screen = AsyncMock(side_effect=asyncio.CancelledError)
        
        # We need to bind the method to the object
        confirm_method = _InitMixin._textual_confirm
        
        request = ConfirmationRequest(
            tool_name="test", description="test", params={}, risk_level="low"
        )
        
        # Should propagate CancelledError
        with pytest.raises(asyncio.CancelledError):
            await confirm_method(mixin, request)

class TestTextualConfirmCleanupRaceBug:
    """Test that demonstrates the race condition in _cleanup_confirm_futures."""
    
    @pytest.mark.anyio
    async def test_cleanup_race_condition(self) -> None:
        """Test that cleanup has NO race condition between cancel() and pop().
        
        Fix verification: pop() should be called BEFORE cancel().
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        source = inspect.getsource(_InitMixin._cleanup_confirm_futures)
        
        assert 'future.cancel()' in source, "Found cancel() call"
        assert 'futures_dict.pop(req_id, None)' in source or 'self._confirm_futures.pop(req_id, None)' in source, "Found pop() call"
        
        # Check order: pop() comes before cancel()
        # Note: we check for the pop inside the loop
        # We look for the loop variable 'req_id' being popped
        
        # Simple heuristic: find all occurrences
        pop_indices = [i for i in range(len(source)) if source.startswith('futures_dict.pop', i) or source.startswith('self._confirm_futures.pop', i)]
        cancel_indices = [i for i in range(len(source)) if source.startswith('future.cancel()', i)]
        
        # In the loop, pop should precede cancel
        # This is a bit loose but sufficient for regression testing the fix pattern
        # The fix is: future = dict.pop(); if future: future.cancel()
        
        # Let's check for the exact fix pattern
        assert "future = futures_dict.pop(req_id, None)" in source or "future = self._confirm_futures.pop(req_id, None)" in source
        
        # And ensure cancel happens on that future object
        assert "future.cancel()" in source

class TestNullProviderDeadCodeBug:
    """Test that demonstrates the dead code bug in _NullProvider."""
    
    def test_no_unreachable_code_in_chat_completion_stream(self) -> None:
        """Test that chat_completion_stream has no unreachable yield statements."""
        
        # Get source code and dedent it
        source = inspect.getsource(_NullProvider.chat_completion_stream)
        source = textwrap.dedent(source)
        
        # Parse AST to find unreachable code
        tree = ast.parse(source)
        
        # Look for If nodes with test=Constant(value=False)
        unreachable_yields = []
        
        class DeadCodeFinder(ast.NodeVisitor):
            def visit_If(self, node: ast.If) -> None:
                # Check if this is 
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
            f"Found {len(unreachable_yields)} unreachable yield statements. "
            f"This is dead code that should be removed."
        )
    
    @pytest.mark.anyio
    async def test_chat_completion_stream_raises_immediately(self) -> None:
        """Test that chat_completion_stream raises RuntimeError immediately."""
        provider = _NullProvider()
        
        # Should be an async iterator
        stream = provider.chat_completion_stream([Message(role="user", content="test")])
        assert isinstance(stream, AsyncIterator)
        
        with pytest.raises(RuntimeError, match="No model provider available"):
            async for _ in stream:
                pytest.fail("Should not yield anything before raising")


import ast
import inspect
import textwrap

class TestTextualConfirmCallbackRaceBug:
    """Test that demonstrates the race condition in _textual_confirm callback."""
    
    @pytest.mark.anyio
    async def test_callback_creates_task_for_lock_race(self) -> None:
        """Test that _callback does NOT create a task for lock acquisition.
        
        Fix verification: _callback should not try to acquire async lock from sync context.
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        # Get the actual source code
        source = inspect.getsource(_InitMixin._textual_confirm)
        
        # The fix: _callback should not try to acquire async lock from sync context
        # It should just pop directly without lock/task creation
        assert 'asyncio.create_task(remove_from_dict())' not in source, (
            "Fix verification: _callback should NOT use asyncio.create_task() for lock acquisition"
        )

class TestCancelledErrorBug:
    """Test that asyncio.CancelledError is handled correctly."""

    @pytest.mark.anyio
    async def test_cancelled_error_propagated(self) -> None:
        """Test that asyncio.CancelledError is propagated correctly."""
        # Create a mock mixin instance
        mixin = MagicMock(spec=_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 0
        mixin._confirm_lock = asyncio.Lock()
        
        # Mock push_screen to raise CancelledError
        # Note: side_effect=exception raises it when called
        mixin.push_screen = AsyncMock(side_effect=asyncio.CancelledError)
        
        # We need to bind the method to the object
        # Using the unbound method with explicit self
        confirm_method = _InitMixin._textual_confirm
        
        request = ConfirmationRequest(
            tool_name="test", description="test", params={}, risk_level="low"
        )
        
        # Should propagate CancelledError
        with pytest.raises(asyncio.CancelledError):
            await confirm_method(mixin, request)

class TestTextualConfirmCleanupRaceBug:
    """Test that demonstrates the race condition in _cleanup_confirm_futures."""
    
    @pytest.mark.anyio
    async def test_cleanup_race_condition(self) -> None:
        """Test that cleanup has NO race condition between cancel() and pop().
        
        Fix verification: pop() should be called BEFORE cancel().
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        source = inspect.getsource(_InitMixin._cleanup_confirm_futures)
        
        # Check basic elements are present
        assert 'future.cancel()' in source, "Found cancel() call"
        
        # Check for the fix pattern
        # The fix is: future = dict.pop(); if future: future.cancel()
        assert "future = futures_dict.pop(req_id, None)" in source or "future = self._confirm_futures.pop(req_id, None)" in source, "Fix pattern not found (pop before cancel)"
        
        # Check that we iterate over keys, not items
        assert "keys = list(futures_dict.keys())" in source or "keys = list(self._confirm_futures.keys())" in source, "Safe iteration pattern not found"

class TestNullProviderDeadCodeBug:
    """Test that demonstrates the dead code bug in _NullProvider."""
    
    def test_no_unreachable_code_in_chat_completion_stream(self) -> None:
        """Test that chat_completion_stream has no unreachable yield statements."""
        
        # Get source code and dedent it
        source = inspect.getsource(_NullProvider.chat_completion_stream)
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
            f"Found {len(unreachable_yields)} unreachable yield statements. "
            f"This is dead code that should be removed."
        )
    
    @pytest.mark.anyio
    async def test_chat_completion_stream_raises_immediately(self) -> None:
        """Test that chat_completion_stream raises RuntimeError immediately."""
        provider = _NullProvider()
        
        # Should be an async iterator
        stream = provider.chat_completion_stream([Message(role="user", content="test")])
        assert isinstance(stream, AsyncIterator)
        
        with pytest.raises(RuntimeError, match="No model provider available"):
            async for _ in stream:
                pytest.fail("Should not yield anything before raising")

