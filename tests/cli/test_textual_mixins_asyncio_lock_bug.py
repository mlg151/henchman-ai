"""Test that demonstrates the asyncio.Lock usage bug in textual_mixins.py.

The bug: Code uses asyncio.Lock but tries to use it with 'with' instead of 'async with'
in sync contexts (_cleanup_confirm_futures, callbacks, exception handlers).
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch
import pytest

from henchman.tools.base import ConfirmationRequest


class TestAsyncioLockBug:
    """Test that asyncio.Lock is misused in sync contexts."""
    
    def test_cleanup_confirm_futures_uses_with_on_asyncio_lock(self) -> None:
        """Test that _cleanup_confirm_futures tries to use 'with' on asyncio.Lock.
        
        This will raise: 'Lock' object does not support the context manager protocol
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        # Create instance
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 0
        mixin._confirm_lock = asyncio.Lock()  # Current implementation
        
        # Add a future to cleanup
        future = asyncio.Future()
        mixin._confirm_futures[0] = future
        
        # This should fail because asyncio.Lock doesn't support 'with'
        try:
            mixin._cleanup_confirm_futures()
            # If we get here, the test might pass if the code was fixed
            # or if there's a try/except we didn't see
            print("_cleanup_confirm_futures didn't raise - maybe already fixed?")
        except AttributeError as e:
            if "context manager" in str(e) or "Lock" in str(e):
                pytest.fail(f"BUG: _cleanup_confirm_futures uses 'with' on asyncio.Lock: {e}")
            else:
                raise
    
    @pytest.mark.anyio
    async def test_exception_handlers_use_with_on_asyncio_lock(self) -> None:
        """Test that exception handlers in _textual_confirm use 'with' on asyncio.Lock.
        
        We need to actually trigger an exception in _textual_confirm to test this.
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        # Create instance
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 0
        mixin._confirm_lock = asyncio.Lock()
        mixin.push_screen = MagicMock(side_effect=Exception("Test exception"))
        
        # Create request
        request = ConfirmationRequest(
            tool_name="test_tool",
            description="Test tool execution",
            params={"arg": "value"},
            risk_level="high"
        )
        
        # Call _textual_confirm - it should raise our test exception
        # and the exception handler should try to use 'with self._confirm_lock'
        with pytest.raises(Exception, match="Test exception"):
            await mixin._textual_confirm(request)
        
        # The bug would be if AttributeError is raised inside the exception handler
        # But we might not see it because it's caught and re-raised
    
    def test_callback_handles_asyncio_lock(self) -> None:
        """Test that the callback in _textual_confirm handles asyncio.Lock properly.
        
        The callback is sync but needs to access shared state protected by asyncio.Lock.
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        # We need to inspect the source code to check the implementation
        import inspect
        import henchman.cli.textual_mixins as module
        
        source = inspect.getsource(module._InitMixin._textual_confirm)
        
        # Look for the callback definition
        lines = source.split('\n')
        in_callback = False
        callback_lines = []
        
        for line in lines:
            if 'def _callback' in line:
                in_callback = True
            elif in_callback and line.strip() and not line.startswith(' ' * 8):
                # Reached end of callback (less indentation)
                in_callback = False
            
            if in_callback:
                callback_lines.append(line)
        
        callback_source = '\n'.join(callback_lines)
        print(f"Callback source:\n{callback_source}")
        
        # Check if callback tries to use 'with self._confirm_lock:'
        if 'with self._confirm_lock:' in callback_source:
            # Check if it has special handling for asyncio.Lock
            if 'lock.locked()' in callback_source or 'asyncio.get_running_loop()' in callback_source:
                print("Callback has special handling for asyncio.Lock")
            else:
                pytest.fail("BUG: Callback uses 'with' on asyncio.Lock without special handling")
    
    def test_inspect_actual_bug_locations(self) -> None:
        """Inspect the source code to find all bug locations."""
        import inspect
        import henchman.cli.textual_mixins as module
        
        source = inspect.getsource(module._InitMixin)
        
        # Find all uses of 'with self._confirm_lock:'
        lines = source.split('\n')
        bug_locations = []
        
        for i, line in enumerate(lines, 1):
            if 'with self._confirm_lock:' in line:
                # Check context - is it in an async method?
                # Look back for async def
                context = "unknown"
                for j in range(max(0, i-10), i):
                    if 'async def' in lines[j]:
                        context = "async"
                        break
                    elif 'def ' in lines[j] and 'async' not in lines[j]:
                        context = "sync"
                        break
                
                bug_locations.append((i, line.strip(), context))
        
        print(f"Found {len(bug_locations)} uses of 'with self._confirm_lock:':")
        for line_num, line, context in bug_locations:
            print(f"  Line {line_num} ({context}): {line}")
        
        # With asyncio.Lock, 'with' should only be used in sync methods
        # if there's special handling. In async methods, it should be 'async with'
        
        # Check for 'async with self._confirm_lock:'
        async_with_locations = []
        for i, line in enumerate(lines, 1):
            if 'async with self._confirm_lock:' in line:
                async_with_locations.append((i, line.strip()))
        
        print(f"\nFound {len(async_with_locations)} uses of 'async with self._confirm_lock:':")
        for line_num, line in async_with_locations:
            print(f"  Line {line_num}: {line}")
        
        # The bug: if we have asyncio.Lock, all uses should be 'async with'
        # except in sync contexts with special handling
        
        # Actually, thinking about it: the real fix might be to go back to threading.Lock
        # but handle the async reentrancy issue differently. Or use a hybrid approach.