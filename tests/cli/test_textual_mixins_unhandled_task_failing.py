"""Failing test for unhandled task bug - should FAIL with current implementation."""

from __future__ import annotations

import asyncio
import inspect
import pytest


class TestUnhandledTaskBugFailing:
    """Test that fails due to unhandled task bug."""
    
    def test_callback_creates_unhandled_task(self) -> None:
        """Test that _callback creates unhandled task.
        
        This test should FAIL with current implementation.
        """
        import henchman.cli.textual_mixins as module
        
        # Get source of _textual_confirm
        source = inspect.getsource(module._InitMixin._textual_confirm)
        
        # Check for the bug pattern: asyncio.create_task() without storing result
        # Look for: asyncio.create_task(remove_from_dict())
        # But NOT: task = asyncio.create_task(remove_from_dict())
        
        lines = source.split('\n')
        bug_found = False
        
        for i, line in enumerate(lines):
            if 'asyncio.create_task(' in line:
                # Check if it's assigned to a variable
                # Look at previous lines/current line for assignment
                line_before = lines[i-1] if i > 0 else ""
                current_line = line
                
                # Check if there's an assignment on this line
                if '=' in current_line.split('asyncio.create_task(')[0]:
                    # Probably assigned, e.g., "task = asyncio.create_task(...)"
                    continue
                # Check if previous line ends with assignment
                elif line_before.strip().endswith('='):
                    # Assignment on previous line
                    continue
                else:
                    # Found unhandled task creation!
                    bug_found = True
                    print(f"BUG FOUND at line {i+1}: {line.strip()}")
                    print("This creates an unhandled asyncio task that can cause warnings.")
        
        # This test should FAIL if bug exists
        assert not bug_found, \
            "Bug found: _callback creates unhandled asyncio task with asyncio.create_task()"
    
    def test_fix_implementation(self) -> None:
        """Show what the fixed implementation should do."""
        print("\n" + "="*60)
        print("REQUIRED FIX FOR BUG")
        print("="*60)
        
        print("\nCurrent buggy pattern in _callback:")
        print('''
            async def remove_from_dict():
                async with self._confirm_lock:
                    self._confirm_futures.pop(req_id, None)
            
            asyncio.create_task(remove_from_dict())  # BUG: Unhandled task!
        ''')
        
        print("\nFixed pattern (Option 1 - use call_soon):")
        print('''
            def remove_sync():
                self._confirm_futures.pop(req_id, None)
            
            asyncio.get_running_loop().call_soon(remove_sync)
        ''')
        
        print("\nFixed pattern (Option 2 - store task):")
        print('''
            async def remove_from_dict():
                async with self._confirm_lock:
                    self._confirm_futures.pop(req_id, None)
            
            task = asyncio.create_task(remove_from_dict())
            # Store task to prevent garbage collection warning
            if not hasattr(self, '_pending_tasks'):
                self._pending_tasks = set()
            self._pending_tasks.add(task)
            task.add_done_callback(lambda t: self._pending_tasks.discard(t))
        ''')
        
        print("\nRecommendation: Use Option 1 (call_soon) - simpler.")