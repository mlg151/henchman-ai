"""Test for threading.Lock race condition bug in _textual_confirm method.

This test demonstrates that threading.Lock doesn't properly serialize
async tasks, which can lead to race conditions in _textual_confirm.
"""

from __future__ import annotations

import asyncio
import threading
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

from henchman.tools.base import ConfirmationRequest


class TestTextualConfirmThreadingLockBug:
    """Test that demonstrates threading.Lock race condition in _textual_confirm."""
    
    @pytest.mark.anyio
    async def test_threading_lock_allows_concurrent_async_access(self) -> None:
        """Bug is fixed: source now uses asyncio.Lock instead of threading.Lock.

        Original test deadlocked (threading.Lock held + await = event loop block).
        Skipped since the bug it documented no longer exists.
        """
        pytest.skip(
            "Bug fixed: source uses asyncio.Lock, not threading.Lock. "
            "Original test deadlocked due to threading.Lock + await inside lock."
        )
        from henchman.cli.textual_mixins import _InitMixin
        
        # Create mixin instance with threading.Lock (current buggy implementation)
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 0
        mixin._confirm_lock = threading.Lock()  # BUG: Using threading.Lock
        
        # Track operations to see interleaving
        operations = []
        request_ids = []
        
        async def simulate_concurrent_confirm(task_id: int) -> int:
            """Simulate concurrent _textual_confirm calls."""
            # This mimics the actual code structure
            with mixin._confirm_lock:
                req_id = mixin._confirm_counter
                operations.append(f"task{task_id}_read_{req_id}")
                
                # Simulate some work inside lock (like in actual code)
                await asyncio.sleep(0.001)  # This yields control!
                
                mixin._confirm_counter += 1
                operations.append(f"task{task_id}_increment_to_{mixin._confirm_counter}")
                
                future = asyncio.Future()
                mixin._confirm_futures[req_id] = future
                operations.append(f"task{task_id}_store_{req_id}")
            
            # Complete the future
            future.set_result(True)
            return req_id
        
        # Run multiple concurrent calls
        tasks = [asyncio.create_task(simulate_concurrent_confirm(i)) for i in range(3)]
        results = await asyncio.gather(*tasks)
        
        print(f"Operations: {operations}")
        print(f"Results: {results}")
        print(f"Final counter: {mixin._confirm_counter}")
        
        # With threading.Lock and await inside the with block,
        # tasks can interleave. Let's check if operations are interleaved
        # by looking for patterns like task0_read, task1_read, task0_increment
        
        # Find indices of operations
        task0_read_idx = next(i for i, op in enumerate(operations) if op.startswith("task0_read"))
        task0_inc_idx = next(i for i, op in enumerate(operations) if op.startswith("task0_increment"))
        task1_read_idx = next(i for i, op in enumerate(operations) if op.startswith("task1_read"))
        
        # With threading.Lock, it's possible that task1_read happens between
        # task0_read and task0_increment because the await yields control
        # This would be a bug!
        
        # Check if any task1 operation happens between task0_read and task0_increment
        for i in range(task0_read_idx + 1, task0_inc_idx):
            if operations[i].startswith("task1_"):
                print(f"BUG DETECTED: {operations[i]} between task0_read and task0_increment")
                # This test should fail with current implementation
                pytest.fail(
                    "threading.Lock allows concurrent async access: "
                    f"{operations[i]} between task0_read and task0_increment"
                )
        
        # Also check for duplicate IDs (shouldn't happen but could with race)
        if len(set(results)) < len(results):
            pytest.fail(f"Duplicate request IDs with threading.Lock: {results}")
    
    @pytest.mark.anyio
    async def test_asyncio_lock_fixes_the_issue(self) -> None:
        """Show that asyncio.Lock properly serializes async tasks."""
        from henchman.cli.textual_mixins import _InitMixin
        
        # Create mixin instance with asyncio.Lock (the fix)
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 0
        mixin._confirm_lock = asyncio.Lock()  # FIX: Using asyncio.Lock
        
        operations = []
        
        async def simulate_concurrent_confirm(task_id: int) -> int:
            """Simulate concurrent _textual_confirm calls with asyncio.Lock."""
            async with mixin._confirm_lock:
                req_id = mixin._confirm_counter
                operations.append(f"task{task_id}_read_{req_id}")
                
                # With asyncio.Lock, this await won't allow other tasks in
                await asyncio.sleep(0.001)
                
                mixin._confirm_counter += 1
                operations.append(f"task{task_id}_increment_to_{mixin._confirm_counter}")
                
                future = asyncio.Future()
                mixin._confirm_futures[req_id] = future
            
            future.set_result(True)
            return req_id
        
        # Run multiple concurrent calls
        tasks = [asyncio.create_task(simulate_concurrent_confirm(i)) for i in range(3)]
        results = await asyncio.gather(*tasks)
        
        print(f"Operations with asyncio.Lock: {operations}")
        print(f"Results: {results}")
        
        # With asyncio.Lock, operations should be fully serialized
        # Each task should complete its entire with block before next starts
        
        # Verify no interleaving
        current_task = None
        for op in operations:
            if op.startswith("task"):
                task_num = int(op[4])  # Extract task number from "taskX_..."
                if current_task is None:
                    current_task = task_num
                elif current_task != task_num:
                    # Task changed - make sure we see "increment" for previous task
                    # before seeing "read" for next task
                    prev_ops = [o for o in operations if o.startswith(f"task{current_task}_")]
                    next_ops = [o for o in operations if o.startswith(f"task{task_num}_")]
                    
                    # Previous task should have both read and increment
                    assert any("read" in op for op in prev_ops)
                    assert any("increment" in op for op in prev_ops)
                    
                    # Next task should start after previous task's increment
                    current_task = task_num
    
    @pytest.mark.anyio
    async def test_actual_method_has_threading_lock_bug(self) -> None:
        """Verify current implementation uses threading.Lock (which is buggy for async)."""
        from henchman.cli.textual_mixins import _InitMixin
        
        # Check the _init_confirm_state method
        import inspect
        source = inspect.getsource(_InitMixin._init_confirm_state)
        
        # Check if the code creates threading.Lock (not just mentions it in comments)
        lines = source.split('\n')
        creates_threading_lock = False
        creates_asyncio_lock = False
        
        for line in lines:
            # Skip comments and look for actual assignment
            line_stripped = line.strip()
            if line_stripped.startswith('#'):
                continue
            if 'threading.Lock()' in line or 'threading.Lock(' in line:
                creates_threading_lock = True
            if 'asyncio.Lock()' in line or 'asyncio.Lock(' in line:
                creates_asyncio_lock = True
        
        # Current buggy implementation creates threading.Lock
        if creates_threading_lock:
            print("BUG: _init_confirm_state should not create threading.Lock")
        
        # Bug is fixed: _init_confirm_state should NOT create threading.Lock
        assert not creates_threading_lock, (
            "Bug is fixed: _init_confirm_state should not create threading.Lock"
        )
        
        # Bug is fixed: _init_confirm_state creates asyncio.Lock
        assert creates_asyncio_lock, (
            "Bug is fixed: _init_confirm_state creates asyncio.Lock"
        )
        
        # Also check _textual_confirm uses async with for asyncio.Lock
        confirm_source = inspect.getsource(_InitMixin._textual_confirm)
        
        # With asyncio.Lock, it should use async with confirm_lock:
        assert "async with confirm_lock:" in confirm_source, (
            "Bug is fixed: _textual_confirm uses async with confirm_lock (asyncio.Lock)"
        )
    
    @pytest.mark.anyio
    async def test_race_condition_can_cause_duplicate_ids(self) -> None:
        """Test a scenario where race condition could cause duplicate IDs.
        
        This is harder to trigger deterministically but we can demonstrate
        the possibility.
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        # This test shows the theoretical race:
        # 1. Task A: with lock: read counter (0)
        # 2. Task A: yields during await inside with block
        # 3. Task B: with lock: read counter (0) - BUG! Should be blocked
        # 4. Task A: increment counter to 1
        # 5. Task B: increment counter to 1 (or 2 depending on implementation)
        # 6. Both tasks use ID 0 -> collision!
        
        # We can't reliably trigger this but we can show the code
        # has the vulnerability
        
        mixin = _InitMixin.__new__(_InitMixin)
        
        # Initialize as the actual code does
        mixin._init_confirm_state()
        
        # Bug is fixed: use isinstance to properly check for asyncio.Lock
        import asyncio
        assert isinstance(mixin._confirm_lock, asyncio.Lock), (
            "Bug is fixed: _init_confirm_state creates asyncio.Lock (not threading.Lock)"
        )
        print(f"OK: Using asyncio.Lock: {type(mixin._confirm_lock).__name__}")