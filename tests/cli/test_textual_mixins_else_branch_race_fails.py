"""Test for else branch race condition - now fixed.

The race condition has been fixed by adding defensive initialization
and raising RuntimeError when state is not properly initialized.
"""

from __future__ import annotations

import asyncio
import pytest
from henchman.tools.base import ConfirmationRequest


class TestElseBranchRaceFails:
    """Test that the else branch race condition is now fixed."""
    
    @pytest.mark.anyio
    async def test_else_branch_race_with_yields(self) -> None:
        """Test that _textual_confirm raises RuntimeError when state not initialized.
        
        The method should raise RuntimeError if _confirm_lock is missing.
        """
        from henchman.cli.textual_mixins import _InitMixin
        
        # Create instance without _confirm_lock
        mixin = _InitMixin.__new__(_InitMixin)
        mixin._confirm_futures = {}
        mixin._confirm_counter = 0
        # No _confirm_lock!
        
        # Create a simple confirmation request
        request = ConfirmationRequest(
            tool_name="test_tool",
            description="Test tool execution",
            params={"arg": "value"},
            risk_level="medium"
        )
        
        # Should raise RuntimeError because _confirm_lock is missing
        with pytest.raises(RuntimeError, match="_textual_confirm called before _init_confirm_state"):
            await mixin._textual_confirm(request)