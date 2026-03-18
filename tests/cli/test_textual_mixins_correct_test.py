"""Correct Unit of Doom test for TOCTOU bug in _cleanup_confirm_futures.

This test FAILS on original code (raises AttributeError), 
PASSES after fix (handles None gracefully).
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock
import pytest

from henchman.cli.textual_mixins import _InitMixin


class TestTextualMixinsCorrectToctouBug:
    """Correct test for the TOCTOU bug."""
    
    def test_cleanup_confirm_futures_handles_none_gracefully(self) -> None:
        """Test that _cleanup_confirm_futures handles None gracefully.
        
        BUG: If _confirm_futures = None, then:
            if not hasattr(self, '_confirm_futures'):  # False (attribute exists)
                return
            futures_dict = self._confirm_futures  # futures_dict = None
            keys = list(futures_dict.keys())  # CRASH: AttributeError: 'NoneType' object has no attribute 'keys'
        
        FIX: Should handle None gracefully (return without error).
        
        This test FAILS on original code (raises AttributeError),
        PASSES after fix (returns gracefully).
        """
        # Create mixin instance
        mixin = _InitMixin.__new__(_InitMixin)
        
        # Set _confirm_futures to None (simulating bug or race condition)
        mixin._confirm_futures = None
        
        # This should NOT raise AttributeError after fix
        # But WILL raise AttributeError in original code
        try:
            mixin._cleanup_confirm_futures()
            # If we get here, the method handled None gracefully (PASS after fix)
        except AttributeError as e:
            if "'NoneType' object has no attribute 'keys'" in str(e):
                # This is the bug! Test FAILS on original code
                pytest.fail(f"BUG: _cleanup_confirm_futures crashed with AttributeError: {e}")
            else:
                # Some other AttributeError, re-raise
                raise
    
    def test_cleanup_confirm_futures_handles_missing_attribute(self) -> None:
        """Test that _cleanup_confirm_futures handles missing attribute.
        
        This should work in both original and fixed code.
        """
        mixin = _InitMixin.__new__(_InitMixin)
        
        # Ensure attribute doesn't exist
        if hasattr(mixin, '_confirm_futures'):
            delattr(mixin, '_confirm_futures')
        
        # This should return without error
        mixin._cleanup_confirm_futures()
        # No assertion needed - just shouldn't crash
    
    def test_cleanup_confirm_futures_normal_case(self) -> None:
        """Test normal case where _confirm_futures is a dict.
        
        This should work in both original and fixed code.
        """
        mixin = _InitMixin.__new__(_InitMixin)
        
        # Create a mock future
        mock_future = MagicMock(spec=asyncio.Future)
        mock_future.cancel.return_value = None
        
        # Set up normal case
        mixin._confirm_futures = {1: mock_future, 2: mock_future}
        
        # This should work without error
        mixin._cleanup_confirm_futures()
        
        # Verify futures were cancelled
        assert mock_future.cancel.call_count == 2