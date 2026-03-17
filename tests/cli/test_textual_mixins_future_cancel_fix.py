"""Test for the future.cancel() fix in _cleanup_confirm_futures.

Verifies that future.cancel() is called without unnecessary done() check.
"""

from __future__ import annotations

import asyncio
import threading
import pytest


class TestFutureCancelFix:
    """Test that verifies the fix for TOCTOU race condition."""
    
    def test_cancel_called_directly(self) -> None:
        """Verify that future.cancel() is called without done() check.
        
        This test checks the source code to ensure the fix is applied.
        """
        import inspect
        import henchman.cli.textual_mixins as module
        
        # Get _cleanup_confirm_futures source
        source = inspect.getsource(module._InitMixin._cleanup_confirm_futures)
        
        print("Checking _cleanup_confirm_futures implementation...")
        
        # Check that we don't have the buggy pattern
        buggy_pattern = "if not future.done():"
        if buggy_pattern in source:
            pytest.fail(f"Bug still present: Found '{buggy_pattern}' in _cleanup_confirm_futures")
        
        # Check that we call future.cancel() directly
        if "future.cancel()" not in source:
            pytest.fail("future.cancel() not found in _cleanup_confirm_futures")
        
        # Count how many times future.cancel() appears
        cancel_count = source.count("future.cancel()")
        print(f"future.cancel() appears {cancel_count} times in source")
        
        # Should appear at least twice (once in if block, once in else block)
        assert cancel_count >= 2, f"Expected at least 2 future.cancel() calls, found {cancel_count}"
        
        print("✓ Fix verified: future.cancel() called without unnecessary done() check")
    
    @pytest.mark.anyio
    async def test_cancel_idempotent(self) -> None:
        """Test that future.cancel() is idempotent (the basis for the fix)."""
        loop = asyncio.get_running_loop()
        
        # Test 1: Cancel pending future
        future1 = loop.create_future()
        assert not future1.done()
        future1.cancel()
        assert future1.done()
        assert future1.cancelled()
        
        # Cancel again (idempotent)
        future1.cancel()
        assert future1.cancelled()
        
        # Test 2: Cancel on completed future (with result)
        future2 = loop.create_future()
        future2.set_result(42)
        assert future2.done()
        assert not future2.cancelled()
        
        # Cancel should be safe no-op
        future2.cancel()
        assert future2.done()
        assert not future2.cancelled()  # Still not cancelled
        assert future2.result() == 42
        
        # Test 3: Cancel on completed future (with exception)
        future3 = loop.create_future()
        future3.set_exception(ValueError("test"))
        assert future3.done()
        
        future3.cancel()  # Safe no-op
        assert future3.done()
        assert not future3.cancelled()
        
        print("✓ future.cancel() is idempotent as expected")
    
    def test_cleanup_with_mixed_futures(self) -> None:
        """Test that cleanup works with mixed done/not-done futures."""
        from henchman.cli.textual_mixins import _InitMixin
        
        # Create instance
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        import threading
        mixin._confirm_lock = threading.Lock()
        
        # Create event loop for futures
        loop = asyncio.new_event_loop()
        try:
            # Create mixed futures
            pending_future = loop.create_future()
            completed_future = loop.create_future()
            completed_future.set_result("done")
            cancelled_future = loop.create_future()
            cancelled_future.cancel()
            
            mixin._confirm_futures[1] = pending_future
            mixin._confirm_futures[2] = completed_future
            mixin._confirm_futures[3] = cancelled_future
            
            # Call cleanup
            mixin._cleanup_confirm_futures()
            
            # All futures should be in final state
            assert pending_future.done()
            assert pending_future.cancelled()
            
            assert completed_future.done()
            assert not completed_future.cancelled()
            assert completed_future.result() == "done"
            
            assert cancelled_future.done()
            assert cancelled_future.cancelled()
            
            # Dictionary should be empty
            assert not mixin._confirm_futures
            
            print("✓ Cleanup works correctly with mixed futures")
            
        finally:
            loop.close()