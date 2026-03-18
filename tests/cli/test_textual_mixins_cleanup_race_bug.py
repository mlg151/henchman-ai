"""Test for the race condition bug in textual_mixins.py _cleanup_confirm_futures."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch
import pytest

from henchman.tools.base import ConfirmationRequest


class TestTextualConfirmCleanupRaceBug:
    """Test that demonstrates the race condition in _cleanup_confirm_futures."""
    
    @pytest.mark.anyio
    async def test_cleanup_race_condition(self) -> None:
        """Bug is fixed: _cleanup_confirm_futures uses getattr and pops before cancelling.

        The old bug: cancel() called before pop() - callbacks could see future in dict.
        The fix: future = futures_dict.pop(req_id, None) then future.cancel().
        """
        from henchman.cli.textual_mixins import _InitMixin
        import inspect
        
        mixin = _InitMixin.__new__(_InitMixin)
        source = inspect.getsource(mixin._cleanup_confirm_futures)
        
        assert 'future.cancel()' in source, "Found cancel() call"
        # Bug is fixed: source uses futures_dict.pop() (via getattr, atomic)
        assert 'futures_dict.pop(req_id, None)' in source, "Found pop() call"
        
        # Bug is fixed: future is popped from dict BEFORE cancel()
        assert 'future = futures_dict.pop(req_id, None)' in source, (
            "Bug is fixed: future popped from dict before cancel()"
        )


    @pytest.mark.anyio
    async def test_demonstrate_cleanup_race(self) -> None:
        """Demonstrate the race condition in cleanup."""
        from henchman.cli.textual_mixins import _InitMixin
        
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 100
        
        # Create a future that will have a callback
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        req_id = 100
        
        # Track what happens
        events = []
        
        def callback(f):
            # This runs when future is cancelled
            events.append("callback_started")
            # Check if future is still in dict
            if hasattr(mixin, '_confirm_futures'):
                still_in_dict = req_id in mixin._confirm_futures
                events.append(f"future_still_in_dict: {still_in_dict}")
            events.append("callback_ended")
        
        future.add_done_callback(callback)
        mixin._confirm_futures[req_id] = future
        
        # Simulate the buggy cleanup logic
        def buggy_cleanup():
            if hasattr(mixin, '_confirm_futures'):
                keys = list(mixin._confirm_futures.keys())
                for rid in keys:
                    future = mixin._confirm_futures.get(rid)
                    if future is not None:
                        # BUG: cancel before pop
                        events.append("before_cancel")
                        future.cancel()  # This triggers callback!
                        events.append("after_cancel")
                        mixin._confirm_futures.pop(rid, None)
                        events.append("after_pop")
        
        buggy_cleanup()
        
        # Check event sequence
        print(f"Events: {events}")
        
        # The race: callback runs between cancel() and pop()
        # In current implementation, callback could see future still in dict
        
        # Actually run pending callbacks
        await asyncio.sleep(0)
        
        # The fix would be to pop first, then cancel
        def fixed_cleanup():
            if hasattr(mixin, '_confirm_futures'):
                keys = list(mixin._confirm_futures.keys())
                for rid in keys:
                    # FIX: pop first, then cancel
                    future = mixin._confirm_futures.pop(rid, None)
                    if future is not None:
                        future.cancel()  # Callback won't find future in dict
        
        # Reset and test fixed version
        mixin._confirm_futures = {}
        future2 = loop.create_future()
        future2.add_done_callback(lambda f: None)
        mixin._confirm_futures[100] = future2
        
        events2 = []
        
        def callback2(f):
            events2.append("callback")
            if hasattr(mixin, '_confirm_futures'):
                events2.append(f"dict_has_100: {100 in mixin._confirm_futures}")
        
        future2.add_done_callback(callback2)
        
        fixed_cleanup()
        await asyncio.sleep(0)
        
        # With fix, callback should see future NOT in dict
        print(f"Events2: {events2}")
    
    @pytest.mark.anyio
    async def test_concurrent_cleanup_and_callback(self) -> None:
        """Test concurrent cleanup and callback execution."""
        from henchman.cli.textual_mixins import _InitMixin
        
        # This is hard to test deterministically because
        # we can't control when callbacks run
        
        # But we can show the logic flaw
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        
        # The bug scenario:
        # 1. Cleanup starts, gets key 100
        # 2. Cleanup calls future.cancel()
        # 3. Callback runs (triggered by cancel)
        # 4. Callback tries to pop key 100 from dict
        # 5. Cleanup tries to pop key 100 from dict
        # 
        # This is mostly harmless (pop with default) but shows race
        
        # Actually, there's a worse scenario:
        # 1. Cleanup gets key 100
        # 2. Cleanup calls future.cancel()  
        # 3. Callback runs and modifies dict (adds/removes other keys)
        # 4. Cleanup continues iterating over original keys list
        # 
        # This could cause issues if dict structure changes
        
        # The fix is simple: pop before cancel
        import inspect
        source = inspect.getsource(_InitMixin._cleanup_confirm_futures)
        
        # Extract the cleanup logic
        lines = source.split('\n')
        in_loop = False
        for i, line in enumerate(lines):
            if 'for req_id in keys:' in line:
                in_loop = True
            elif in_loop and line.strip() == '':
                in_loop = False
            elif in_loop:
                # Check for the pattern
                if 'future.cancel()' in line and 'self._confirm_futures.pop' in source[i:]:
                    # Find which comes first
                    remaining = '\n'.join(lines[i:])
                    cancel_pos = remaining.find('future.cancel()')
                    pop_pos = remaining.find('self._confirm_futures.pop')
                    
                    if cancel_pos < pop_pos:
                        print("BUG FOUND: cancel() before pop()")
                        print(f"Line {i}: {line}")
                        # This is the bug we need to fix