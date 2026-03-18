"""Test for the else branch bug in _textual_confirm.

This test demonstrates that the else branch in _textual_confirm
has a race condition when _confirm_lock doesn't exist.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch
import pytest

from henchman.tools.base import ConfirmationRequest


class TestElseBranchBug:
    """Test that demonstrates the else branch race condition bug."""
    
    @pytest.mark.anyio
    async def test_else_branch_race_condition(self) -> None:
        """Demonstrate race condition in else branch.
        
        BUG: When _confirm_lock doesn't exist (else branch),
        concurrent calls to _textual_confirm can race on:
        1. _confirm_counter increment (not atomic)
        2. _confirm_futures dictionary insertion
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        # Create instance without _confirm_lock to trigger else branch
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 0
        # Intentionally don't set _confirm_lock
        
        # Track operations to detect races
        operations = []
        operation_lock = asyncio.Lock()
        
        async def simulate_textual_confirm(task_id: int):
            """Simulate the else branch logic."""
            # This mimics the else branch in _textual_confirm
            req_id = mixin._confirm_counter
            async with operation_lock:
                operations.append(f"task{task_id}_read_{req_id}")
            
            # NOT ATOMIC: read, increment, write
            # Between read and write, another task can read same value
            mixin._confirm_counter += 1
            
            async with operation_lock:
                operations.append(f"task{task_id}_incremented")
            
            future = asyncio.Future()
            mixin._confirm_futures[req_id] = future
            
            async with operation_lock:
                operations.append(f"task{task_id}_stored_{req_id}")
            
            return req_id
        
        # Run multiple concurrent tasks
        tasks = [asyncio.create_task(simulate_textual_confirm(i)) for i in range(5)]
        results = await asyncio.gather(*tasks)
        
        print(f"Operations: {operations}")
        print(f"Results (req_ids): {results}")
        print(f"Final counter: {mixin._confirm_counter}")
        print(f"Dict keys: {list(mixin._confirm_futures.keys())}")
        
        # Check for duplicates (race condition symptom)
        if len(set(results)) < len(results):
            print(f"BUG: Duplicate request IDs due to race: {results}")
            # This is the bug!
            assert False, f"Duplicate request IDs: {results}"
        
        # Check counter value
        if mixin._confirm_counter != 5:
            print(f"BUG: Counter should be 5 but is {mixin._confirm_counter}")
            # Might happen if increments were lost
        
        # Check dict size
        if len(mixin._confirm_futures) != 5:
            print(f"BUG: Dict should have 5 entries but has {len(mixin._confirm_futures)}")
            # Might happen if entries were overwritten
    
    @pytest.mark.anyio
    async def test_with_lock_protects_against_race(self) -> None:
        """Show that with lock (normal case), there's no race."""
        from henchman.cli.textual_mixins import _InitMixin
        
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 0
        mixin._confirm_lock = asyncio.Lock()  # Has lock
        
        operations = []
        
        async def simulate_textual_confirm_with_lock(task_id: int):
            """Simulate with lock (normal case)."""
            async with mixin._confirm_lock:
                req_id = mixin._confirm_counter
                operations.append(f"task{task_id}_read_{req_id}")
                
                mixin._confirm_counter += 1
                operations.append(f"task{task_id}_incremented")
                
                future = asyncio.Future()
                mixin._confirm_futures[req_id] = future
                operations.append(f"task{task_id}_stored_{req_id}")
            
            return req_id
        
        tasks = [asyncio.create_task(simulate_textual_confirm_with_lock(i)) for i in range(5)]
        results = await asyncio.gather(*tasks)
        
        print(f"With lock - Operations: {operations}")
        print(f"With lock - Results: {results}")
        print(f"With lock - Final counter: {mixin._confirm_counter}")
        print(f"With lock - Dict keys: {list(mixin._confirm_futures.keys())}")
        
        # With lock, should be no duplicates
        assert len(set(results)) == len(results), f"Duplicate IDs even with lock: {results}"
        assert mixin._confirm_counter == 5, f"Counter should be 5 but is {mixin._confirm_counter}"
        assert len(mixin._confirm_futures) == 5, f"Dict should have 5 entries but has {len(mixin._confirm_futures)}"
    
    @pytest.mark.anyio
    async def test_actual_code_else_branch(self) -> None:
        """Test the actual _textual_confirm method's else branch."""
        from henchman.cli.textual_mixins import _InitMixin
        
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 0
        # No _confirm_lock
        
        # Mock dependencies
        mock_request = ConfirmationRequest(
            tool_name="test_tool",
            arguments={"arg": "value"},
            kind="WRITE"
        )
        
        # Mock push_screen to call callback immediately
        callback_called = []
        
        async def mock_push_screen(screen, callback):
            # Store callback to call later
            callback_called.append(callback)
            return None
        
        mixin.push_screen = mock_push_screen
        
        # Mock import_module
        with patch('henchman.cli.textual_mixins._import_module') as mock_import:
            mock_screen_cls = MagicMock()
            mock_import.return_value.ConfirmToolScreen = mock_screen_cls
            
            # Call _textual_confirm multiple times concurrently
            tasks = []
            for i in range(3):
                task = asyncio.create_task(mixin._textual_confirm(mock_request))
                tasks.append(task)
            
            # Let tasks run a bit
            await asyncio.sleep(0.01)
            
            # Call callbacks
            for callback in callback_called:
                callback(True)
            
            # Get results
            results = await asyncio.gather(*tasks)
            
            print(f"Actual code results: {results}")
            print(f"Counter: {mixin._confirm_counter}")
            print(f"Dict size: {len(mixin._confirm_futures)}")
            
            # Check for issues
            if len(set(results)) < len(results):
                print(f"BUG: Duplicate futures returned! {results}")
            
            # The dict should be empty after callbacks
            if mixin._confirm_futures:
                print(f"BUG: Futures not cleaned up: {mixin._confirm_futures.keys()}")
            
            # Note: This test might pass or fail depending on timing
            # Race conditions are non-deterministic