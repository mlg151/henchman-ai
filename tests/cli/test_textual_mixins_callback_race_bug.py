"""Test for the race condition bug in textual_mixins.py _textual_confirm callback."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch
import pytest

from henchman.tools.base import ConfirmationRequest


class TestTextualConfirmCallbackRaceBug:
    """Test that demonstrates the race condition in _textual_confirm callback."""
    
    @pytest.mark.anyio
    async def test_callback_creates_task_for_lock_race(self) -> None:
        """Test that _callback does NOT create a task for lock acquisition.
        
        The callback should use getattr and .pop() which are safe in sync context.
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        # Create mixin instance
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 100
        mixin._confirm_lock = asyncio.Lock()
        
        # Get the actual source code
        import inspect
        source = inspect.getsource(mixin._textual_confirm)
        
        # The callback should NOT use asyncio.create_task() to acquire lock
        # It should use getattr and .pop() which are safe in sync context
        assert 'asyncio.create_task(' not in source, (
            "Callback should not use asyncio.create_task() in sync context"
        )
        
        # Check that it uses getattr for safe attribute access
        assert 'getattr(self, \'_confirm_futures\', None)' in source, (
            "Callback should use getattr for safe attribute access"
        )
        
        # Check that it uses .pop() which is thread-safe for dict
        assert '.pop(req_id, None)' in source, (
            "Callback should use .pop() for safe dictionary removal"
        )
        # Actually, let me check what the fix should be...
        
        # Actually, looking at the code more carefully:
        # The callback IS called from Textual which runs in asyncio event loop
        # So we COULD make it async, but Textual API might not support it
        
        # The real bug is the race between task creation and execution
        # Let me demonstrate it
        
    @pytest.mark.anyio 
    async def test_demonstrate_race_condition(self) -> None:
        """Demonstrate the race condition."""
        from henchman.cli.textual_mixins import _InitMixin
        
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 100
        mixin._confirm_lock = asyncio.Lock()
        
        # Add a future to the dict
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        req_id = 100
        mixin._confirm_futures[req_id] = future
        
        # Track if task was created
        task_created = False
        original_create_task = asyncio.create_task
        
        def track_create_task(coro):
            nonlocal task_created
            task_created = True
            return original_create_task(coro)
        
        # Simulate the callback logic
        def simulate_callback():
            if hasattr(mixin, '_confirm_futures'):
                if hasattr(mixin, '_confirm_lock'):
                    try:
                        loop = asyncio.get_running_loop()
                        
                        async def remove_from_dict():
                            async with mixin._confirm_lock:
                                mixin._confirm_futures.pop(req_id, None)
                        
                        # BUG: Creates task but doesn't wait
                        asyncio.create_task(remove_from_dict())
                    except RuntimeError:
                        mixin._confirm_futures.pop(req_id, None)
        
        # Patch to track task creation
        with patch('asyncio.create_task', track_create_task):
            simulate_callback()
            
            # Task was created
            assert task_created, "Callback created task for lock acquisition"
            
            # But task hasn't run yet!
            # The future is still in the dict
            assert req_id in mixin._confirm_futures, (
                "Race condition: future still in dict after callback creates task"
            )
            
            # This is the TOCTOU race:
            # 1. Callback creates task to remove from dict (with lock)
            # 2. Task is scheduled but hasn't run
            # 3. Other code could access dict before task runs
            
            # Run pending tasks
            await asyncio.sleep(0)
            
            # Now task should have run
            assert req_id not in mixin._confirm_futures, (
                "Future should be removed after task runs"
            )
    
    @pytest.mark.anyio
    async def test_concurrent_cleanup_during_race(self) -> None:
        """Test that cleanup during the race can cause issues."""
        from henchman.cli.textual_mixins import _InitMixin
        
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 100
        mixin._confirm_lock = asyncio.Lock()
        
        # Add multiple futures
        futures = {}
        for i in range(100, 110):
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            mixin._confirm_futures[i] = future
            futures[i] = future
        
        # Simulate multiple callbacks running
        tasks_created = []
        
        original_create_task = asyncio.create_task
        
        def track_create_task(coro):
            task = original_create_task(coro)
            tasks_created.append(task)
            return task
        
        with patch('asyncio.create_task', track_create_task):
            # Run callbacks for first 5 futures
            for req_id in range(100, 105):
                def callback(rid=req_id):
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
                
                callback()
            
            # Tasks created but not run
            assert len(tasks_created) == 5
            assert len(mixin._confirm_futures) == 10  # All 10 still there!
            
            # Now simulate _cleanup_confirm_futures being called
            # (e.g., during app shutdown)
            def simulate_cleanup():
                if hasattr(mixin, '_confirm_futures'):
                    # Current implementation: iterates over keys and modifies dict
                    keys = list(mixin._confirm_futures.keys())
                    for req_id in keys:
                        future = mixin._confirm_futures.get(req_id)
                        if future is not None:
                            future.cancel()
                            mixin._confirm_futures.pop(req_id, None)
            
            # Cleanup runs while tasks are pending
            simulate_cleanup()
            
            # Dict should be empty after cleanup
            assert len(mixin._confirm_futures) == 0, (
                "Cleanup should remove all futures"
            )
            
            # Now tasks will run and try to pop already-removed entries
            # This is mostly harmless (pop with default), but shows the race
            
            # Run the tasks (they'll complete without error due to pop with default)
            results = await asyncio.gather(*tasks_created, return_exceptions=True)
            
            # Check no exceptions
            for result in results:
                if isinstance(result, Exception):
                    raise result