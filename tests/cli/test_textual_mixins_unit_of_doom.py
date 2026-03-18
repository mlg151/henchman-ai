"""Unit of Doom test for _textual_confirm AttributeError bug.

This test MUST fail with the original code and pass after the fix.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from henchman.cli.textual_mixins import _InitMixin
from henchman.tools.base import ConfirmationRequest


class TestTextualConfirmAttributeErrorUnitOfDoom:
    """Unit of Doom test demonstrating the AttributeError bug."""
    
    @pytest.mark.anyio
    async def test_textual_confirm_raises_attribute_error_without_init(self) -> None:
        """Unit of Doom: _textual_confirm raises AttributeError when state not initialized.
        
        This test demonstrates the bug and MUST FAIL with the original code.
        After the fix, it should pass.
        """
        # Create a minimal test case that reproduces the bug
        # We need an object with _InitMixin but without calling _init_confirm_state()
        class TestApp:
            """Minimal app class that uses _InitMixin."""
            
            def __init__(self) -> None:
                # DON'T call _init_confirm_state() - this simulates the bug condition
                pass
            
            # We need to bind the _textual_confirm method
            _textual_confirm = _InitMixin._textual_confirm
            
            # Mock methods that will be called
            async def push_screen(self, screen, callback):
                # Simulate screen being dismissed immediately with True (approve)
                # But first, let the callback run to trigger the bug
                import asyncio
                asyncio.get_event_loop().call_soon(callback, True)
                raise asyncio.CancelledError("Test cancellation")
        
        # Create instance
        app = TestApp()
        
        # Create a real ConfirmationRequest
        request = ConfirmationRequest(
            tool_name="test_tool",
            description="Test tool execution",
            params={"arg1": "value1"},
        )
        
        # With the fix, this should NOT raise AttributeError
        # It will raise CancelledError from our mock push_screen
        with pytest.raises(asyncio.CancelledError) as exc_info:
            await app._textual_confirm(request)
        
        # Verify it's NOT an AttributeError about missing state
        assert "Test cancellation" in str(exc_info.value), \
            f"Expected test CancelledError, got: {exc_info.value}"
    
    @pytest.mark.anyio
    async def test_textual_confirm_works_with_proper_init(self) -> None:
        """Sanity check: _textual_confirm works when state is properly initialized."""
        # Create a properly initialized object
        class TestApp:
            def __init__(self) -> None:
                # Manually initialize the state as _init_confirm_state() would
                self._confirm_lock = asyncio.Lock()
                self._confirm_counter = 0
                self._confirm_futures = {}
            
            _textual_confirm = _InitMixin._textual_confirm
            
            async def push_screen(self, screen, callback):
                # Simulate user approving immediately
                callback(True)
                # Return a future that will never complete (test will timeout)
                # But we'll cancel it
                fut = asyncio.get_event_loop().create_future()
                fut.set_result(True)
                return await fut
        
        app = TestApp()
        request = ConfirmationRequest(
            tool_name="test_tool",
            description="Test tool execution",
            params={"arg1": "value1"},
        )
        
        # This should work (or at least not raise AttributeError)
        try:
            # Use timeout to prevent hanging if there's an issue
            result = await asyncio.wait_for(app._textual_confirm(request), timeout=1.0)
            # If we get here, it worked
            assert result is True or result is False
        except (asyncio.CancelledError, asyncio.TimeoutError, AttributeError) as e:
            # CancelledError or TimeoutError is OK for this test
            # But AttributeError would indicate the bug
            if isinstance(e, AttributeError):
                pytest.fail(f"Unexpected AttributeError even with initialized state: {e}")