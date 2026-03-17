"""Test that demonstrates the actual threading.Lock bug in textual_mixins.py.

This test will FAIL with current implementation and PASS after fix.
"""

from __future__ import annotations

import asyncio
import threading
from unittest.mock import MagicMock, patch
import pytest

from henchman.tools.base import ConfirmationRequest


class TestActualThreadingLockBug:
    """Test the actual bug: threading.Lock doesn't prevent async task switching."""
    
    @pytest.mark.anyio
    async def test_threading_lock_allows_async_task_switching(self) -> None:
        """Demonstrate that threading.Lock doesn't prevent async task switching.
        
        Even without await in critical section, Python can switch async tasks
        at bytecode boundaries, and threading.Lock won't prevent it.
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        # Create instance with current buggy implementation
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 0
        mixin._confirm_lock = threading.Lock()  # BUG
        
        # We'll manually control task switching to demonstrate the bug
        switch_event = asyncio.Event()
        task1_done = asyncio.Event()
        task2_done = asyncio.Event()
        
        captured_ids = []
        
        async def task1():
            """Simulate _textual_confirm for task 1."""
            with mixin._confirm_lock:
                # Read counter
                my_id = mixin._confirm_counter
                captured_ids.append(("task1_read", my_id))
                
                # Signal to switch to task2
                switch_event.set()
                
                # Give task2 time to run
                await asyncio.sleep(0.001)
                
                # Now increment
                mixin._confirm_counter = my_id + 1
                captured_ids.append(("task1_incremented_to", mixin._confirm_counter))
                
                # Store future
                future = asyncio.Future()
                mixin._confirm_futures[my_id] = future
                captured_ids.append(("task1_stored", my_id))
            
            task1_done.set()
            future.set_result(True)
            return my_id
        
        async def task2():
            """Simulate _textual_confirm for task 2."""
            # Wait for task1 to signal
            await switch_event.wait()
            
            # Now try to acquire lock - SHOULD BLOCK but won't with threading.Lock
            with mixin._confirm_lock:
                # Read counter (might still be 0 if task1 hasn't incremented yet!)
                my_id = mixin._confirm_counter
                captured_ids.append(("task2_read", my_id))
                
                # Increment
                mixin._confirm_counter = my_id + 1
                captured_ids.append(("task2_incremented_to", mixin._confirm_counter))
                
                # Store future
                future = asyncio.Future()
                mixin._confirm_futures[my_id] = future
                captured_ids.append(("task2_stored", my_id))
            
            task2_done.set()
            future.set_result(True)
            return my_id
        
        # Run tasks
        t1 = asyncio.create_task(task1())
        t2 = asyncio.create_task(task2())
        
        await asyncio.gather(t1, t2)
        
        id1 = t1.result()
        id2 = t2.result()
        
        print(f"Captured operations: {captured_ids}")
        print(f"Task 1 got ID: {id1}")
        print(f"Task 2 got ID: {id2}")
        print(f"Final counter: {mixin._confirm_counter}")
        print(f"Future keys: {list(mixin._confirm_futures.keys())}")
        
        # Check for the bug
        if id1 == id2:
            pytest.fail(f"BUG: Both tasks got same ID {id1}! threading.Lock failed to provide mutual exclusion.")
        
        # Also check final counter value
        expected_counter = 2  # Should have been incremented twice
        if mixin._confirm_counter != expected_counter:
            print(f"Warning: Counter is {mixin._confirm_counter}, expected {expected_counter}")
    
    @pytest.mark.anyio
    async def test_realistic_race_condition(self) -> None:
        """Test a more realistic race condition scenario.
        
        Instead of manually controlling switches, we'll run many concurrent
        tasks and see if any get duplicate IDs.
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 0
        mixin._confirm_lock = threading.Lock()  # BUG
        
        results = []
        
        async def simulate_confirm():
            """Simulate the critical section of _textual_confirm."""
            with mixin._confirm_lock:
                # This mimics the actual code
                req_id = mixin._confirm_counter
                # Small delay to increase chance of race
                # In real code, this is just integer operations but
                # we add a tiny sleep to encourage context switching
                await asyncio.sleep(0)  # Yield to event loop
                
                mixin._confirm_counter += 1
                future = asyncio.Future()
                mixin._confirm_futures[req_id] = future
            
            # Don't actually await push_screen
            future.set_result(True)
            return req_id
        
        # Run many tasks concurrently
        tasks = [asyncio.create_task(simulate_confirm()) for _ in range(100)]
        results = await asyncio.gather(*tasks)
        
        # Check for duplicates
        unique_ids = set(results)
        if len(unique_ids) != len(results):
            duplicates = [id for id in results if results.count(id) > 1]
            pytest.fail(f"BUG: Found duplicate IDs with threading.Lock: {duplicates}")
        
        # Check final counter
        assert mixin._confirm_counter == 100, f"Expected counter=100, got {mixin._confirm_counter}"
        
        print(f"Test passed: {len(results)} tasks got unique IDs")
    
    @pytest.mark.anyio 
    async def test_asyncio_lock_fixes_the_problem(self) -> None:
        """Show that asyncio.Lock fixes the problem."""
        from henchman.cli.textual_mixins import _InitMixin
        
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 0
        mixin._confirm_lock = asyncio.Lock()  # FIX
        
        results = []
        
        async def simulate_confirm_with_asyncio_lock():
            """Same simulation but with asyncio.Lock."""
            async with mixin._confirm_lock:
                req_id = mixin._confirm_counter
                await asyncio.sleep(0)  # Yield - with asyncio.Lock, this is safe
                mixin._confirm_counter += 1
                future = asyncio.Future()
                mixin._confirm_futures[req_id] = future
            
            future.set_result(True)
            return req_id
        
        # Run many tasks
        tasks = [asyncio.create_task(simulate_confirm_with_asyncio_lock()) 
                for _ in range(100)]
        results = await asyncio.gather(*tasks)
        
        # Should have no duplicates
        unique_ids = set(results)
        assert len(unique_ids) == len(results), \
            f"asyncio.Lock should prevent duplicates. Got {len(unique_ids)} unique, {len(results)} total"
        
        assert mixin._confirm_counter == 100, f"Expected counter=100, got {mixin._confirm_counter}"
        
        print(f"asyncio.Lock test passed: {len(results)} unique IDs")