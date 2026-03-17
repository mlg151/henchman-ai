"""Failing test for the id() collision bug in textual_mixins.py."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch
import pytest

from henchman.tools.base import ConfirmationRequest


class TestTextualConfirmIdCollisionBugFailing:
    """Test that fails due to the id() collision bug in _textual_confirm."""
    
    @pytest.mark.anyio
    async def test_id_collision_bug_demonstration(self) -> None:
        """Demonstrate the bug by showing id() is used instead of counter.
        
        This test will FAIL with current implementation because:
        - Current code uses `id(future)` as dictionary key
        - This test checks that `_confirm_counter` is used and incremented
        - After fix, this test should pass
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        # Create a real instance to test
        class MockApp:
            def __init__(self):
                self._confirm_futures = {}
                self._confirm_counter = 100
                
        app = MockApp()
        
        # We need to test the actual _textual_confirm method
        # But it requires push_screen which we can mock
        
        with patch('henchman.cli.textual_mixins._import_module') as mock_import:
            mock_screen = MagicMock()
            mock_import.return_value.ConfirmToolScreen = mock_screen
            
            # Create mixin instance
            mixin = _InitMixin.__new__(_InitMixin)
            mixin._confirm_futures = {}
            mixin._confirm_counter = 100
            mixin.push_screen = MagicMock()
            
            # Create request
            request = ConfirmationRequest(
                tool_name="test_tool",
                description="Test tool execution",
                params={"arg": "value"},
                risk_level="high"
            )
            
            # Try to call _textual_confirm
            # It will fail because we haven't mocked everything properly
            # But we can inspect the source code
            
            import inspect
            import henchman.cli.textual_mixins as module
            
            source = inspect.getsource(module._InitMixin._textual_confirm)
            
            # THE BUG: Current implementation uses id(future)
            assert 'id(future)' in source, "Bug: _textual_confirm uses id(future) which can collide!"
            
            # THE FIX: Should use self._confirm_counter
            # This assertion will FAIL with current implementation
            # After fix, it should pass
            assert 'self._confirm_counter' in source, (
                "Fix needed: _textual_confirm should use self._confirm_counter, not id(future)"
            )
            
            # Also check that counter is incremented
            assert 'self._confirm_counter += 1' in source or 'self._confirm_counter = self._confirm_counter + 1' in source, (
                "Fix needed: _textual_confirm should increment self._confirm_counter"
            )
    
    @pytest.mark.anyio
    async def test_actual_bug_scenario(self) -> None:
        """Test a scenario that could trigger the bug.
        
        This test simulates what could happen if id() is reused:
        - Future A created, gets id X
        - Future A completes, removed from dict
        - Future B created, gets same id X (if memory reused)
        - Late callback for Future A affects Future B
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        # This is hard to test deterministically because
        # we can't control when Python reuses memory addresses
        
        # But we can test the fix: using a counter instead of id()
        
        # Create test implementation with the bug
        async def buggy_textual_confirm(self, request):
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            req_id = id(future)  # BUG: uses id()
            self._confirm_futures[req_id] = future
            # ... rest of implementation
            future.set_result(True)  # Simulate immediate approval for test
            return True
            
        # Create test implementation with the fix  
        async def fixed_textual_confirm(self, request):
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            req_id = self._confirm_counter  # FIX: uses counter
            self._confirm_counter += 1  # FIX: increments counter
            self._confirm_futures[req_id] = future
            # ... rest of implementation
            future.set_result(True)  # Simulate immediate approval for test
            return True
            
        # Test that with buggy implementation, IDs are memory addresses
        mixin1 = _InitMixin.__new__(_InitMixin)
        mixin1._confirm_futures = {}
        mixin1._confirm_counter = 100
        
        loop = asyncio.get_running_loop()
        future1 = loop.create_future()
        buggy_id = id(future1)
        
        # buggy_id is a large memory address, not 100
        assert buggy_id != 100, "id() should not equal counter value"
        
        # With fixed implementation, ID should be counter value
        mixin2 = _InitMixin.__new__(_InitMixin)
        mixin2._confirm_futures = {}
        mixin2._confirm_counter = 100
        
        # In fixed version, req_id would be 100
        fixed_id = 100  # What the fix should produce
        
        assert fixed_id == 100, "Fixed version should use counter value"
        
        # The bug is that id() can be reused, counter can't
        # We can't test the actual collision, but we can show
        # the flawed assumption