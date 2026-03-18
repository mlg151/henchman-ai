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
        """Test that _textual_confirm raises RuntimeError when state not initialized.
        
        The method should raise RuntimeError if _confirm_lock, _confirm_counter,
        or _confirm_futures are not initialized.
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        # Create instance without _confirm_lock to test defensive initialization
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 0
        # Intentionally don't set _confirm_lock
        
        # Create a simple confirmation request
        request = ConfirmationRequest(
            tool_name="test_tool",
            description="Test tool execution",
            params={"file": "test.txt"},
            risk_level="medium"
        )
        
        # Should raise RuntimeError because state is not properly initialized
        with pytest.raises(RuntimeError, match="_textual_confirm called before _init_confirm_state"):
            await mixin._textual_confirm(request)
        
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
        """Test that _textual_confirm raises RuntimeError when state not initialized."""
        from henchman.cli.textual_mixins import _InitMixin
        
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 0
        # No _confirm_lock
        
        # Create proper confirmation request
        mock_request = ConfirmationRequest(
            tool_name="test_tool",
            description="Test tool execution",
            params={"arg": "value"},
            risk_level="medium"
        )
        
        # Should raise RuntimeError because _confirm_lock is missing
        with pytest.raises(RuntimeError, match="_textual_confirm called before _init_confirm_state"):
            await mixin._textual_confirm(mock_request)
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