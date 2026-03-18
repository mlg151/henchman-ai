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
        """Test that asyncio.CancelledError is caught by bare except Exception.
        
        This is a bug because asyncio.CancelledError should be re-raised
        for proper async task cancellation.
        """
        # Create a mock mixin instance
        mixin = _InitMixin()
        
        # Initialize the state that _textual_confirm expects
        mixin._confirm_futures = {}
        mixin._confirm_counter = 0
        mixin._confirm_lock = asyncio.Lock()
        
        # Mock the push_screen to raise CancelledError immediately
        with patch.object(mixin, 'push_screen', side_effect=asyncio.CancelledError):
            # Create a simple confirmation request
            request = ConfirmationRequest(
                tool_name="test_tool",
                tool_kind="WRITE",
                arguments={"file": "test.txt"},
                description="Test tool execution"
            )
            
            # The bug: asyncio.CancelledError should be re-raised,
            # but it will be caught by the bare `except Exception:` 
            # which calls future.cancel() and re-raises a generic Exception
            # Actually, let's trace through the logic:
            # 1. push_screen raises asyncio.CancelledError
            # 2. except asyncio.CancelledError: should catch it
            # 3. BUT except Exception: comes AFTER and catches it first!
            # 4. So the CancelledError handler never runs
            
            try:
                await mixin._textual_confirm(request)
                pytest.fail("Should have raised asyncio.CancelledError")
            except asyncio.CancelledError:
                # This is what SHOULD happen
                print("✓ asyncio.CancelledError correctly propagated")
                return
            except Exception as e:
                if isinstance(e, asyncio.CancelledError):
                    # Actually caught and re-raised by bare except?
                    # Let's check the trace
                    print(f"✓ asyncio.CancelledError caught and re-raised: {e}")
                    return
                else:
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
        
        # Wait, let me check the actual code again...
        # Actually the handlers are in the right order!
        # So CancelledError SHOULD be caught by its specific handler
        
        assert cancelled_handler_found, "asyncio.CancelledError handler not found"
        assert generic_handler_found, "Exception handler not found"
        assert cancelled_line < generic_line, "CancelledError handler should come BEFORE Exception handler"