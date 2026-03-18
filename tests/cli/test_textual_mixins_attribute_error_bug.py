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
        """Test _textual_confirm raises AttributeError when state not initialized.
        
        This is the bug: _textual_confirm assumes _init_confirm_state() was called,
        but doesn't check. If called before initialization, it will raise AttributeError
        when trying to access _confirm_lock, _confirm_counter, or _confirm_futures.
        """
        # Create an instance without calling _init_confirm_state
        obj = MagicMock(spec=_InitMixin)
        
        # Don't initialize the state attributes
        # obj._confirm_lock, obj._confirm_counter, obj._confirm_futures don't exist
        
        # Create a mock request
        request = MagicMock(spec=ConfirmationRequest)
        request.tool_name = "test_tool"
        request.arguments = {}
        request.kind = "EXECUTE"
        
        # Get the method
        confirm_method = _InitMixin._textual_confirm
        
        # This should raise AttributeError because _confirm_lock doesn't exist
        with pytest.raises(AttributeError) as exc_info:
            await confirm_method(obj, request)
        
        # Verify it's the expected attribute error
        assert "_confirm_lock" in str(exc_info.value) or \
               "_confirm_counter" in str(exc_info.value) or \
               "_confirm_futures" in str(exc_info.value)
    
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