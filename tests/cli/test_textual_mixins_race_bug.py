"""Test for the race condition bug in textual_mixins.py _textual_confirm callback."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
import pytest

from henchman.tools.base import ConfirmationRequest


class TestTextualConfirmRaceBug:
    """Test that demonstrates the race condition in _textual_confirm callback."""
    
    @pytest.mark.anyio
    async def test_callback_lock_race_condition(self) -> None:
        """Demonstrate the race condition in _callback when using asyncio.Lock.
        
        The bug: _callback is a sync function but tries to acquire an async lock
        by creating a task. This creates a TOCTOU race condition.
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        # Create a mock app with the mixin
        app = MagicMock()
        app._confirm_futures = {}
        app._confirm_counter = 0
        app._confirm_lock = asyncio.Lock()
        
        # We need to test the actual _textual_confirm method
        # First, let's inspect the _callback function logic
        import inspect
        import henchman.cli.textual_mixins as module
        
        source = inspect.getsource(module._InitMixin._textual_confirm)
        
        # Check that _callback tries to create_task for lock acquisition
        assert 'asyncio.create_task(remove_from_dict())' in source, (
            "_callback creates task for lock acquisition - this is the race condition!"
        )
        
        # The bug: In _callback (sync context):
        # 1. Checks if lock exists
        # 2. Creates a task to acquire lock and remove from dict
        # 3. Task is scheduled but not awaited
        
        # Meanwhile, other code could:
        # 1. Access _confirm_futures before task runs
        # 2. Modify _confirm_futures before task runs
        # 3. Cause KeyError or other issues
        
        # Simulate the race
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 100
        mixin._confirm_lock = asyncio.Lock()
        
        # Create a future and add it to dict
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        req_id = 100
        
        mixin._confirm_futures[req_id] = future
        
        # Now simulate what happens in _callback
        # This is the buggy code path
        def buggy_callback(result: object | None) -> None:
            if hasattr(mixin, '_confirm_futures'):
                if hasattr(mixin, '_confirm_lock'):
                    try:
                        loop = asyncio.get_running_loop()
                        
                        async def remove_from_dict():
                            async with mixin._confirm_lock:
                                mixin._confirm_futures.pop(req_id, None)
                        
                        # BUG: Creates task but doesn't wait for it
                        asyncio.create_task(remove_from_dict())
                    except RuntimeError:
                        mixin._confirm_futures.pop(req_id, None)
        
        # Call the callback
        buggy_callback(True)
        
        # The task is created but hasn't run yet
        # _confirm_futures[100] still exists!
        assert 100 in mixin._confirm_futures, (
            "Race condition: dict entry still exists after callback creates task"
        )
        
        # Now if another operation tries to access/clean up...
        # This could cause issues
        
        # Run pending tasks to simulate what happens eventually
        await asyncio.sleep(0)
        
        # Now the entry should be removed
        assert 100 not in mixin._confirm_futures, (
            "Entry should be removed after task runs"
        )
    
    @pytest.mark.anyio
    async def test_concurrent_access_during_race(self) -> None:
        """Test that concurrent access during the race can cause issues."""
        from henchman.cli.textual_mixins import _InitMixin
        
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 100
        mixin._confirm_lock = asyncio.Lock()
        
        # Add multiple entries
        for i in range(100, 110):
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            mixin._confirm_futures[i] = future
        
        # Track task creation
        tasks_created = []
        
        original_create_task = asyncio.create_task
        
        def track_create_task(coro):
            task = original_create_task(coro)
            tasks_created.append(task)
            return task
        
        # Simulate multiple callbacks running "concurrently"
        # (In reality, they'd be sequential in event loop, but tasks interleave)
        
        with patch('asyncio.create_task', track_create_task):
            # Create multiple callbacks
            callbacks = []
            for req_id in range(100, 105):
                def callback(result: object | None, rid=req_id) -> None:
                    if hasattr(mixin, '_confirm_futures'):
                        if hasattr(mixin, '_confirm_lock'):
                            try:
                                loop = asyncio.get_running_loop()
                                
                                async def remove_from_dict():
                                    async with mixin._confirm_lock:
                                        mixin._confirm_futures.pop(rid, None)
                                
                                asyncio.create_task(remove_from_dict())
                            except RuntimeError:
                                mixin._confirm_futures.pop(rid, None)
                
                callbacks.append(callback)
            
            # Run all callbacks
            for callback in callbacks:
                callback(True)
            
            # Tasks are created but not run yet
            assert len(tasks_created) == 5
            assert len(mixin._confirm_futures) == 10  # All entries still there!
            
            # This is the race: dict still has all entries
            # If _cleanup_confirm_futures is called now, it will see all 10
            
            # Simulate cleanup being called (e.g., during shutdown)
            def simulate_cleanup():
                if hasattr(mixin, '_confirm_futures'):
                    keys = list(mixin._confirm_futures.keys())
                    for req_id in keys:
                        future = mixin._confirm_futures.get(req_id)
                        if future is not None:
                            future.cancel()
                            mixin._confirm_futures.pop(req_id, None)
            
            # Cleanup runs while tasks are pending
            simulate_cleanup()
            
            # Now tasks will run and try to pop already-removed entries
            # This is harmless (pop with default), but shows the race
            
            # Run the tasks
            await asyncio.gather(*tasks_created, return_exceptions=True)
            
            # Dict should be empty
            assert len(mixin._confirm_futures) == 0
    
    @pytest.mark.anyio
    async def test_fix_should_use_threadsafe_approach(self) -> None:
        """Test what the fix should look like."""
        from henchman.cli.textual_mixins import _InitMixin
        
        # The fix should either:
        # 1. Not use a lock in the callback (accept race during cleanup)
        # 2. Use a threadsafe approach (like asyncio.run_coroutine_threadsafe)
        # 3. Make callback async (if Textual supports it)
        
        # Current implementation creates race condition
        mixin = _InitMixin.__new__(_InitMixin)
        
        # Get the actual source to check
        import inspect
        source = inspect.getsource(mixin._textual_confirm)
        
        # The problematic pattern:
        assert 'asyncio.create_task(remove_from_dict())' in source, (
            "Found the race condition pattern"
        )
        
        # A better approach would be to not try to acquire lock in sync callback
        # Since cleanup during shutdown accepts races anyway
        
        # Or use call_soon_threadsafe if we need thread safety
        # But Textual callbacks run in event loop thread, so we could
        # just call the async function directly
        
        # Actually, looking at the code again:
        # The callback is called from Textual which runs in asyncio event loop
        # So we COULD make the callback async and use await
        
        # But the current Textual API might not support async callbacks
        # So the fix is to remove the lock acquisition attempt in callback
        # and accept the potential race (which the comment already says is OK)