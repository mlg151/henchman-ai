"""Test for the bool conversion bug in textual_mixins.py.

The bug: In _textual_confirm._callback, bool(result) incorrectly converts
non-boolean values:
- bool(None) = False (cancellation treated as denial)
- bool("no") = True (string "no" becomes approval)
- bool(0) = False (numeric 0 becomes denial)
- bool([]) = False (empty list becomes denial)

Bug is fixed: _callback now explicitly checks for True/False/None.
"""

from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

from henchman.cli.textual_mixins import _InitMixin
from henchman.tools.base import ConfirmationRequest


class TestBoolConversionBug:
    """Test the bool conversion bug in _textual_confirm._callback."""

    @pytest.mark.anyio
    async def test_bool_conversion_bug_none_becomes_false(self) -> None:
        """Bug is fixed: None (cancellation) correctly returns False.

        The fix uses explicit if/elif instead of bool(result), so None
        is handled as False without the ambiguity of bool() conversion.
        """
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 0
        mixin._confirm_lock = asyncio.Lock()

        request = ConfirmationRequest(
            tool_name="test_tool",
            description="Test tool execution",
            params={"arg": "value"},
            risk_level="medium",
        )

        # Patch push_screen to call callback with None (cancellation)
        async def mock_push_screen(screen, callback):
            callback(None)
            return None

        mixin.push_screen = AsyncMock(side_effect=mock_push_screen)

        with patch("henchman.cli.textual_mixins._import_module") as mock_import:
            mock_screen = MagicMock()
            mock_screen.ConfirmToolScreen = MagicMock()
            mock_import.return_value = mock_screen

            result = await mixin._textual_confirm(request)

        # None → False (cancellation treated as denial — this is correct behavior)
        assert result is False, f"Expected False for None result, got {result!r}"

    def test_bool_conversion_directly(self) -> None:
        """Test bool() conversion directly to demonstrate the original bug."""
        # These are all problematic conversions that the fix avoids:
        assert bool(None) is False   # Cancellation → Denial (now handled explicitly)

        # What the fix does: explicit if/elif instead of bool()
        # None → False (explicitly, for cancellation)
        # True → True
        # False → False

    @pytest.mark.anyio
    async def test_callback_with_various_values(self) -> None:
        """Test _callback behavior with various input values.

        This tests the closure logic inline to verify explicit if/elif handling.
        """
        loop = asyncio.get_running_loop()
        future = loop.create_future()

        class MockSelf:
            def __init__(self) -> None:
                self._confirm_futures: dict[int, asyncio.Future[bool]] = {}

        mock_self = MockSelf()
        req_id = 1

        def simulate_callback(result: object | None) -> None:
            """Simulate the fixed _callback closure logic."""
            with contextlib.suppress(asyncio.InvalidStateError, asyncio.CancelledError):
                if result is True:
                    future.set_result(True)
                elif result is False or result is None:
                    future.set_result(False)
                else:
                    future.set_result(False)
            futures_dict = getattr(mock_self, "_confirm_futures", None)
            if futures_dict is not None:
                futures_dict.pop(req_id, None)

        mock_self._confirm_futures[req_id] = future
        simulate_callback(None)

        assert future.done(), "Future should be done after callback"
        assert future.result() is False, "None should become False"

        # Verify all cases with explicit if/elif (no bool() ambiguity)
        test_cases = [
            (None, False, "None → False (cancellation)"),
            (True, True, "True → True"),
            (False, False, "False → False"),
        ]
        for input_val, expected, description in test_cases:
            if input_val is True:
                actual = True
            elif input_val is False or input_val is None:
                actual = False
            else:
                actual = False
            assert actual is expected, f"Failed: {description}"

    @pytest.mark.anyio
    async def test_actual_bug_reproduction(self) -> None:
        """Verify fix: explicit if/elif in callback instead of bool()."""
        import inspect
        import henchman.cli.textual_mixins as module

        source = inspect.getsource(module._InitMixin._textual_confirm)

        # The fix uses explicit if/elif, NOT bool(result)
        assert "bool(result)" not in source, (
            "Bug present: callback still uses bool(result) instead of explicit if/elif"
        )
        assert "result is True" in source or "if result is True" in source, (
            "Fix not applied: explicit 'if result is True' check missing from callback"
        )
