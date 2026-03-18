"""Simple Unit of Doom test for threading.Lock initialization bug in _textual_confirm.

This test demonstrates the REAL bug: threading.Lock in async context.
"""

from __future__ import annotations

import asyncio
import inspect
from unittest.mock import MagicMock, patch
import pytest

from henchman.cli.textual_mixins import _InitMixin
from henchman.tools.base import ConfirmationRequest


class TestThreadingLockInitBugSimple:
    """Simple test that demonstrates threading.Lock bug."""
    
    @pytest.mark.anyio
    async def test_threading_lock_present_in_async_method(self) -> None:
        """Test that _textual_confirm uses threading.Lock in async method.
        
        BUG: The method uses threading.Lock() for synchronization in an
        async context. This is wrong and can cause deadlocks.
        """
        import henchman.cli.textual_mixins as module
        
        # Get source code of _textual_confirm
        source = inspect.getsource(module._InitMixin._textual_confirm)
        
        # Check for threading.Lock
        if 'threading.Lock()' in source:
            print("BUG FOUND: _textual_confirm uses threading.Lock() in async method")
            print("This can cause deadlocks because threading.Lock blocks event loop")
            
            # Show the problematic lines
            lines = source.split('\n')
            for i, line in enumerate(lines):
                if 'threading.Lock()' in line:
                    print(f"Line {i+1}: {line}")
            
            # This test should FAIL with current implementation
            # because threading.Lock should not be used in async methods
            pytest.fail("threading.Lock() should not be used in async method _textual_confirm")
        else:
            print("GOOD: threading.Lock() not found in _textual_confirm")
            # Test passes if bug is fixed
    
    @pytest.mark.anyio
    async def test_hasattr_toc_tou_race(self) -> None:
        """Test that hasattr check has TOCTOU race.
        
        BUG: `if not hasattr(self, '_confirm_lock'):` has TOCTOU race.
        Between check and class lock acquisition, another task could initialize.
        """
        import henchman.cli.textual_mixins as module
        
        source = inspect.getsource(module._InitMixin._textual_confirm)
        
        # Look for the problematic pattern
        lines = source.split('\n')
        for i, line in enumerate(lines):
            if 'if not hasattr(self, \'_confirm_lock\')' in line:
                print(f"BUG FOUND: TOCTOU race at line {i+1}: {line}")
                print("Between hasattr check and class lock acquisition, another")
                print("task could initialize attributes, causing race condition.")
                
                # Show context
                start = max(0, i - 3)
                end = min(len(lines), i + 10)
                for j in range(start, end):
                    print(f"{j+1}: {lines[j]}")
                
                # This test should FAIL with current implementation
                pytest.fail("hasattr check has TOCTOU race in _textual_confirm")
        
        print("GOOD: No hasattr TOCTOU race found")
        # Test passes if bug is fixed
    
    @pytest.mark.anyio
    async def test_import_inside_method(self) -> None:
        """Test that import is inside method.
        
        BUG: `import threading` is inside the method, causing repeated imports.
        """
        import henchman.cli.textual_mixins as module
        
        source = inspect.getsource(module._InitMixin._textual_confirm)
        
        # Check for import inside method
        lines = source.split('\n')
        for i, line in enumerate(lines):
            if 'import threading' in line and not line.strip().startswith('#'):
                print(f"BUG FOUND: import threading inside method at line {i+1}: {line}")
                print("Imports should be at module level for efficiency.")
                
                # This is a code smell, not a crashing bug
                # But we'll fail the test to track the issue
                pytest.fail("import threading should be at module level")
        
        print("GOOD: No import threading inside method")
        # Test passes if bug is fixed
    
    @pytest.mark.anyio
    async def test_defensive_initialization_creates_asyncio_lock(self) -> None:
        """Test that defensive initialization creates asyncio.Lock.
        
        This is actually CORRECT - the method creates asyncio.Lock.
        But it uses threading.Lock to protect the creation, which is wrong.
        """
        import henchman.cli.textual_mixins as module
        
        source = inspect.getsource(module._InitMixin._textual_confirm)
        
        # Check for asyncio.Lock creation
        if 'asyncio.Lock()' in source:
            print("GOOD: Method creates asyncio.Lock (correct for async)")
        else:
            print("WARNING: Method doesn't create asyncio.Lock")
            # Not necessarily a bug, but unusual for async method
        
        # Check the overall pattern
        has_threading = 'threading.Lock()' in source
        has_asyncio = 'asyncio.Lock()' in source
        
        if has_threading and has_asyncio:
            print("PROBLEM: Method mixes threading.Lock and asyncio.Lock")
            print("This indicates sync-async mixing which is error-prone.")
            
            # Show both occurrences
            lines = source.split('\n')
            print("\nThreading lock usage:")
            for i, line in enumerate(lines):
                if 'threading.Lock()' in line:
                    print(f"  Line {i+1}: {line}")
            
            print("\nAsyncio lock usage:")
            for i, line in enumerate(lines):
                if 'asyncio.Lock()' in line:
                    print(f"  Line {i+1}: {line}")
            
            # This is the core bug: mixing sync and async primitives
            pytest.fail("Mixing threading.Lock and asyncio.Lock in async method")