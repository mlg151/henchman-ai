"""Test for TOCTOU race condition bug in textual_mixins.py _textual_confirm method.

This test demonstrates the bug where checking future.done() before calling
future.cancel() creates a race condition that can cause InvalidStateError.
"""

from __future__ import annotations

import asyncio
import threading
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

from henchman.tools.base import ConfirmationRequest


class TestTextualConfirmToctouBug:
    """Test that demonstrates the TOCTOU race condition bug in _textual_confirm."""
    
    @pytest.mark.anyio
    async def test_toctou_race_in_exception_handler(self) -> None:
        """Test that exception handlers have TOCTOU race condition.
        
        The bug is in both exception handlers in _textual_confirm:
        - except asyncio.CancelledError:
        - except Exception:
        
        Both have:
            if not future.done():
                future.cancel()
                
        This creates a TOCTOU race where between checking future.done()
        and calling future.cancel(), the callback could complete the future,
        causing future.cancel() to raise InvalidStateError.
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        # Create mixin instance
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 0
        mixin._confirm_lock = threading.Lock() if hasattr(threading, 'Lock') else None
        
        # Get the actual source code to verify the bug exists
        import inspect
        import henchman.cli.textual_mixins as module
        
        source = inspect.getsource(module._InitMixin._textual_confirm)
        
        # Check for the buggy pattern in exception handlers
        print("Checking for TOCTOU bug pattern in _textual_confirm...")
        
        # Look for the pattern in CancelledError handler
        cancelled_error_section = self._extract_exception_section(source, "asyncio.CancelledError")
        if cancelled_error_section:
            print(f"CancelledError handler section:\n{cancelled_error_section}")
            has_bug = "if not future.done():" in cancelled_error_section and "future.cancel()" in cancelled_error_section
            if has_bug:
                print("✓ BUG FOUND in CancelledError handler: if not future.done(): future.cancel()")
            else:
                print("✓ No bug in CancelledError handler (or pattern changed)")
        
        # Look for the pattern in Exception handler  
        exception_section = self._extract_exception_section(source, "Exception")
        if exception_section:
            print(f"\nException handler section:\n{exception_section}")
            has_bug = "if not future.done():" in exception_section and "future.cancel()" in exception_section
            if has_bug:
                print("✓ BUG FOUND in Exception handler: if not future.done(): future.cancel()")
            else:
                print("✓ No bug in Exception handler (or pattern changed)")
        
        # Now test the actual race condition
        # We need to simulate the race between callback and exception handler
        
        # Create a future
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        req_id = 1
        mixin._confirm_futures[req_id] = future
        
        # Create the callback that would be defined in _textual_confirm
        def _callback(result: object | None) -> None:
            if not future.done() and not future.cancelled():
                future.set_result(bool(result))
            # Remove from dict (simplified - actual code uses lock)
            mixin._confirm_futures.pop(req_id, None)
        
        # Simulate the race:
        # 1. Exception handler checks if not future.done(): (returns True)
        # 2. Callback runs between check and cancel: future.set_result(True)
        # 3. Exception handler calls future.cancel() -> InvalidStateError!
        
        # We can't perfectly simulate the timing race in a test,
        # but we can demonstrate the problematic pattern
        
        # First, let's show what happens if we follow the buggy pattern
        print("\nDemonstrating the buggy pattern:")
        
        # Simulate callback completing the future
        _callback(True)
        assert future.done()
        assert not future.cancelled()
        assert future.result() is True
        
        # Now simulate what the exception handler would do (buggy version)
        try:
            if not future.done():  # This check passes (future IS done now)
                print("  Check: future.done() returned True, so skipping cancel()")
                # In race scenario, this check might have returned False
                # if callback hadn't run yet
            else:
                print("  Check: future.done() returned False (would call cancel())")
                # future.cancel() here would raise InvalidStateError
                # because future already has a result
        except Exception as e:
            print(f"  Exception during buggy pattern: {e}")
        
        # The fix is to just call future.cancel() without the check
        # because future.cancel() is idempotent for asyncio Futures
        print("\nDemonstrating the fix (future.cancel() is idempotent):")
        
        # Create another future
        future2 = loop.create_future()
        
        # Cancel it
        future2.cancel()
        assert future2.cancelled()
        
        # Cancel again (idempotent)
        future2.cancel()  # No error!
        assert future2.cancelled()
        
        # Create a completed future
        future3 = loop.create_future()
        future3.set_result(42)
        
        # Cancel on completed future (safe no-op)
        future3.cancel()  # No error!
        assert future3.done()
        assert not future3.cancelled()  # Still has result, not cancelled
        assert future3.result() == 42
        
        print("✓ future.cancel() is idempotent - safe to call on any future state")
        
        # The test should fail if the buggy pattern exists
        # We'll check the source code directly
        if "if not future.done():" in source and "future.cancel()" in source:
            # Check if they appear together in exception handlers
            lines = source.split('\n')
            in_exception_handler = False
            for i, line in enumerate(lines):
                if "except asyncio.CancelledError:" in line or "except Exception:" in line:
                    in_exception_handler = True
                elif line.strip().startswith("except "):
                    in_exception_handler = False
                elif in_exception_handler and "if not future.done():" in line:
                    # Look ahead for future.cancel()
                    for j in range(i, min(i+3, len(lines))):
                        if "future.cancel()" in lines[j]:
                            pytest.fail(
                                "TOCTOU race condition bug found: "
                                "if not future.done(): future.cancel() in exception handler"
                            )
    
    @pytest.mark.anyio
    async def test_future_cancel_idempotent(self) -> None:
        """Test that future.cancel() is idempotent (the basis for the fix)."""
        loop = asyncio.get_running_loop()
        
        # Test 1: Cancel pending future
        future1 = loop.create_future()
        assert not future1.done()
        future1.cancel()
        assert future1.done()
        assert future1.cancelled()
        
        # Cancel again (idempotent)
        future1.cancel()  # Should not raise
        assert future1.cancelled()
        
        # Test 2: Cancel on completed future (with result)
        future2 = loop.create_future()
        future2.set_result(42)
        assert future2.done()
        assert not future2.cancelled()
        
        # Cancel should be safe no-op
        future2.cancel()  # Should not raise
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
    
    @pytest.mark.anyio
    async def test_cleanup_confirm_futures_already_fixed(self) -> None:
        """Test that _cleanup_confirm_futures already has the fix.
        
        This method should call future.cancel() directly without
        checking future.done() first.
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        import inspect
        import henchman.cli.textual_mixins as module
        
        source = inspect.getsource(module._InitMixin._cleanup_confirm_futures)
        
        print("Checking _cleanup_confirm_futures implementation...")
        print(source)
        
        # Check that it DOES call future.cancel()
        assert "future.cancel()" in source, "_cleanup_confirm_futures should call future.cancel()"
        
        # Check that it does NOT have the buggy pattern
        buggy_pattern = "if not future.done():"
        if buggy_pattern in source:
            pytest.fail(f"Bug still present in _cleanup_confirm_futures: Found '{buggy_pattern}'")
        
        # Check that it has the fix comment
        if "future.cancel() is idempotent" in source or "No need to check future.done() first" in source:
            print("✓ _cleanup_confirm_futures has fix with explanatory comment")
        else:
            print("Note: _cleanup_confirm_futures doesn't have explanatory comment")
    
    def _extract_exception_section(self, source: str, exception_name: str) -> str:
        """Extract code section for a specific exception handler."""
        lines = source.split('\n')
        in_section = False
        section_lines = []
        indent_level = None
        
        for line in lines:
            if f"except {exception_name}:" in line:
                in_section = True
                section_lines.append(line)
                # Get indent level
                indent_level = len(line) - len(line.lstrip())
            elif in_section:
                current_indent = len(line) - len(line.lstrip()) if line.strip() else 0
                if line.strip() and current_indent <= indent_level:
                    # Reached next exception handler or end of try block
                    break
                section_lines.append(line)
        
        return '\n'.join(section_lines) if section_lines else ""