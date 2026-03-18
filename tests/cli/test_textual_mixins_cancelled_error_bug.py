"""Test for asyncio.CancelledError bug in _textual_confirm method."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.cli.textual_mixins import _InitMixin
from henchman.tools.base import ConfirmationRequest


class TestCancelledErrorBug:
    """Test that demonstrates the asyncio.CancelledError handling bug."""

    @pytest.mark.anyio
    async def test_cancelled_error_not_propagated(self) -> None:
        """Test that asyncio.CancelledError is properly handled and re-raised.
        
        asyncio.CancelledError is a BaseException (not Exception), so it
        should be caught by the specific handler and re-raised.
        """
        # Create a mock mixin instance
        mixin = MagicMock(spec=_InitMixin)
        
        # Initialize the state that _textual_confirm expects
        mixin._confirm_futures = {}
        mixin._confirm_counter = 0
        mixin._confirm_lock = asyncio.Lock()
        mixin.push_screen = AsyncMock(side_effect=asyncio.CancelledError)
        
        # Get the actual method
        confirm_method = _InitMixin._textual_confirm
        
        # Create a simple confirmation request
        request = ConfirmationRequest(
            tool_name="test_tool",
            description="Test tool execution",
            params={"file": "test.txt"},
            risk_level="medium"
        )
        
        # asyncio.CancelledError should be caught by the specific handler
        # and re-raised after cleanup
        try:
            await confirm_method(mixin, request)
            pytest.fail("Should have raised asyncio.CancelledError")
        except asyncio.CancelledError:
            # This is what should happen - CancelledError is re-raised
            pass
        except Exception as e:
            pytest.fail(f"Wrong exception type: {type(e).__name__}: {e}")

    @pytest.mark.anyio
    async def test_exception_order_bug(self) -> None:
        """Test the exception handler order bug directly."""
        # Read the source code to verify the bug
        import inspect
        from henchman.cli.textual_mixins import _InitMixin
        
        source = inspect.getsource(_InitMixin._textual_confirm)
        lines = source.split('\n')
        
        # Find the exception handlers
        cancelled_handler_found = False
        generic_handler_found = False
        cancelled_line = -1
        generic_line = -1
        
        for i, line in enumerate(lines):
            if 'except asyncio.CancelledError:' in line:
                cancelled_handler_found = True
                cancelled_line = i
            elif 'except Exception:' in line and 'asyncio.CancelledError' not in line:
                generic_handler_found = True
                generic_line = i
        
        print(f"CancelledError handler found: {cancelled_handler_found} at line {cancelled_line}")
        print(f"Exception handler found: {generic_handler_found} at line {generic_line}")
        
        # The bug: if generic Exception handler comes AFTER CancelledError handler,
        # it doesn't matter because exception matching is first-match
        # But if CancelledError handler comes first, it should catch CancelledError
        # UNLESS the generic handler is a bare `except:` which comes first
        
        # Actually, looking at the code structure:
        # try:
        #     ...
        # except asyncio.CancelledError:
        #     ...
        # except Exception:
        #     ...
        
        # This is CORRECT! asyncio.CancelledError is caught first.
        # So maybe there's no bug here?
        
        # Both handlers should be present
        assert cancelled_handler_found, "asyncio.CancelledError handler not found"
        assert generic_handler_found, "Exception handler not found"
        
        # Check that CancelledError handler comes before Exception handler
        # (though Exception won't catch CancelledError since it's a BaseException)
        if cancelled_line != -1 and generic_line != -1:
            assert cancelled_line < generic_line, (
                "asyncio.CancelledError handler should come before Exception handler"
            )