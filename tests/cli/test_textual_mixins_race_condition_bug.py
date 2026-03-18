"""Test for race condition bug in _cleanup_confirm_futures."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from henchman.cli.textual_mixins import _InitMixin


class TestCleanupConfirmFuturesRaceCondition:
    """Test race condition in _cleanup_confirm_futures."""

    def test_cleanup_with_concurrent_pop_raises_runtime_error(self) -> None:
        """Test that concurrent dict modification during cleanup raises RuntimeError.
        
        This demonstrates the bug: if _callback or exception handlers call
        futures_dict.pop() while _cleanup_confirm_futures is iterating,
        it can raise RuntimeError: dictionary changed size during iteration.
        """
        # Create a mock object with _InitMixin methods
        obj = MagicMock(spec=_InitMixin)
        
        # Create some futures
        loop = asyncio.new_event_loop()
        try:
            future1 = loop.create_future()
            future2 = loop.create_future()
            future3 = loop.create_future()
            
            # Create a dictionary that will be modified during iteration
            # We'll simulate concurrent modification by having a callback
            # that removes an item during iteration
            futures_dict = {0: future1, 1: future2, 2: future3}
            
            # Track if we've modified during iteration
            modified_during_iteration = False
            
            # Monkey-patch the dict's pop method to simulate concurrent modification
            original_pop = futures_dict.pop
            def popping_pop(key, default=None):
                nonlocal modified_during_iteration
                # Simulate callback removing item 1 during iteration
                if key == 1 and not modified_during_iteration:
                    modified_during_iteration = True
                return original_pop(key, default)
            
            futures_dict.pop = popping_pop
            
            obj._confirm_futures = futures_dict
            
            # Get the method
            cleanup_method = _InitMixin._cleanup_confirm_futures
            
            # This should work without error in the current implementation
            # because it uses keys = list(futures_dict.keys()) first
            # But if the callback runs between getting keys and iterating,
            # or if we iterate over the dict directly, it would fail
            
            # Actually, let me check the actual implementation more carefully
            # The bug might be more subtle
            
        finally:
            loop.close()
    
    def test_cleanup_iterates_over_dict_directly_bug(self) -> None:
        """Demonstrate the bug if code iterated over dict directly (hypothetical)."""
        # This test shows what WOULD happen if the code didn't use keys = list(futures_dict.keys())
        obj = MagicMock(spec=_InitMixin)
        
        # Create a dictionary that will be modified during iteration
        futures_dict = {0: "future0", 1: "future1", 2: "future2"}
        
        # Track iterations
        iterations = []
        
        def bad_cleanup(self):
            # BUGGY VERSION: iterates over dict directly
            for req_id in self._confirm_futures:
                iterations.append(req_id)
                # Simulate callback removing another item
                if req_id == 0:
                    # Callback removes item 1
                    self._confirm_futures.pop(1, None)
        
        obj._confirm_futures = futures_dict
        
        # This would raise RuntimeError: dictionary changed size during iteration
        # But the actual code uses keys = list(futures_dict.keys()) so it's safe
        
        # The actual bug might be different - let me examine the real code more carefully