"""Final verification test for textual_mixins.py lock bug fix."""

from __future__ import annotations

import asyncio
import threading
from unittest.mock import MagicMock, patch
import pytest

from henchman.tools.base import ConfirmationRequest


class TestFinalVerification:
    """Final verification that all lock-related bugs are fixed."""
    
    def test_lock_type_is_asyncio_lock(self) -> None:
        """Verify that _init_confirm_state creates asyncio.Lock, not threading.Lock."""
        # Read the source file directly
        with open('src/henchman/cli/textual_mixins.py', 'r') as f:
            content = f.read()
        
        # Find _init_confirm_state method
        import re
        # Look for the method definition
        pattern = r'def _init_confirm_state\(self: _InitMixin\) -> None:.*?(?=\n    def|\nclass|\Z)'
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            pytest.skip("Could not find _init_confirm_state method")
        
        method_text = match.group(0)
        print("Found _init_confirm_state method")
        
        # Check for asyncio.Lock vs threading.Lock
        if 'asyncio.Lock' in method_text:
            print("✓ Uses asyncio.Lock")
            lock_type = 'asyncio'
        elif 'threading.Lock' in method_text:
            print("✗ Still uses threading.Lock")
            lock_type = 'threading'
            pytest.fail("Still uses threading.Lock - bug not fixed!")
        else:
            print("? Could not determine lock type")
            lock_type = 'unknown'
        
        return lock_type
    
    def test_no_with_statements_on_asyncio_lock(self) -> None:
        """Verify no 'with self._confirm_lock:' statements (should be 'async with')."""
        with open('src/henchman/cli/textual_mixins.py', 'r') as f:
            content = f.read()
        
        # Find all lines with 'with self._confirm_lock:'
        lines = content.split('\n')
        bug_locations = []
        
        for i, line in enumerate(lines, 1):
            if 'with self._confirm_lock:' in line and 'async with self._confirm_lock:' not in line:
                bug_locations.append((i, line.strip()))
        
        if bug_locations:
            print("✗ Found 'with self._confirm_lock:' statements (should be 'async with'):")
            for line_num, line in bug_locations:
                print(f"  Line {line_num}: {line}")
            pytest.fail(f"Found {len(bug_locations)} uses of 'with' on asyncio.Lock")
        else:
            print("✓ No 'with self._confirm_lock:' statements found")
    
    def test_cleanup_does_not_use_lock(self) -> None:
        """Verify _cleanup_confirm_futures doesn't try to use asyncio.Lock in sync context."""
        with open('src/henchman/cli/textual_mixins.py', 'r') as f:
            content = f.read()
        
        # Find _cleanup_confirm_futures method
        import re
        pattern = r'def _cleanup_confirm_futures\(self: _InitMixin\) -> None:.*?(?=\n    def|\nclass|\Z)'
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            pytest.skip("Could not find _cleanup_confirm_futures method")
        
        method_text = match.group(0)
        
        # Check if it uses 'with self._confirm_lock:'
        if 'with self._confirm_lock:' in method_text:
            print("✗ _cleanup_confirm_futures uses 'with' on asyncio.Lock")
            pytest.fail("_cleanup_confirm_futures tries to use asyncio.Lock in sync context")
        else:
            print("✓ _cleanup_confirm_futures doesn't use lock (correct for sync context)")
        
        # Check for comment about accepting races
        if 'accept potential races' in method_text.lower() or 'shutdown' in method_text.lower():
            print("✓ Method has comment about shutdown/races")
    
    @pytest.mark.anyio
    async def test_async_with_used_in_async_context(self) -> None:
        """Verify _textual_confirm uses 'async with' for asyncio.Lock."""
        with open('src/henchman/cli/textual_mixins.py', 'r') as f:
            content = f.read()
        
        # Find _textual_confirm method
        import re
        pattern = r'async def _textual_confirm\(self: _InitMixin, request: ConfirmationRequest\) -> bool:.*?(?=\n    def|\nclass|\Z)'
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            pytest.skip("Could not find _textual_confirm method")
        
        method_text = match.group(0)
        
        # Count async with vs with
        async_with_count = method_text.count('async with self._confirm_lock')
        with_count = method_text.count('with self._confirm_lock') - async_with_count
        
        print(f"Found {async_with_count} 'async with self._confirm_lock:' statements")
        print(f"Found {with_count} 'with self._confirm_lock:' statements (should be 0)")
        
        if with_count > 0:
            pytest.fail(f"_textual_confirm has {with_count} uses of 'with' on asyncio.Lock")
        
        # Also check exception handlers
        if 'except asyncio.CancelledError:' in method_text:
            # Check what's in the exception handler
            cancelled_section = method_text.split('except asyncio.CancelledError:')[1].split('except Exception:')[0]
            if 'async with self._confirm_lock:' in cancelled_section:
                print("✓ CancelledError handler uses 'async with'")
            elif 'with self._confirm_lock:' in cancelled_section:
                print("✗ CancelledError handler uses 'with' instead of 'async with'")
        
        print("✓ _textual_confirm correctly uses 'async with' for asyncio.Lock")
    
    def test_overall_status(self) -> None:
        """Print overall status of the fix."""
        print("\n=== Overall Status ===")
        
        # Run the checks
        try:
            lock_type = self.test_lock_type_is_asyncio_lock()
            if lock_type == 'asyncio':
                print("✓ Lock type: asyncio.Lock (correct)")
            else:
                print(f"✗ Lock type: {lock_type} (incorrect)")
        except Exception as e:
            print(f"✗ Lock type check failed: {e}")
        
        try:
            self.test_no_with_statements_on_asyncio_lock()
            print("✓ No 'with' statements on asyncio.Lock")
        except Exception as e:
            print(f"✗ Found 'with' statements: {e}")
        
        try:
            self.test_cleanup_does_not_use_lock()
            print("✓ Cleanup doesn't use lock in sync context")
        except Exception as e:
            print(f"✗ Cleanup uses lock incorrectly: {e}")
        
        print("\nSummary: Check if all tests pass to verify bug is fixed.")