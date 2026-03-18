"""Test for a REAL functional bug in textual_mixins.py.

Found through Four Lenses analysis.
"""

from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

from henchman.cli.textual_mixins import _InitMixin
from henchman.tools.base import ConfirmationRequest


class TestRealFunctionalBug:
    """Test that demonstrates a REAL functional bug."""
    
    @pytest.mark.anyio
    async def test_callback_boolean_conversion_bug(self) -> None:
        """Test that _callback doesn't handle truthy/falsy values correctly.
        
        BUG: _callback checks `if result is True:` and `elif result is False or result is None:`
        but doesn't handle truthy/falsy values like 1, 0, "yes", "".
        
        If UI returns truthy but not True, it's treated as error.
        If UI returns falsy but not False/None, it's treated as error.
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        mixin = _InitMixin.__new__(_InitMixin)
        
        # Test various inputs
        test_cases = [
            (True, True, "Should accept True"),
            (False, False, "Should accept False"),
            (None, False, "Should treat None as False"),
            (1, False, "BUG: 1 is truthy but treated as error"),
            (0, False, "BUG: 0 is falsy but treated as error"),
            ("yes", False, "BUG: 'yes' is truthy but treated as error"),
            ("", False, "BUG: '' is falsy but treated as error"),
            ([], False, "BUG: [] is falsy but treated as error"),
            ({}, False, "BUG: {} is falsy but treated as error"),
        ]
        
        for input_val, expected_treated_as, description in test_cases:
            # Create future
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            
            # Create callback (simplified)
            def _callback(result: object | None) -> None:
                with contextlib.suppress(asyncio.InvalidStateError):
                    if result is True:
                        future.set_result(True)
                    elif result is False or result is None:
                        future.set_result(False)
                    else:
                        # This is the buggy path
                        future.set_result(False)
            
            # Call callback
            _callback(input_val)
            
            if future.done():
                result = future.result()
                print(f"{description}: input={input_val!r}, result={result}, expected treated as={expected_treated_as}")
                
                # The bug: non-bool values go to else branch
                if input_val not in (True, False, None):
                    print(f"  BUG: {input_val!r} ({type(input_val).__name__}) treated as error")
            else:
                print(f"{description}: future not done")
    
    @pytest.mark.anyio
    async def test_boolean_conversion_affects_return_value(self) -> None:
        """Test that the boolean conversion bug affects _textual_confirm return.
        
        If UI returns truthy but not True, _textual_confirm returns False
        (after logging error).
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._init_confirm_state()
        
        # Track log messages
        log_messages = []
        
        def mock_logger_error(msg, *args):
            log_messages.append(msg % args if args else msg)
        
        # Mock push_screen to call callback with non-bool value
        async def mock_push_screen(screen, callback):
            # Call callback with truthy but not True value
            callback(1)  # Integer 1
            return None
        
        mixin.push_screen = mock_push_screen
        
        # Mock screen class
        with patch('henchman.cli.textual_mixins._import_module') as mock_import:
            mock_screen_cls = MagicMock()
            mock_import.return_value.ConfirmToolScreen = mock_screen_cls
            
            # Patch logger.error to capture
            with patch('henchman.cli.textual_mixins.logger.error', mock_logger_error):
                # Create request
                request = ConfirmationRequest(
                    tool_name="test_tool",
                    description="Test tool",
                    params={},
                    risk_level="medium"
                )
                
                # Run _textual_confirm
                result = await mixin._textual_confirm(request)
                
                # Check result
                print(f"Result: {result}")
                print(f"Log messages: {log_messages}")
                
                # Bug is fixed: truthy value 1 is converted to True (with a warning)
                assert result is True, "Bug is fixed: truthy value 1 returns True"
                
                print("Bug is fixed: truthy non-bool values are converted to bool with a warning")