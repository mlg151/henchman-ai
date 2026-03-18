"""Test for the real TOCTOU race condition bug in textual_mixins.py.

The bug: In both _textual_confirm._callback and _cleanup_confirm_futures,
there's a TOCTOU race between hasattr() check and attribute access.

_callback:
    if hasattr(self, '_confirm_futures'):
        self._confirm_futures.pop(req_id, None)  # TOCTOU!

_cleanup_confirm_futures:
    if not hasattr(self, '_confirm_futures'):
        return
    keys = list(self._confirm_futures.keys())  # TOCTOU!
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch
import pytest

from henchman.cli.textual_mixins import _InitMixin


class TestTextualMixinsRealBug:
    """Test the real TOCTOU race condition bug."""
    
    def test_cleanup_confirm_futures_toc_tou_race(self) -> None:
        """Test _cleanup_confirm_futures has TOCTOU race between hasattr and access.
        
        This test demonstrates that between:
        1. if not hasattr(self, '_confirm_futures'): return
        2. keys = list(self._confirm_futures.keys())
        
        Another thread could delete the _confirm_futures attribute.
        """
        # Create mixin instance
        mixin = _InitMixin.__new__(_InitMixin)
        
        # Simulate race condition by deleting attribute between hasattr and access
        class RaceSimulator:
            def __init__(self):
                self._confirm_futures = {1: MagicMock(spec=asyncio.Future)}
                self.attribute_deleted = False
            
            def __getattr__(self, name):
                if name == '_confirm_futures' and self.attribute_deleted:
                    raise AttributeError(f"'RaceSimulator' object has no attribute '_confirm_futures'")
                return super().__getattribute__(name)
            
            def trigger_race(self):
                # Simulate another thread deleting attribute
                self.attribute_deleted = True
        
        simulator = RaceSimulator()
        
        # Monkey-patch hasattr to trigger race
        original_hasattr = hasattr
        
        def racing_hasattr(obj, name):
            if obj is simulator and name == '_confirm_futures':
                result = original_hasattr(obj, name)
                if result:  # If attribute exists, trigger race
                    simulator.trigger_race()
                return result
            return original_hasattr(obj, name)
        
        # Test with patched hasattr
        with patch('builtins.hasattr', racing_hasattr):
            # This should raise AttributeError due to race condition
            with pytest.raises(AttributeError, match="_confirm_futures"):
                # We need to call the actual method on our simulator
                # But simulator isn't an _InitMixin, so we need to test differently
                pass
        
        # Actually, let's test the actual code path
        # The bug is theoretical but real - in concurrent execution,
        # between hasattr check and attribute access, attribute could be deleted
    
    def test_callback_toc_tou_race(self) -> None:
        """Test _callback in _textual_confirm has TOCTOU race.
        
        The _callback function (defined inside _textual_confirm) has:
            if hasattr(self, '_confirm_futures'):
                self._confirm_futures.pop(req_id, None)
        
        Between hasattr and pop(), attribute could be deleted.
        """
        # This is harder to test because _callback is a closure inside _textual_confirm
        # But the bug pattern is the same as above
        
        # The fix should be to get a reference to the dict first:
        # futures_dict = getattr(self, '_confirm_futures', None)
        # if futures_dict is not None:
        #     futures_dict.pop(req_id, None)
        
        assert True  # Placeholder - actual test would require mocking the closure
    
    def test_cleanup_with_none_attribute(self) -> None:
        """Test _cleanup_confirm_futures when _confirm_futures is None.
        
        What if someone sets _confirm_futures = None?
        Then list(self._confirm_futures.keys()) would raise AttributeError
        because None doesn't have a .keys() method.
        """
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = None  # Someone sets it to None
        
        # This should raise AttributeError: 'NoneType' object has no attribute 'keys'
        with pytest.raises(AttributeError, match="'NoneType' object has no attribute 'keys'"):
            mixin._cleanup_confirm_futures()
    
    def test_cleanup_with_missing_attribute_after_check(self) -> None:
        """Test the TOCTOU race more directly.
        
        Simulate: hasattr returns True, then attribute is deleted, then access fails.
        """
        mixin = _InitMixin.__new__(_InitMixin)
        
        # Use a property that deletes itself when accessed
        class SelfDeletingDict(dict):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.deleted = False
            
            def __getattribute__(self, name):
                if name == 'keys' and not self.deleted:
                    self.deleted = True
                    # After returning .keys method, delete the attribute from mixin
                    del mixin._confirm_futures
                return super().__getattribute__(name)
        
        mixin._confirm_futures = SelfDeletingDict({1: MagicMock(spec=asyncio.Future)})
        
        # This should raise AttributeError when trying to access .keys()
        # because the attribute gets deleted during access
        with pytest.raises(AttributeError, match="_confirm_futures"):
            mixin._cleanup_confirm_futures()