"""Simple Unit of Doom test for TOCTOU bug in _cleanup_confirm_futures.

Tests the actual bug: if _confirm_futures is None, accessing .keys() fails.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock
import pytest

from henchman.cli.textual_mixins import _InitMixin


class TestTextualMixinsSimpleToctouBug:
    """Simple test for the TOCTOU bug."""
    
    def test_cleanup_confirm_futures_with_none_attribute(self) -> None:
        """Test that _cleanup_confirm_futures crashes when _confirm_futures is None.
        
        BUG: If _confirm_futures = None, then:
            if not hasattr(self, '_confirm_futures'):  # False (attribute exists)
                return
            futures_dict = self._confirm_futures  # futures_dict = None
            keys = list(futures_dict.keys())  # CRASH: AttributeError: 'NoneType' object has no attribute 'keys'
        
        This test FAILS on original code, PASSES after fix.
        """
        # Create mixin instance
        mixin = _InitMixin.__new__(_InitMixin)
        
        # Set _confirm_futures to None (simulating bug or race condition)
        mixin._confirm_futures = None
        
        # Bug is fixed: should return gracefully, not raise AttributeError
        result = mixin._cleanup_confirm_futures()
        assert result is None  # Returns None (exits early due to None check)
    
    def test_cleanup_confirm_futures_with_missing_attribute(self) -> None:
        """Test that _cleanup_confirm_futures handles missing attribute.
        
        This should work in original code due to hasattr check.
        """
        mixin = _InitMixin.__new__(_InitMixin)
        
        # Ensure attribute doesn't exist
        if hasattr(mixin, '_confirm_futures'):
            delattr(mixin, '_confirm_futures')
        
        # This should return without error
        result = mixin._cleanup_confirm_futures()
        assert result is None  # Method returns None
    
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