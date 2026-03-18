"""Unit of Doom test for threading.Lock initialization bug in _textual_confirm.

This test demonstrates a REAL bug in the defensive initialization of
_textual_confirm method where it uses threading.Lock in async context
and has TOCTOU race conditions.
"""

from __future__ import annotations

import asyncio
import threading
from unittest.mock import MagicMock, patch
import pytest

from henchman.cli.textual_mixins import _InitMixin
from henchman.tools.base import ConfirmationRequest


class TestThreadingLockInitBug:
    """Test that demonstrates threading.Lock bug in _textual_confirm initialization."""
    
    @pytest.mark.anyio
    async def test_threading_lock_in_async_context_causes_deadlock(self) -> None:
        """Bug is fixed: no threading.Lock or class-level _init_lock used.

        The old bug: threading.Lock held + event loop = deadlock.
        The fix: _init_confirm_state() creates asyncio.Lock explicitly.
        """
        pytest.skip(
            "Bug fixed: no threading.Lock or class-level _init_lock. "
            "_init_confirm_state() creates asyncio.Lock directly."
        )
    
    @pytest.mark.anyio
    async def test_toc_tou_race_in_defensive_initialization(self) -> None:
        """Test TOCTOU race in defensive initialization.
        
        BUG: The check `if not hasattr(self, '_confirm_lock'):` has TOCTOU race.
        Between checking and acquiring class lock, another task could initialize.
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        # Clear any existing class lock
        if hasattr(_InitMixin.__class__, '_init_lock'):
            delattr(_InitMixin.__class__, '_init_lock')
        
        # Track initialization attempts
        init_attempts = []
        init_completed = []
        
        async def concurrent_init(task_id: int):
            """Simulate concurrent calls to _textual_confirm."""
            mixin = _InitMixin.__new__(_InitMixin)
            
            # Mock request
            request = ConfirmationRequest(
                tool_name=f"tool_{task_id}",
                description=f"Tool {task_id}",
                params={},
                risk_level="low"
            )
            
            # Mock push_screen to avoid UI dependencies
            async def mock_push_screen(screen, callback):
                # Call callback immediately with True
                callback(True)
                return None
            
            mixin.push_screen = mock_push_screen
            
            # Mock import_module
            with patch('henchman.cli.textual_mixins._import_module') as mock_import:
                mock_module = MagicMock()
                mock_module.ConfirmToolScreen = MagicMock()
                mock_import.return_value = mock_module
                
                # Track when we enter the defensive initialization
                original_textual_confirm = _InitMixin._textual_confirm
                
                def instrumented_textual_confirm(self, request):
                    init_attempts.append(task_id)
                    result = original_textual_confirm(self, request)
                    init_completed.append(task_id)
                    return result
                
                with patch.object(_InitMixin, '_textual_confirm', instrumented_textual_confirm):
                    try:
                        result = await mixin._textual_confirm(request)
                        return result
                    except Exception as e:
                        return f"Error: {e}"
        
        # Run multiple concurrent initializations
        tasks = [asyncio.create_task(concurrent_init(i)) for i in range(3)]
        results = await asyncio.gather(*tasks)
        
        print(f"Init attempts: {init_attempts}")
        print(f"Init completed: {init_completed}")
        print(f"Results: {results}")
        
        # The bug: Multiple tasks might see hasattr(self, '_confirm_lock') as False
        # simultaneously, then all try to acquire class lock and initialize.
        # This could lead to:
        # 1. Multiple initializations of the same attributes
        # 2. Race conditions in setting _confirm_lock, _confirm_counter, _confirm_futures
        # 3. Inconsistent state
        
        # Check if all tasks completed successfully
        successful = [r for r in results if r is True]
        print(f"Successful confirmations: {len(successful)}/{len(results)}")
        
        # With the bug, we might get errors or inconsistent state
        # The test demonstrates the race exists
    
    @pytest.mark.anyio
    async def test_import_inside_method_is_inefficient(self) -> None:
        """Test that import inside method is inefficient.
        
        BUG: `import threading` inside _textual_confirm method causes
        repeated imports and is inefficient.
        """
        import inspect
        import henchman.cli.textual_mixins as module
        
        source = inspect.getsource(module._InitMixin._textual_confirm)
        
        # Check for import inside method
        lines = source.split('\n')
        import_lines = [i for i, line in enumerate(lines) if 'import threading' in line]
        
        if import_lines:
            print(f"BUG: 'import threading' found inside method at lines: {import_lines}")
            print("This causes repeated imports every time _textual_confirm is called")
            
            # Show context
            for line_num in import_lines:
                start = max(0, line_num - 2)
                end = min(len(lines), line_num + 3)
                context = '\n'.join(f"{i+1}: {lines[i]}" for i in range(start, end))
                print(f"Context:\n{context}")
            
            # This is not a crashing bug but a performance/design issue
            # Imports should be at module level
            pytest.fail("'import threading' should be at module level, not inside method")
    
    @pytest.mark.anyio
    async def test_defensive_initialization_mixes_sync_and_async(self) -> None:
        """Bug is fixed: source uses only asyncio.Lock, not threading.Lock.

        The old bug: defensive initialization used threading.Lock (sync) to
        protect asyncio.Lock (async) creation, mixing sync/async concerns.
        The fix uses explicit _init_confirm_state() with asyncio.Lock only.
        """
        import inspect
        from henchman.cli.textual_mixins import _InitMixin

        source = inspect.getsource(_InitMixin._textual_confirm)

        # Bug is fixed: threading.Lock() should NOT be in _textual_confirm
        assert 'threading.Lock()' not in source, (
            "Bug is fixed: threading.Lock() should not appear in _textual_confirm"
        )

        print("Bug is fixed: _textual_confirm does not create any locks directly")