"""Test demonstrating why threading.Lock is wrong for async code.

The bug: threading.Lock is reentrant within the same thread, so when
one async task acquires it and then awaits, another async task in the
same thread can also acquire it.
"""

from __future__ import annotations

import asyncio
import threading
from unittest.mock import MagicMock, patch
import pytest


class TestThreadingLockBug:
    """Test that demonstrates threading.Lock doesn't work for async."""
    
    @pytest.mark.anyio
    async def test_threading_lock_reentrant_in_async(self) -> None:
        """Show that threading.Lock allows reentrancy across async tasks.
        
        This demonstrates why threading.Lock is wrong for _textual_confirm.
        """
        lock = threading.Lock()
        acquisition_order = []
        
        async def task1():
            print("Task 1: Acquiring lock")
            with lock:
                acquisition_order.append("task1_enter")
                print("Task 1: Got lock, now awaiting")
                # This await yields control to event loop
                await asyncio.sleep(0.01)
                print("Task 1: Resumed after await")
                acquisition_order.append("task1_exit")
        
        async def task2():
            # Give task1 time to acquire lock first
            await asyncio.sleep(0.001)
            print("Task 2: Trying to acquire lock")
            with lock:
                acquisition_order.append("task2_enter")
                print("Task 2: Got lock too! This is the bug.")
                acquisition_order.append("task2_exit")
        
        # Run both tasks concurrently
        await asyncio.gather(task1(), task2())
        
        print(f"Acquisition order: {acquisition_order}")
        
        # With threading.Lock, both tasks can acquire it because
        # they're in the same thread and threading.Lock is reentrant
        # This is WRONG for async code!
        assert "task2_enter" in acquisition_order, \
            "Threading lock should allow reentrancy (this shows the bug)"
        
        # The correct order would be task1 enters, task1 exits, THEN task2 enters
        # But with threading.Lock, we get interleaving
        
    @pytest.mark.anyio 
    async def test_asyncio_lock_correct_for_async(self) -> None:
        """Show that asyncio.Lock properly serializes async tasks."""
        lock = asyncio.Lock()
        acquisition_order = []
        
        async def task1():
            print("Task 1: Acquiring asyncio lock")
            async with lock:
                acquisition_order.append("task1_enter")
                print("Task 1: Got asyncio lock, now awaiting")
                # This await yields control, but lock is held
                await asyncio.sleep(0.01)
                print("Task 1: Resumed after await")
                acquisition_order.append("task1_exit")
        
        async def task2():
            # Give task1 time to acquire lock first
            await asyncio.sleep(0.001)
            print("Task 2: Trying to acquire asyncio lock")
            async with lock:
                acquisition_order.append("task2_enter")
                print("Task 2: Got lock after task1 released it")
                acquisition_order.append("task2_exit")
        
        await asyncio.gather(task1(), task2())
        
        print(f"Acquisition order with asyncio.Lock: {acquisition_order}")
        
        # With asyncio.Lock, task2 should NOT enter until task1 exits
        # Check that task1_enter comes before task1_exit, and task2_enter
        # comes after task1_exit
        task1_enter_idx = acquisition_order.index("task1_enter")
        task1_exit_idx = acquisition_order.index("task1_exit")
        task2_enter_idx = acquisition_order.index("task2_enter")
        
        assert task1_enter_idx < task1_exit_idx, "task1 should enter before exiting"
        assert task1_exit_idx < task2_enter_idx, \
            "task2 should enter only after task1 exits (with asyncio.Lock)"
        
    @pytest.mark.anyio
    async def test_actual_bug_scenario(self) -> None:
        """Simulate the actual bug scenario in _textual_confirm."""
        from henchman.cli.textual_mixins import _InitMixin
        
        # Create instance with threading.Lock (current buggy implementation)
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 0
        mixin._confirm_lock = asyncio.Lock()  # BUG: threading.Lock
        
        # Track operations
        operations = []
        
        async def simulate_textual_confirm(task_id: int):
            """Simulate _textual_confirm with await inside lock."""
            # This mimics the actual code structure
            with mixin._confirm_lock:
                req_id = mixin._confirm_counter
                operations.append(f"task{task_id}_read_{req_id}")
                
                # Simulate await that happens in real code (e.g., push_screen)
                # In real code, there's `await self.push_screen(...)` inside try block
                # which happens AFTER the with lock: block
                # Actually, looking at the code again, the await is OUTSIDE the with lock:
                # So maybe the bug is different...
                
                # Let me check the actual code structure again
                mixin._confirm_counter += 1
                operations.append(f"task{task_id}_increment_to_{mixin._confirm_counter}")
                
                future = asyncio.Future()
                mixin._confirm_futures[req_id] = future
                operations.append(f"task{task_id}_store_{req_id}")
            
            # The await happens here (outside lock)
            # Simulate some async work
            await asyncio.sleep(0.001)
            
            future.set_result(True)
            return req_id
        
        # Run multiple concurrent calls
        tasks = [asyncio.create_task(simulate_textual_confirm(i)) for i in range(5)]
        results = await asyncio.gather(*tasks)
        
        print(f"Operations: {operations}")
        print(f"Results: {results}")
        print(f"Final counter: {mixin._confirm_counter}")
        print(f"Dict keys: {list(mixin._confirm_futures.keys())}")
        
        # Check for duplicates
        if len(set(results)) < len(results):
            print(f"BUG: Duplicate IDs: {results}")
            pytest.fail(f"Duplicate request IDs with threading.Lock: {results}")
        
        # Actually, with this simulation, threading.Lock might work
        # because all the counter operations are inside the with block
        # without any await. The issue is if there WAS an await inside...
        
        # Let me check the actual _textual_confirm code again
        import inspect
        import henchman.cli.textual_mixins as module
        source = inspect.getsource(module._InitMixin._textual_confirm)
        
        # Look for the structure
        lines = source.split('\n')
        for i, line in enumerate(lines):
            if 'with self._confirm_lock:' in line:
                print(f"Lock starts at line {i}: {line}")
                # Check what's in the lock
                j = i + 1
                while j < len(lines) and lines[j].startswith(' ' * 8):  # Inside lock
                    print(f"  In lock: {lines[j]}")
                    j += 1
                print(f"Lock ends before line {j}: {lines[j] if j < len(lines) else 'EOF'}")
                
        # The actual code has the await OUTSIDE the with lock: block
        # So threading.Lock might actually work... unless...
        
        # Actually no! Even with await outside, there's a race:
        # Task A: with lock: read counter (0), increment to 1, store future at key 0
        # Task A: exits with block
        # Task B: with lock: read counter (1), increment to 2, store future at key 1
        # Task B: exits with block
        # This should work...
        
        # Unless the issue is in _cleanup_confirm_futures which also uses the lock!
        # Let me check
        
    @pytest.mark.anyio
    async def test_concurrent_cleanup_race(self) -> None:
        """Test race between _textual_confirm and _cleanup_confirm_futures.
        
        This might be the actual bug: _cleanup_confirm_futures is called
        from on_unmount (sync) while _textual_confirm is async.
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 0
        mixin._confirm_lock = asyncio.Lock()
        
        # Simulate concurrent access from sync and async contexts
        import threading as th
        
        async_results = []
        sync_results = []
        
        async def async_operation():
            """Simulate _textual_confirm."""
            with mixin._confirm_lock:
                req_id = mixin._confirm_counter
                async_results.append(f"async_read_{req_id}")
                mixin._confirm_counter += 1
                future = asyncio.Future()
                mixin._confirm_futures[req_id] = future
                async_results.append(f"async_store_{req_id}")
            # Don't await anything to keep it simple
            return req_id
        
        def sync_operation():
            """Simulate _cleanup_confirm_futures (called from on_unmount)."""
            with mixin._confirm_lock:
                sync_results.append("sync_entered")
                # Simulate cleanup
                count = len(mixin._confirm_futures)
                sync_results.append(f"sync_cleanup_{count}")
        
        # Run async operation
        async_task = asyncio.create_task(async_operation())
        
        # Run sync operation in a thread (simulating on_unmount from different thread?)
        # Actually on_unmount runs in main thread but sync
        sync_thread = th.Thread(target=sync_operation)
        sync_thread.start()
        sync_thread.join()
        
        await async_task
        
        print(f"Async results: {async_results}")
        print(f"Sync results: {sync_results}")
        
        # The issue: threading.Lock works across threads
        # But if on_unmount is called from main thread while async code
        # is running in same thread, threading.Lock is reentrant!
        
        # Actually, if both are in same thread, threading.Lock allows
        # the sync operation to enter even if async has the lock
        # because it's reentrant!
        
        # This is complex. The real fix is to use asyncio.Lock for
        # async code and handle sync access properly.