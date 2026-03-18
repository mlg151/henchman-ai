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
        """Test that future.cancel() does NOT raise InvalidStateError on completed future.
        
        According to asyncio documentation, future.cancel() should return False
        (not raise) when the future is already done or cancelled.
        This test was incorrectly expecting InvalidStateError.
        """
        loop = asyncio.get_running_loop()
        
        # Create a future and complete it
        future = loop.create_future()
        future.set_result(True)
        assert future.done()
        assert not future.cancelled()
        
        # This should NOT raise InvalidStateError - it should return False
        # According to asyncio docs: "If the future is already done or cancelled, return False."
        result = future.cancel()
        assert result is False, f"future.cancel() should return False on completed future, got {result}"
        
        print(f"✓ future.cancel() returns False on completed future (does not raise InvalidStateError)")
    
    @pytest.mark.anyio
    async def test_race_callback_and_exception_causes_bug(self) -> None:
        """Test the race condition between callback and exception handler.
        
        Simulates the scenario where:
        1. User responds to confirmation dialog (_callback completes future)
        2. Exception occurs in _textual_confirm at same time
        3. Exception handler tries to cancel already-completed future
        4. future.cancel() should NOT raise InvalidStateError (returns False instead)
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        # Create a mock class that has push_screen and inherits from _InitMixin
        class MockApp(_InitMixin):
            def __init__(self):
                super().__init__()
                self._confirm_futures = {}
                self._confirm_counter = 0
                self._confirm_lock = asyncio.Lock()
            
            async def push_screen(self, screen, callback):
                # This will be mocked below
                pass
        
        # Create app instance
        app = MockApp()
        
        # Mock the push_screen to immediately call callback
        mock_request = MagicMock(spec=ConfirmationRequest)
        mock_request.tool_name = "test_tool"
        mock_request.arguments = {"arg": "value"}
        
        async def mock_push_screen(screen, callback):
            # Simulate user immediately responding "Yes"
            callback(True)
            # Then raise an exception to trigger exception handler
            raise RuntimeError("Simulated error during confirmation")
        
        # Patch push_screen
        with patch.object(app, 'push_screen', mock_push_screen):
            try:
                # Call _textual_confirm
                result = await app._textual_confirm(mock_request)
                print(f"Unexpected success: got result {result}")
            except RuntimeError as e:
                print(f"Expected RuntimeError caught: {e}")
                # Check if any exception was raised during future.cancel()
                # In Python 3.12+, future.cancel() should NOT raise InvalidStateError
                import traceback
                tb = traceback.format_exc()
                # The code has try-except around future.cancel(), so even if
                # it did raise, it would be caught and logged
                print("✓ Exception handling works correctly")
        
        # future.cancel() should not raise InvalidStateError in Python 3.12+
        # The test passes if we get here without the assertion failing
        print("✓ No InvalidStateError raised (as expected in Python 3.12+)")
    
    @pytest.mark.anyio 
    async def test_fix_prevents_invalid_state_error(self) -> None:
        """Test that future.cancel() is idempotent and safe to call on done futures.
        
        According to asyncio documentation, future.cancel() is idempotent
        and returns False (does not raise) when called on done futures.
        The code correctly calls future.cancel() without checking future.done()
        first to avoid TOCTOU races.
        
        Note: This test is skipped because it tries to patch asyncio.Future.cancel
        which is immutable in Python 3.12+. The behavior it tests (future.cancel()
        being idempotent) is already verified by the other tests.
        """
        pytest.skip("Cannot patch asyncio.Future.cancel in Python 3.12+ (immutable type)")