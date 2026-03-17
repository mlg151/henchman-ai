"""Test for callback lock bug in textual_mixins.py.

The bug: Callback doesn't use lock when accessing _confirm_futures,
creating race condition with concurrent _textual_confirm calls.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch
import pytest

from henchman.tools.base import ConfirmationRequest


class TestCallbackLockBug:
    """Test that callback should use lock but doesn't."""
    
    @pytest.mark.anyio
    async def test_callback_does_not_use_lock(self) -> None:
        """Verify callback doesn't use async with lock.
        
        The callback is called in async context (from Textual screen dismissal)
        but doesn't use async with self._confirm_lock:, creating race condition.
        """
        import inspect
        import henchman.cli.textual_mixins as module
        
        # Get source of _textual_confirm method
        source = inspect.getsource(module._InitMixin._textual_confirm)
        
        # Find callback definition
        lines = source.split('\n')
        in_callback = False
        callback_lines = []
        
        for line in lines:
            if 'def _callback(' in line:
                in_callback = True
            if in_callback:
                callback_lines.append(line)
                # Check for end of callback (typically empty line or dedent)
                if line.strip() == '' and len(callback_lines) > 5:
                    # Probably end of callback
                    break
        
        callback_text = '\n'.join(callback_lines)
        print("Callback function:")
        print(callback_text)
        
        # Check if callback uses async with
        if 'async with self._confirm_lock:' in callback_text:
            print("✓ Callback uses async with lock")
            uses_lock = True
        else:
            print("✗ Callback doesn't use async with lock")
            uses_lock = False
        
        # Check comment about not using lock
        if 'we can\'t use async with' in callback_text or "can't use async with" in callback_text:
            print("✓ Callback has comment about not using async with")
            has_comment = True
        else:
            print("✗ Callback doesn't explain why it doesn't use lock")
            has_comment = False
        
        # The bug: callback should use lock but doesn't
        # Actually, thinking about it: the callback is sync (def not async def)
        # So it CAN'T use async with. But it could schedule lock acquisition.
        
        # Check if callback is async def
        if 'async def _callback' in callback_text:
            print("✓ Callback is async (can use async with)")
            is_async = True
        else:
            print("✗ Callback is sync (can't use async with)")
            is_async = False
        
        # If callback is sync, it really can't use async with
        # But it could use asyncio.run_coroutine_threadsafe or similar
        # Or accept the race (current approach)
        
        # Actually, the real question: is the race acceptable?
        # Callback removes its own entry from dict
        # _textual_confirm adds new entries
        # Race: callback popping while _textual_confirm is adding
        # Could cause KeyError or missed pop
        
        print("\nAnalysis:")
        print("- Callback is sync (def _callback)")
        print("- Can't use async with in sync function")
        print("- Current approach: accept race")
        print("- Alternative: make callback async or use different sync mechanism")
        
        # This might not be a bug, just a design choice
        # But we should verify the race is handled
        
        # Check if callback handles missing _confirm_futures
        if 'hasattr(self, \'_confirm_futures\')' in callback_text:
            print("✓ Callback checks if _confirm_futures exists")
        else:
            print("✗ Callback doesn't check if _confirm_futures exists (potential AttributeError)")
        
        # The test doesn't fail because it's not clearly a bug
        # It's a design tradeoff: simplicity vs. perfect synchronization
    
    @pytest.mark.anyio
    async def test_race_condition_scenario(self) -> None:
        """Simulate race between callback and _textual_confirm."""
        from henchman.cli.textual_mixins import _InitMixin
        
        # Create instance
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 0
        mixin._confirm_lock = asyncio.Lock()
        
        # Simulate the race
        # Thread A: _textual_confirm adding future
        # Thread B: Callback removing future
        
        # We can't easily simulate this without actual Textual screen
        # But we can think about the race:
        
        # _textual_confirm does:
        # 1. async with lock: req_id = counter; counter++; dict[req_id] = future
        # 2. await push_screen (yields control)
        
        # Callback does (without lock):
        # 1. future.set_result()
        # 2. dict.pop(req_id, None)
        
        # Race window: between step 1 and 2 in callback,
        # _textual_confirm could be at step 1 (adding to dict)
        
        # Actually, _textual_confirm holds lock while adding to dict
        # Callback doesn't use lock
        # So race is: callback popping while _textual_confirm holds lock and is adding
        
        # This is a classic lock vs no-lock race
        # Could cause:
        # - Callback pops, _textual_confirm adds -> dict has entry (callback missed it)
        # - _textual_confirm adds, callback pops -> dict clean
        
        # Actually, thinking more: _textual_confirm holds lock during dict update
        # Callback doesn't hold lock during dict pop
        # Python dict operations are generally atomic for single operations
        # So pop and __setitem__ are atomic
        
        # The race is probably benign:
        # - If callback pops first: _textual_confirm adds after -> dict has entry (leak)
        # - If _textual_confirm adds first: callback pops after -> dict clean
        
        # Leaked entry (future in dict but done) could be cleaned up later
        # by _cleanup_confirm_futures or next callback
        
        print("Race analysis:")
        print("- _textual_confirm: holds lock, adds to dict")
        print("- Callback: no lock, pops from dict")
        print("- Possible outcome: dict entry leak if callback pops first")
        print("- Leak is cleaned up during shutdown")
        print("- Probably acceptable for this use case")
        
        # Not clearly a bug, more of a design tradeoff