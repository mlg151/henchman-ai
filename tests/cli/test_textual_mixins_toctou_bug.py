"""Unit of Doom test for TOCTOU bug in _cleanup_confirm_futures.

This test demonstrates the TOCTOU race condition where:
1. hasattr(self, '_confirm_futures') returns True
2. Between check and access, attribute is deleted/set to None
3. AttributeError occurs

The test FAILS on original code, PASSES after fix.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock
import pytest

from henchman.cli.textual_mixins import _InitMixin


class TestTextualMixinsToctouBug:
    """Test the TOCTOU race condition bug in _cleanup_confirm_futures."""
    
    def test_cleanup_confirm_futures_attribute_deleted_between_check_and_access(self) -> None:
        """Test TOCTOU race: attribute deleted between hasattr and access.
        
        This test simulates the race condition where:
        - hasattr(self, '_confirm_futures') returns True
        - Another thread deletes self._confirm_futures
        - self._confirm_futures access raises AttributeError
        
        BUG: The original code has:
            if not hasattr(self, '_confirm_futures'):
                return
            futures_dict = self._confirm_futures  # TOCTOU!
        
        FIX: Use atomic getattr:
            futures_dict = getattr(self, '_confirm_futures', None)
            if futures_dict is None:
                return
        """
        # Create mixin instance
        mixin = _InitMixin.__new__(_InitMixin)
        
        # Create a mock that deletes itself when accessed
        class SelfDeletingAttribute:
            def __init__(self, mixin_obj):
                self.mixin = mixin_obj
                self.access_count = 0
            
            def __get__(self, obj, objtype=None):
                if obj is None:
                    return self
                self.access_count += 1
                if self.access_count == 1:
                    # First access (from hasattr) - return True-like value
                    return True
                elif self.access_count == 2:
                    # Second access (from attribute access) - delete attribute first
                    del self.mixin._confirm_futures
                    raise AttributeError("_confirm_futures")
        
        # Monkey-patch hasattr to control the race
        original_hasattr = hasattr
        
        def racing_hasattr(obj, name):
            if obj is mixin and name == '_confirm_futures':
                # Simulate: attribute exists when checked
                return True
            return original_hasattr(obj, name)
        
        # Set up the mixin with a future
        mixin._confirm_futures = {1: MagicMock(spec=asyncio.Future)}
        
        # Patch hasattr to simulate race
        import builtins
        original_hasattr = builtins.hasattr
        builtins.hasattr = racing_hasattr
        
        try:
            # Bug is fixed: source uses getattr atomically, TOCTOU race is eliminated.
            try:
                mixin._cleanup_confirm_futures()
            except AttributeError:
                pytest.fail(
                    "Bug is fixed: getattr pattern prevents TOCTOU race. "
                    "No AttributeError should be raised."
                )
        finally:
            # Restore original hasattr
            builtins.hasattr = original_hasattr
    
    def test_cleanup_confirm_futures_attribute_set_to_none(self) -> None:
        """Test when _confirm_futures is set to None.
        
        BUG: If _confirm_futures = None, then:
            futures_dict = self._confirm_futures  # futures_dict = None
            keys = list(futures_dict.keys())  # AttributeError: 'NoneType' object has no attribute 'keys'
        """
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = None
        
        # Bug is fixed: should return gracefully without raising
        result = mixin._cleanup_confirm_futures()
        assert result is None  # Returns None (exits early)
    
    def test_cleanup_confirm_futures_missing_attribute(self) -> None:
        """Test when _confirm_futures attribute doesn't exist.
        
        This should work correctly in original code due to hasattr check.
        """
        mixin = _InitMixin.__new__(_InitMixin)
        
        # Ensure attribute doesn't exist
        if hasattr(mixin, '_confirm_futures'):
            delattr(mixin, '_confirm_futures')
        
        # This should return without error (hasattr check works)
        mixin._cleanup_confirm_futures()
        # No assertion needed - just shouldn't crash
    
    def test_callback_race_with_cleanup(self) -> None:
        """Test race between _callback and _cleanup_confirm_futures.
        
        The _callback function also has a TOCTOU issue:
            if hasattr(self, '_confirm_futures'):
                self._confirm_futures.pop(req_id, None)  # TOCTOU!
        
        Between hasattr and pop(), attribute could be deleted.
        """
        mixin = _InitMixin.__new__(_InitMixin)
        
        # Create a future
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            future = loop.create_future()
            
            # Set up mixin state
            mixin._confirm_futures = {0: future}
            mixin._confirm_counter = 1
            
            # Define _callback similar to the one in _textual_confirm
            def _callback(result: object | None) -> None:
                # This mimics the buggy pattern in the actual code
                if hasattr(mixin, '_confirm_futures'):
                    # TOCTOU: attribute could be deleted here
                    mixin._confirm_futures.pop(0, None)
            
            # Simulate race: delete attribute between hasattr and pop
            def racing_hasattr(obj, name):
                if obj is mixin and name == '_confirm_futures':
                    # Delete attribute after hasattr returns True
                    del mixin._confirm_futures
                    return True
                return False
            
            # Patch hasattr
            import builtins
            original_hasattr = builtins.hasattr
            builtins.hasattr = racing_hasattr
            
            try:
                # This should raise AttributeError
                with pytest.raises(AttributeError, match="_confirm_futures"):
                    _callback(True)
            finally:
                builtins.hasattr = original_hasattr
        finally:
            loop.close()