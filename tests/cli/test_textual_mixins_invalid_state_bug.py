"""Test for InvalidStateError bug in textual_mixins.py _textual_confirm method.

This test demonstrates the bug where future.cancel() is called on an already
completed future, causing asyncio.InvalidStateError.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

from henchman.tools.base import ConfirmationRequest


class TestTextualConfirmInvalidStateBug:
    """Test that demonstrates the InvalidStateError bug in _textual_confirm."""
    
    @pytest.mark.anyio
    async def test_future_cancel_on_completed_future_raises(self) -> None:
        """Test that future.cancel() raises InvalidStateError on completed future.
        
        This is the core bug: future.cancel() is NOT idempotent when the future
        is already done (has a result or exception).
        """
        loop = asyncio.get_running_loop()
        
        # Create a future and complete it
        future = loop.create_future()
        future.set_result(True)
        assert future.done()
        assert not future.cancelled()
        
        # This should raise InvalidStateError
        with pytest.raises(asyncio.InvalidStateError) as exc_info:
            future.cancel()
        
        print(f"✓ future.cancel() raises InvalidStateError on completed future: {exc_info.value}")
    
    @pytest.mark.anyio
    async def test_race_callback_and_exception_causes_bug(self) -> None:
        """Test the race condition between callback and exception handler.
        
        Simulates the scenario where:
        1. User responds to confirmation dialog (_callback completes future)
        2. Exception occurs in _textual_confirm at same time
        3. Exception handler tries to cancel already-completed future
        4. InvalidStateError is raised
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        # Create mixin instance
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 0
        mixin._confirm_lock = asyncio.Lock()
        
        # Mock the push_screen to immediately call callback
        mock_request = MagicMock(spec=ConfirmationRequest)
        mock_request.tool_name = "test_tool"
        mock_request.arguments = {"arg": "value"}
        
        # Track if InvalidStateError was raised
        invalid_state_error_raised = False
        
        async def mock_push_screen(screen, callback):
            # Simulate user immediately responding "Yes"
            callback(True)
            # Then raise an exception to trigger exception handler
            raise RuntimeError("Simulated error during confirmation")
        
        # Patch push_screen
        with patch.object(mixin, 'push_screen', mock_push_screen):
            try:
                # Call _textual_confirm
                result = await mixin._textual_confirm(mock_request)
                print(f"Unexpected success: got result {result}")
            except RuntimeError as e:
                print(f"Expected RuntimeError caught: {e}")
                # Check if InvalidStateError was raised internally
                import traceback
                tb = traceback.format_exc()
                if "InvalidStateError" in tb:
                    invalid_state_error_raised = True
                    print("✓ Bug reproduced: InvalidStateError raised internally")
                else:
                    print("✗ Bug NOT reproduced: No InvalidStateError in traceback")
        
        # The bug should cause InvalidStateError
        assert invalid_state_error_raised, \
            "Expected InvalidStateError to be raised when future.cancel() is called on completed future"
    
    @pytest.mark.anyio 
    async def test_fix_prevents_invalid_state_error(self) -> None:
        """Test that the fix (checking future.done()) prevents the error.
        
        This test shows what the fixed code should do.
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        # Create mixin instance
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 0
        mixin._confirm_lock = asyncio.Lock()
        
        # Track calls to check we're testing the right thing
        future_cancel_called_on_done_future = False
        
        # Monkey-patch future.cancel to track calls
        original_cancel = asyncio.Future.cancel
        
        def tracked_cancel(future_self):
            if future_self.done():
                nonlocal future_cancel_called_on_done_future
                future_cancel_called_on_done_future = True
                # In the buggy code, this would raise InvalidStateError
                # But we're testing the fix, so we should check done() first
                return  # Don't call cancel on done future
            return original_cancel(future_self)
        
        mock_request = MagicMock(spec=ConfirmationRequest)
        mock_request.tool_name = "test_tool"
        mock_request.arguments = {"arg": "value"}
        
        async def mock_push_screen(screen, callback):
            # Simulate user immediately responding
            callback(True)
            # Then raise exception
            raise RuntimeError("Simulated error")
        
        with patch.object(mixin, 'push_screen', mock_push_screen), \
             patch.object(asyncio.Future, 'cancel', tracked_cancel):
            
            try:
                result = await mixin._textual_confirm(mock_request)
                print(f"Unexpected success: {result}")
            except RuntimeError:
                print("Expected RuntimeError caught")
        
        # With the fix, cancel should NOT be called on done future
        assert not future_cancel_called_on_done_future, \
            "future.cancel() was called on a done future - fix not working"
        
        print("✓ Fix verified: future.cancel() not called on done future")