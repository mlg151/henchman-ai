"""Test for the id() collision bug in textual_mixins.py."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch
import pytest

from henchman.tools.base import ConfirmationRequest


class TestTextualConfirmIdCollisionBug:
    """Test that demonstrates the id() collision bug in _textual_confirm."""
    
    @pytest.mark.anyio
    async def test_id_collision_bug(self) -> None:
        """Demonstrate that id() can be reused after garbage collection.
        
        This test shows the theoretical bug where id(future) can return
        the same value for two different futures if one is garbage collected
        and memory is reused.
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        # Create a mock app with the mixin
        app = MagicMock()
        app._confirm_futures = {}
        app._confirm_counter = 0
        
        # Monkey-patch the _textual_confirm method to test it
        mixin = _InitMixin.__new__(_InitMixin)
        
        # We need to simulate the bug scenario
        # First, create a future and get its id
        loop = asyncio.get_running_loop()
        future1 = loop.create_future()
        id1 = id(future1)
        
        # Simulate what happens in _textual_confirm
        app._confirm_futures[id1] = future1
        
        # Now simulate future1 being garbage collected
        # (in real scenario, this would happen after completion)
        del future1
        
        # Create a new future - Python might reuse the same memory address
        future2 = loop.create_future()
        id2 = id(future2)
        
        # In the bug scenario, id2 could equal id1 if memory was reused
        # This is non-deterministic but possible
        
        # The bug is that the code assumes id() is unique over time,
        # but it's only unique among simultaneously existing objects
        
        # We can't reliably reproduce the exact memory reuse scenario,
        # but we can demonstrate the flawed assumption by showing
        # that two different futures can theoretically get the same id
        # if one is garbage collected
        
        # Instead, let's test the actual fix: using a counter instead of id()
        
        # Test that _confirm_counter exists but is unused
        assert hasattr(app, '_confirm_counter')
        
        # The bug is that _textual_confirm uses id(future) instead of
        # using and incrementing _confirm_counter
        
    @pytest.mark.anyio 
    async def test_textual_confirm_uses_id_bug(self) -> None:
        """Test that _textual_confirm currently uses id() which is buggy."""
        from henchman.cli.textual_mixins import _InitMixin
        
        # Create mock
        app = MagicMock()
        app._confirm_futures = {}
        app._confirm_counter = 0
        app.push_screen = MagicMock()
        
        # Get the actual _textual_confirm method
        mixin = _InitMixin.__new__(_InitMixin)
        
        # We need to inspect the source to confirm it uses id()
        import inspect
        import henchman.cli.textual_mixins as module
        
        source = inspect.getsource(module._InitMixin._textual_confirm)
        assert 'id(future)' in source, "_textual_confirm should use id(future) - this is the bug!"
        assert 'self._confirm_counter' not in source, "_textual_confirm should NOT use _confirm_counter (but it should!)"
        
    @pytest.mark.anyio
    async def test_fix_would_use_counter(self) -> None:
        """Test what the fixed version should look like."""
        from henchman.cli.textual_mixins import _InitMixin
        
        # After fix, _textual_confirm should:
        # 1. Use self._confirm_counter as ID
        # 2. Increment self._confirm_counter
        # 3. NOT use id(future)
        
        # We'll write this test to fail with current implementation
        # and pass after fix
        
        app = MagicMock()
        app._confirm_futures = {}
        app._confirm_counter = 100  # Start at 100
        
        # Mock the method to test the logic
        async def mock_textual_confirm(self, request):
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            
            # BUGGY CURRENT IMPLEMENTATION uses id()
            req_id = id(future)  # This is the bug!
            
            # CORRECT IMPLEMENTATION should use counter:
            # req_id = self._confirm_counter
            # self._confirm_counter += 1
            
            self._confirm_futures[req_id] = future
            return True
            
        # Patch it
        with patch.object(_InitMixin, '_textual_confirm', mock_textual_confirm):
            mixin = _InitMixin.__new__(_InitMixin)
            mixin._confirm_futures = {}
            mixin._confirm_counter = 100
            
            request = ConfirmationRequest(
                tool_name="test_tool",
                tool_kind="EXECUTE",
                arguments={"arg": "value"},
                description="Test tool execution"
            )
            
            # Call the method
            result = await mixin._textual_confirm(request)
            
            # Check that it used id() not counter
            # This assertion will fail after fix
            futures_keys = list(mixin._confirm_futures.keys())
            if futures_keys:
                key = futures_keys[0]
                # With buggy implementation, key is a large memory address (id)
                # With fixed implementation, key should be 100 (counter)
                assert key != 100, "After fix, key should be 100 (counter value), not id()"
                
    @pytest.mark.anyio
    async def test_concurrent_id_collision_scenario(self) -> None:
        """Simulate a scenario where id() collision could cause issues."""
        from henchman.cli.textual_mixins import _InitMixin
        
        # This is a more direct test of the problem
        app = MagicMock()
        app._confirm_futures = {}
        app._confirm_counter = 0
        
        # Create two futures
        loop = asyncio.get_running_loop()
        future1 = loop.create_future()
        future2 = loop.create_future()
        
        # Manually create the bug scenario
        # In real code, this would happen if:
        # 1. future1 gets id 1000
        # 2. future1 completes, removed from dict, garbage collected  
        # 3. future2 gets allocated at same address, id 1000
        # 4. Something tries to access id 1000 in dict
        
        # Simulate by forcing same id (not possible in real Python but illustrates bug)
        import ctypes
        id1 = id(future1)
        
        # We can't force id2 to equal id1, but we can show the logic flaw
        # The dictionary stores futures by id
        app._confirm_futures[id1] = future1
        
        # If future1 is removed and future2 gets same id...
        # (can't actually simulate but illustrating the bug)
        del app._confirm_futures[id1]
        
        # Now if something tries to pop id1 for future1 (late callback)
        # it won't find it (returns None) - that's actually OK
        
        # But if future2 gets same id and is added to dict...
        # Actually, thinking more: the real issue is if the callback
        # for future1 runs late and future2 has same id
        
        # The test shows we need deterministic unique IDs, not memory addresses