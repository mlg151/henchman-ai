"""Test for AttributeError bug in _textual_confirm when _init_confirm_state not called."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from henchman.cli.textual_mixins import _InitMixin
from henchman.tools.base import ConfirmationRequest


class TestTextualConfirmAttributeErrorBug:
    """Test that _textual_confirm raises AttributeError if _init_confirm_state not called."""

    @pytest.mark.anyio
    async def test_textual_confirm_without_init_raises_attribute_error(self) -> None:
        """Test _textual_confirm raises RuntimeError when state not initialized.
        
        The method should raise RuntimeError with a clear message when
        _init_confirm_state() hasn't been called.
        """
        # Create an instance without calling _init_confirm_state
        obj = MagicMock(spec=_InitMixin)
        
        # Don't initialize the state attributes
        # obj._confirm_lock, obj._confirm_counter, obj._confirm_futures don't exist
        
        # Create a mock request
        request = MagicMock(spec=ConfirmationRequest)
        request.tool_name = "test_tool"
        request.description = "Test tool execution"
        request.params = {}
        request.risk_level = "medium"
        
        # Get the method
        confirm_method = _InitMixin._textual_confirm
        
        # This should raise RuntimeError because state is not initialized
        with pytest.raises(RuntimeError) as exc_info:
            await confirm_method(obj, request)
        
        # Verify it's the expected error
        assert "_textual_confirm called before _init_confirm_state" in str(exc_info.value)
    
    @pytest.mark.anyio 
    async def test_textual_confirm_with_init_works(self) -> None:
        """Test _textual_confirm works when state is properly initialized."""
        # Create an instance
        obj = MagicMock(spec=_InitMixin)
        
        # Initialize the state as the real code would
        obj._confirm_lock = asyncio.Lock()
        obj._confirm_counter = 0
        obj._confirm_futures = {}
        
        # Mock the screen pushing (will raise CancelledError to exit early)
        obj.push_screen = MagicMock(side_effect=asyncio.CancelledError())
        
        # Create a mock request
        request = MagicMock(spec=ConfirmationRequest)
        request.tool_name = "test_tool"
        request.arguments = {}
        request.kind = "EXECUTE"
        
        # Get the method
        confirm_method = _InitMixin._textual_confirm
        
        # This should raise CancelledError (from our mock), not AttributeError
        with pytest.raises(asyncio.CancelledError):
            await confirm_method(obj, request)