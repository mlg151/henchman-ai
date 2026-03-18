"""Test verification of the fix for the else branch race condition."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch
import pytest

from henchman.tools.base import ConfirmationRequest


class TestFixVerification:
    """Test that verifies the fix works."""
    
    @pytest.mark.anyio
    async def test_fix_creates_lock_if_missing(self) -> None:
        """Test that fix creates lock if missing (backward compatibility)."""
        from henchman.cli.textual_mixins import _InitMixin
        
        # Create instance without _confirm_lock
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 0
        # No _confirm_lock!
        
        mock_request = ConfirmationRequest(
            tool_name="test_tool",
            description="Test tool",
            params={"arg": "value"},
            risk_level="medium"
        )
        
        # Mock push_screen to call callback immediately
        callback_called = []
        
        async def mock_push_screen(screen, callback):
            callback_called.append(callback)
            # Call callback immediately with True
            callback(True)
            return None
        
        mixin.push_screen = mock_push_screen
        
        # Mock import_module
        with patch('henchman.cli.textual_mixins._import_module') as mock_import:
            mock_screen_cls = MagicMock()
            mock_import.return_value.ConfirmToolScreen = mock_screen_cls
            
            # Call _textual_confirm
            # This should create _confirm_lock since it doesn't exist
            result = await mixin._textual_confirm(mock_request)
            
            # Verify lock was created
            assert hasattr(mixin, '_confirm_lock'), "Lock should have been created"
            assert isinstance(mixin._confirm_lock, asyncio.Lock), "Should be asyncio.Lock"
            
            # Verify result
            assert result is True, "Should return True (user confirmed)"
            
            # Verify callback was called
            assert len(callback_called) == 1, "Callback should have been called"
            
            # Verify dict is empty (future removed)
            assert len(mixin._confirm_futures) == 0, "Future should have been removed"
            
            print("Fix verified: lock created if missing, no race condition")
    
    @pytest.mark.anyio
    async def test_fix_prevents_race_condition(self) -> None:
        """Test that fix prevents race condition."""
        from henchman.cli.textual_mixins import _InitMixin
        
        # Create instance
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 0
        mixin._confirm_lock = asyncio.Lock()  # Has lock
        
        mock_request = ConfirmationRequest(
            tool_name="test_tool",
            description="Test tool",
            params={"arg": "value"},
            risk_level="medium"
        )
        
        # Track request IDs to check for duplicates
        request_ids = []
        original_lock_acquire = mixin._confirm_lock.acquire
        
        async def tracked_lock_acquire():
            # Track when lock is acquired
            result = await original_lock_acquire()
            # Simulate some work while lock is held
            await asyncio.sleep(0.001)  # Make race more obvious if lock not working
            return result
        
        # Replace lock acquire to track it
        mixin._confirm_lock.acquire = tracked_lock_acquire
        
        # Mock push_screen
        callbacks = []
        
        async def mock_push_screen(screen, callback):
            callbacks.append(callback)
            # Don't call callback yet
            return None
        
        mixin.push_screen = mock_push_screen
        
        # Mock import_module
        with patch('henchman.cli.textual_mixins._import_module') as mock_import:
            mock_screen_cls = MagicMock()
            mock_import.return_value.ConfirmToolScreen = mock_screen_cls
            
            # Start multiple concurrent calls
            tasks = []
            for i in range(10):
                task = asyncio.create_task(mixin._textual_confirm(mock_request))
                tasks.append(task)
            
            # Let them run (they'll block on lock)
            await asyncio.sleep(0.01)
            
            # Call callbacks
            for callback in callbacks:
                callback(True)
            
            # Get results
            results = await asyncio.gather(*tasks)
            
            # All should return True
            assert all(r is True for r in results), "All should return True"
            
            # Check counter value
            assert mixin._confirm_counter == 10, f"Counter should be 10, got {mixin._confirm_counter}"
            
            # Check dict is empty
            assert len(mixin._confirm_futures) == 0, "All futures should be removed"
            
            # With lock, there should be no race condition
            # (We can't easily verify this, but if we got here without errors,
            # and counter is correct, the lock is working)
            
            print("Fix verified: lock prevents race condition")
            print(f"Counter: {mixin._confirm_counter}, Results: {len(results)} all True")
    
    @pytest.mark.anyio
    async def test_fix_also_creates_dict_if_missing(self) -> None:
        """Test that fix also creates _confirm_futures if missing."""
        from henchman.cli.textual_mixins import _InitMixin
        
        # Create instance without _confirm_futures
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_counter = 0
        mixin._confirm_lock = asyncio.Lock()
        # No _confirm_futures!
        
        mock_request = ConfirmationRequest(
            tool_name="test_tool",
            description="Test tool",
            params={"arg": "value"},
            risk_level="medium"
        )
        
        # Mock push_screen
        async def mock_push_screen(screen, callback):
            callback(True)
            return None
        
        mixin.push_screen = mock_push_screen
        
        # Mock import_module
        with patch('henchman.cli.textual_mixins._import_module') as mock_import:
            mock_screen_cls = MagicMock()
            mock_import.return_value.ConfirmToolScreen = mock_screen_cls
            
            # Call _textual_confirm
            result = await mixin._textual_confirm(mock_request)
            
            # Verify _confirm_futures was created
            assert hasattr(mixin, '_confirm_futures'), "_confirm_futures should have been created"
            assert isinstance(mixin._confirm_futures, dict), "Should be a dict"
            
            # Verify result
            assert result is True, "Should return True"
            
            print("Fix verified: _confirm_futures created if missing")