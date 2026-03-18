"""Test for incorrect asyncio.CancelledError suppression in _textual_confirm callback."""

from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import MagicMock

import pytest

from henchman.cli.textual_mixins import _InitMixin
from henchman.tools.base import ConfirmationRequest


class TestCancelledErrorSuppressionBug:
    """Test that demonstrates the incorrect suppression of asyncio.CancelledError."""

    def test_future_set_result_never_raises_cancelled_error(self) -> None:
        """Test that future.set_result() never raises asyncio.CancelledError.
        
        This is the core bug: the code suppresses asyncio.CancelledError
        when calling future.set_result(), but set_result() doesn't raise it.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            future = asyncio.Future()
            
            # Test 1: set_result on pending future
            future.set_result(True)
            assert future.done()
            assert future.result() is True
            
            # Test 2: set_result on already-done future raises InvalidStateError
            future2 = asyncio.Future()
            future2.set_result(False)
            with pytest.raises(asyncio.InvalidStateError):
                future2.set_result(True)  # Can't set result twice
            
            # Test 3: set_result never raises CancelledError
            future3 = asyncio.Future()
            # Even if we cancel it first...
            future3.cancel()
            # set_result on cancelled future raises InvalidStateError, not CancelledError
            with pytest.raises(asyncio.InvalidStateError):
                future3.set_result(True)
            
            # Test 4: What does raise CancelledError?
            future4 = asyncio.Future()
            future4.cancel()
            # Awaiting a cancelled future raises CancelledError
            async def test_await():
                with pytest.raises(asyncio.CancelledError):
                    await future4
            
            loop.run_until_complete(test_await())
            
            print("✓ Verified: future.set_result() raises InvalidStateError, not CancelledError")
            
        finally:
            loop.close()

    def test_callback_suppression_logic(self) -> None:
        """Test the actual callback logic from _textual_confirm."""
        # Create a mock to test the callback logic
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            future = asyncio.Future()
            
            # Simulate the callback from _textual_confirm
            def callback(result: object | None) -> None:
                with contextlib.suppress(asyncio.InvalidStateError, asyncio.CancelledError):
                    if result is True:
                        future.set_result(True)
                    elif result is False or result is None:
                        future.set_result(False)
                    else:
                        future.set_result(False)
            
            # Test normal operation
            callback(True)
            assert future.done()
            assert future.result() is True
            
            # Reset for next test
            future2 = asyncio.Future()
            def callback2(result: object | None) -> None:
                with contextlib.suppress(asyncio.InvalidStateError, asyncio.CancelledError):
                    if result is True:
                        future2.set_result(True)
                    elif result is False or result is None:
                        future2.set_result(False)
                    else:
                        future2.set_result(False)
            
            # Cancel the future first
            future2.cancel()
            # Callback should suppress InvalidStateError (not CancelledError!)
            callback2(True)
            # future2 was cancelled, so set_result raised InvalidStateError
            # which was suppressed
            assert future2.cancelled()
            
            # The bug: asyncio.CancelledError in suppress list is unnecessary
            # because set_result() doesn't raise it
            
            print("✓ Verified: Callback suppresses InvalidStateError (correct)")
            print("✓ Bug: Callback also suppresses CancelledError (unnecessary)")
            
        finally:
            loop.close()

    @pytest.mark.anyio
    async def test_actual_callback_behavior(self) -> None:
        """Test the actual callback behavior with the real suppression."""
        from henchman.cli.textual_mixins import _InitMixin
        
        # We need to inspect the actual source code
        import inspect
        source = inspect.getsource(_InitMixin._textual_confirm)
        
        # Find the callback definition more precisely
        lines = source.split('\n')
        callback_start = -1
        callback_end = -1
        indent_level = None
        
        for i, line in enumerate(lines):
            if 'def _callback(' in line:
                callback_start = i
                # Find indentation level
                indent_level = len(line) - len(line.lstrip())
                break
        
        if callback_start == -1:
            pytest.fail("Could not find callback definition")
        
        # Find where callback ends (next line at same or less indentation)
        for i in range(callback_start + 1, len(lines)):
            line = lines[i]
            if line.strip():  # Non-empty line
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= indent_level:
                    callback_end = i
                    break
        
        if callback_end == -1:
            callback_end = len(lines)
        
        callback_lines = lines[callback_start:callback_end]
        callback_text = '\n'.join(callback_lines)
        print("Callback source code:")
        print(callback_text)
        
        # Check for the bug (should be fixed)
        # We need to check if asyncio.CancelledError is in the contextlib.suppress line
        import re
        suppress_pattern = r'with contextlib\.suppress\([^)]*\)'
        suppress_match = re.search(suppress_pattern, callback_text)
        
        if suppress_match:
            suppress_line = suppress_match.group(0)
            print(f"\nFound suppress line: {suppress_line}")
            
            if 'asyncio.CancelledError' in suppress_line:
                print("\n✗ BUG STILL EXISTS: Callback suppresses asyncio.CancelledError")
                print("  But future.set_result() doesn't raise CancelledError!")
                print("  It only raises InvalidStateError.")
                
                # This test should fail if bug not fixed
                assert False, "Callback incorrectly suppresses asyncio.CancelledError"
            else:
                print("\n✓ BUG FIXED: Callback no longer suppresses asyncio.CancelledError")
                print("  Only InvalidStateError is suppressed (correct)")
        else:
            print("\nCould not find contextlib.suppress in callback")
            pytest.fail("Could not find contextlib.suppress in callback")