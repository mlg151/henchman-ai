"""Failing test for _cleanup_confirm_futures exception handling bug.

The bug: _cleanup_confirm_futures calls future.cancel() without try-except.
If cancel() raises, cleanup stops and other futures aren't cancelled.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch
import pytest

from henchman.cli.textual_mixins import _InitMixin


class TestCleanupConfirmFuturesExceptionBug:
    """Test that demonstrates the exception handling bug in _cleanup_confirm_futures."""
    
    def test_cleanup_handles_cancel_exception(self) -> None:
        """Test that _cleanup_confirm_futures handles exceptions from future.cancel().
        
        This test will FAIL with current implementation because:
        - future.cancel() is called without try-except
        - If cancel() raises, cleanup stops
        - Other futures won't be cancelled
        
        After fix, this test should pass.
        """
        # Create a mock mixin instance
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        
        # Create mock futures
        future1 = MagicMock(spec=asyncio.Future)
        future2 = MagicMock(spec=asyncio.Future)
        
        # Make future1.cancel() raise an exception
        future1.cancel.side_effect = RuntimeError("Future in invalid state")
        # future2.cancel() should work normally
        future2.cancel.return_value = True
        
        # Add futures to dict
        mixin._confirm_futures[1] = future1
        mixin._confirm_futures[2] = future2
        
        # Call cleanup - should handle exception and continue
        try:
            mixin._cleanup_confirm_futures()
        except Exception as e:
            pytest.fail(f"_cleanup_confirm_futures raised exception: {e}")
        
        # Verify both futures had cancel() called
        # With bug: future1.cancel() raises, future2.cancel() never called
        # After fix: future1.cancel() exception caught, future2.cancel() still called
        future1.cancel.assert_called_once()
        future2.cancel.assert_called_once()
        
        # Verify dict is empty after cleanup
        assert len(mixin._confirm_futures) == 0, "Dict should be empty after cleanup"
    
    def test_cleanup_with_no_futures(self) -> None:
        """Test cleanup when _confirm_futures doesn't exist."""
        mixin = _InitMixin.__new__(_InitMixin)
        # Don't set _confirm_futures attribute
        assert not hasattr(mixin, '_confirm_futures')
        
        # Should not raise
        mixin._cleanup_confirm_futures()
        
        # Test passes if no exception
    
    def test_cleanup_with_empty_dict(self) -> None:
        """Test cleanup with empty futures dict."""
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        
        # Should not raise
        mixin._cleanup_confirm_futures()
        
        # Dict should still be empty
        assert len(mixin._confirm_futures) == 0