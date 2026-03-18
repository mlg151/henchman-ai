"""Unit of Doom test for boolean conversion bug in textual_mixins.py.

This test FAILS with current implementation, demonstrating the real bug.
After fix, this test should PASS.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

from henchman.cli.textual_mixins import _InitMixin
from henchman.tools.base import ConfirmationRequest


class TestBooleanBugUnitOfDoom:
    """Unit of Doom test for boolean conversion bug."""
    
    @pytest.mark.anyio
    async def test_boolean_conversion_bug_fails(self) -> None:
        """Test that demonstrates the boolean conversion bug.
        
        This test WILL FAIL with current implementation.
        After fix, it should PASS.
        """
        # Create properly initialized mixin
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._init_confirm_state()
        
        # Track what happens
        captured_logs = []
        
        def mock_logger_error(msg, *args):
            captured_logs.append(msg % args if args else msg)
        
        # Mock push_screen to simulate UI returning truthy non-bool value
        async def mock_push_screen(screen, callback):
            # Simulate UI returning integer 1 (truthy but not True)
            # This could happen if UI code has a bug or returns numeric value
            callback(1)
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
                
                # ASSERTION: This is the bug!
                # UI returned truthy value (1), which means "approve"
                # But method returns False (denies)
                assert result is True, (
                    f"BUG: Truthy value 1 should return True (approve), "
                    f"but returned {result} (type: {type(result).__name__})"
                )
                
                # Also check that no error was logged
                # (Truthy values shouldn't be treated as errors)
                error_logs = [log for log in captured_logs if "unexpected" in log.lower()]
                assert len(error_logs) == 0, (
                    f"BUG: Truthy value 1 shouldn't log error, but got: {error_logs}"
                )
    
    @pytest.mark.anyio
    async def test_falsy_non_bool_values(self) -> None:
        """Test falsy non-bool values like 0, "", [].
        
        These should return False (deny) without logging error.
        """
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._init_confirm_state()
        
        captured_logs = []
        
        def mock_logger_error(msg, *args):
            captured_logs.append(msg % args if args else msg)
        
        # Test cases: (input, should_return, description)
        test_cases = [
            (0, False, "0 should return False (falsy)"),
            ("", False, "Empty string should return False (falsy)"),
            ([], False, "Empty list should return False (falsy)"),
            ({}, False, "Empty dict should return False (falsy)"),
            (None, False, "None should return False (explicitly handled)"),
            (False, False, "False should return False"),
        ]
        
        for input_val, expected_result, description in test_cases:
            # Reset for each test
            captured_logs.clear()
            
            async def mock_push_screen(screen, callback):
                callback(input_val)
                return None
            
            mixin.push_screen = mock_push_screen
            
            with patch('henchman.cli.textual_mixins._import_module') as mock_import:
                mock_screen_cls = MagicMock()
                mock_import.return_value.ConfirmToolScreen = mock_screen_cls
                
                with patch('henchman.cli.textual_mixins.logger.error', mock_logger_error):
                    request = ConfirmationRequest(
                        tool_name="test_tool",
                        description="Test tool",
                        params={},
                        risk_level="medium"
                    )
                    
                    result = await mixin._textual_confirm(request)
                    
                    # Check result
                    assert result is expected_result, (
                        f"{description}: expected {expected_result}, got {result}"
                    )
                    
                    # Check no error logged for falsy values
                    # (Current implementation logs error for non-bool falsy values)
                    error_logs = [log for log in captured_logs if "unexpected" in log.lower()]
                    # This will fail with current implementation!
                    # Falsy non-bool values are treated as "unexpected"
                    assert len(error_logs) == 0, (
                        f"{description}: shouldn't log error for {input_val!r}, "
                        f"but got: {error_logs}"
                    )
    
    @pytest.mark.anyio
    async def test_truthy_values_variants(self) -> None:
        """Test various truthy values."""
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._init_confirm_state()
        
        captured_logs = []
        
        def mock_logger_error(msg, *args):
            captured_logs.append(msg % args if args else msg)
        
        # Truthy values that should return True
        truthy_values = [
            1,
            42,
            -1,  # Non-zero integer
            3.14,
            "yes",
            "true",
            "ok",
            [1, 2, 3],
            {"a": 1},
            object(),  # Any object is truthy
        ]
        
        for input_val in truthy_values:
            captured_logs.clear()
            
            async def mock_push_screen(screen, callback):
                callback(input_val)
                return None
            
            mixin.push_screen = mock_push_screen
            
            with patch('henchman.cli.textual_mixins._import_module') as mock_import:
                mock_screen_cls = MagicMock()
                mock_import.return_value.ConfirmToolScreen = mock_screen_cls
                
                with patch('henchman.cli.textual_mixins.logger.error', mock_logger_error):
                    request = ConfirmationRequest(
                        tool_name="test_tool",
                        description="Test tool",
                        params={},
                        risk_level="medium"
                    )
                    
                    result = await mixin._textual_confirm(request)
                    
                    # All truthy values should return True
                    assert result is True, (
                        f"Truthy value {input_val!r} ({type(input_val).__name__}) "
                        f"should return True, got {result}"
                    )
                    
                    # No error should be logged
                    error_logs = [log for log in captured_logs if "unexpected" in log.lower()]
                    assert len(error_logs) == 0, (
                        f"Truthy value {input_val!r} shouldn't log error, "
                        f"but got: {error_logs}"
                    )