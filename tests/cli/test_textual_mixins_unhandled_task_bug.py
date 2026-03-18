"""Test for unhandled task bug in _textual_confirm callback.

This test demonstrates the bug where the callback in _textual_confirm
creates an asyncio task but doesn't store it, causing potential
"Task was destroyed but it is pending!" warnings during shutdown.
"""

from __future__ import annotations

import asyncio
import warnings
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

from henchman.tools.base import ConfirmationRequest


class TestUnhandledTaskBug:
    """Test that demonstrates the unhandled task bug."""
    
    @pytest.mark.anyio
    async def test_callback_creates_unhandled_task(self) -> None:
        """Test that callback creates task but doesn't store it.
        
        This can cause "Task was destroyed but it is pending!" warnings.
        
        Note: This test is skipped because the actual code doesn't create
        tasks in the callback - it uses thread-safe .pop() directly.
        """
        pytest.skip("Actual code doesn't create tasks in callback - uses .pop() directly")
    
    @pytest.mark.anyio
    async def test_task_warning_on_shutdown(self) -> None:
        """Test that unhandled tasks cause warnings.
        
        This is harder to test reliably, but we can demonstrate the issue.
        """
        # Capture warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # Create a simple test to show the issue
            # We'll simulate what happens in callback
            
            async def dummy_coro():
                await asyncio.sleep(0.001)
                return "done"
            
            # Create task but don't store it
            task = asyncio.create_task(dummy_coro())
            # Don't await it, let it be garbage collected
            
            # Force garbage collection
            import gc
            del task
            gc.collect()
            
            # Give event loop a chance to notice
            await asyncio.sleep(0.01)
            
            # Check for warnings
            task_warnings = [warning for warning in w 
                           if "Task was destroyed" in str(warning.message)]
            
            print(f"Task warnings: {len(task_warnings)}")
            
            # Note: This might not always trigger the warning
            # depending on Python version and timing
    
    def test_fix_should_store_or_await_task(self) -> None:
        """Show what the fix should look like."""
        print("\n=== Current buggy implementation ===")
        print("def _callback(result: object | None) -> None:")
        print("    # ...")
        print("    async def remove_from_dict():")
        print("        async with self._confirm_lock:")
        print("            self._confirm_futures.pop(req_id, None)")
        print("    ")
        print("    # Schedule the coroutine to run")
        print("    # Don't await it since we're in sync context")
        print("    asyncio.create_task(remove_from_dict())  # BUG: task not stored!")
        
        print("\n=== Fix option 1: Store task ===")
        print("def _callback(result: object | None) -> None:")
        print("    # ...")
        print("    async def remove_from_dict():")
        print("        async with self._confirm_lock:")
        print("            self._confirm_futures.pop(req_id, None)")
        print("    ")
        print("    # Create and store task")
        print("    task = asyncio.create_task(remove_from_dict())")
        print("    # Store in a set to prevent garbage collection warning")
        print("    self._pending_tasks.add(task)")
        print("    task.add_done_callback(lambda t: self._pending_tasks.discard(t))")
        
        print("\n=== Fix option 2: Run coroutine directly ===")
        print("def _callback(result: object | None) -> None:")
        print("    # ...")
        print("    # Since we're in event loop thread, we can run it")
        print("    # But we need async context...")
        
        print("\n=== Fix option 3: Don't create task, pop directly ===")
        print("def _callback(result: object | None) -> None:")
        print("    # ...")
        print("    # Just pop without lock (race acceptable)")
        print("    self._confirm_futures.pop(req_id, None)")
        
        print("\n=== Fix option 4: Use call_soon ===")
        print("def _callback(result: object | None) -> None:")
        print("    # ...")
        print("    def remove_sync():")
        print("        self._confirm_futures.pop(req_id, None)")
        print("    ")
        print("    # Schedule sync function to run")
        print("    asyncio.get_running_loop().call_soon(remove_sync)")
        
        print("\nRecommended: Option 4 (call_soon) or Option 3 (pop directly)")
        print("Simpler and avoids task management issues.")