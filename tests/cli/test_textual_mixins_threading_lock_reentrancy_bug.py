"""Test demonstrating the threading.Lock reentrancy bug in _textual_confirm."""

from __future__ import annotations

import asyncio
import threading
import pytest


class TestThreadingLockReentrancyBug:
    """Test that demonstrates threading.Lock reentrancy bug."""
    
    @pytest.mark.anyio
    async def test_threading_lock_allows_reentrancy_in_async(self) -> None:
        """Demonstrate that threading.Lock allows reentrancy across async tasks."""
        lock = threading.Lock()
        acquisition_order = []
        
        async def task1():
            with lock:
                acquisition_order.append("task1_enter")
                await asyncio.sleep(0.01)  # Yield control
                acquisition_order.append("task1_exit")
        
        async def task2():
            await asyncio.sleep(0.001)  # Let task1 acquire lock first
            with lock:
                acquisition_order.append("task2_enter")
                acquisition_order.append("task2_exit")
        
        await asyncio.gather(task1(), task2())
        
        # With threading.Lock, task2 can enter while task1 holds the lock
        # This is the bug!
        task1_enter_idx = acquisition_order.index("task1_enter")
        task1_exit_idx = acquisition_order.index("task1_exit")
        task2_enter_idx = acquisition_order.index("task2_enter")
        
        # This will FAIL with threading.Lock
        assert task1_exit_idx < task2_enter_idx, \
            "BUG: threading.Lock allows reentrancy across async tasks"
        
    @pytest.mark.anyio
    async def test_asyncio_lock_properly_serializes(self) -> None:
        """Show that asyncio.Lock properly serializes async tasks."""
        lock = asyncio.Lock()
        acquisition_order = []
        
        async def task1():
            async with lock:
                acquisition_order.append("task1_enter")
                await asyncio.sleep(0.01)
                acquisition_order.append("task1_exit")
        
        async def task2():
            await asyncio.sleep(0.001)
            async with lock:
                acquisition_order.append("task2_enter")
                acquisition_order.append("task2_exit")
        
        await asyncio.gather(task1(), task2())
        
        task1_enter_idx = acquisition_order.index("task1_enter")
        task1_exit_idx = acquisition_order.index("task1_exit")
        task2_enter_idx = acquisition_order.index("task2_enter")
        
        assert task1_enter_idx < task1_exit_idx
        assert task1_exit_idx < task2_enter_idx  # This passes with asyncio.Lock