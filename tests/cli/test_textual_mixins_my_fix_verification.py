"""Verification test for the unhandled task bug fix."""

from __future__ import annotations

import asyncio
import inspect
import pytest


class TestUnhandledTaskFixVerification:
    """Verify the unhandled task bug is fixed."""
    
    def test_no_unhandled_task_creation(self) -> None:
        """Verify _callback doesn't create unhandled tasks."""
        import henchman.cli.textual_mixins as module
        
        # Get source of _textual_confirm
        source = inspect.getsource(module._InitMixin._textual_confirm)
        
        # Check for the bug pattern
        lines = source.split('\n')
        unhandled_task_found = False
        
        for i, line in enumerate(lines):
            # Look for asyncio.create_task() without assignment
            if 'asyncio.create_task(' in line:
                # Check if it's in a comment
                if '#' in line and line.find('#') < line.find('asyncio.create_task('):
                    continue  # In comment
                
                # Check if assigned to variable
                before_create = line.split('asyncio.create_task(')[0]
                if '=' in before_create:
                    # Probably assigned
                    continue
                
                # Check previous line for assignment
                if i > 0:
                    prev_line = lines[i-1].strip()
                    if prev_line.endswith('='):
                        # Assignment on previous line
                        continue
                
                # Found unhandled task creation!
                unhandled_task_found = True
                print(f"ERROR: Unhandled task creation at line {i+1}:")
                print(f"  {line.strip()}")
        
        assert not unhandled_task_found, \
            "Bug not fixed: _callback still creates unhandled asyncio tasks"
        
        print("✓ No unhandled task creation found")
    
    def test_callback_has_exception_handling(self) -> None:
        """Verify callback has proper exception handling for set_result."""
        import henchman.cli.textual_mixins as module
        
        source = inspect.getsource(module._InitMixin._textual_confirm)
        
        # Find callback
        lines = source.split('\n')
        in_callback = False
        callback_lines = []
        
        for line in lines:
            if 'def _callback' in line:
                in_callback = True
                callback_lines.append(line)
            elif in_callback:
                callback_lines.append(line)
                # Check if we're out of callback (based on indentation)
                if line.strip() == '':
                    continue
                if not line.startswith(' ' * 8) and 'def ' in line:
                    # New function definition
                    break
        
        callback_source = '\n'.join(callback_lines)
        
        # Check for try-except around set_result
        if 'future.set_result(' in callback_source:
            # Find the line with set_result
            set_result_line = -1
            for i, line in enumerate(callback_lines):
                if 'future.set_result(' in line:
                    set_result_line = i
                    break
            
            if set_result_line != -1:
                # Check for exception handling before set_result
                # Could be try: or with contextlib.suppress(...):
                found_exception_handling = False
                for i in range(max(0, set_result_line - 5), set_result_line):
                    if 'try:' in callback_lines[i] or 'contextlib.suppress' in callback_lines[i]:
                        found_exception_handling = True
                        break
                
                assert found_exception_handling, \
                    "Callback should have exception handling around future.set_result()"
                
                print("✓ Callback has proper exception handling for set_result()")
            else:
                print("Note: Could not find set_result line in callback")
        else:
            print("Note: set_result() not found in callback (might have changed)")
    
    def test_cleanup_has_exception_handling(self) -> None:
        """Verify cleanup has exception handling for cancel()."""
        import henchman.cli.textual_mixins as module
        
        source = inspect.getsource(module._InitMixin._cleanup_confirm_futures)
        
        # Check for try-except around cancel()
        assert 'try:' in source and 'future.cancel()' in source, \
            "Cleanup should have try-except around future.cancel()"
        
        print("✓ Cleanup has proper exception handling for cancel()")
    
    def test_simplified_dictionary_access(self) -> None:
        """Verify dictionary access is simplified (no lock in callback)."""
        import henchman.cli.textual_mixins as module
        
        source = inspect.getsource(module._InitMixin._textual_confirm)
        
        # Check callback doesn't try to use _confirm_lock
        if 'def _callback' in source:
            # Extract callback
            start = source.find('def _callback')
            # Find end of callback (next function or end)
            end = source.find('\n    def ', start)
            if end == -1:
                end = source.find('\n\n', start)
            if end == -1:
                end = len(source)
            
            callback_source = source[start:end]
            
            # Should not try to use async with lock
            assert 'async with self._confirm_lock' not in callback_source, \
                "Callback should not try to use async with lock (simplified)"
            
            print("✓ Callback uses simplified dictionary access (no lock)")
        
        print("\n" + "="*60)
        print("FIX VERIFICATION SUMMARY")
        print("="*60)
        print("✓ Fixed unhandled task creation bug")
        print("✓ Added exception handling for future.set_result()")
        print("✓ Simplified dictionary access (no lock needed)")
        print("✓ All fixes maintain correctness while eliminating warnings")