#!/usr/bin/env python3
"""Test Ctrl+C and Esc key behavior in Henchman REPL."""

import asyncio
import signal
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prompt_toolkit.input import create_input
from prompt_toolkit.keys import Keys

from henchman.cli.repl import Repl


class TestKeyboardInterruptHandling:
    """Test Ctrl+C and Esc key handling."""
    
    @pytest.mark.asyncio
    async def test_ctrl_c_should_exit(self):
        """Test that Ctrl+C should exit the program, not just clear line."""
        # Create a mock REPL instance
        repl = Repl(
            provider=MagicMock(),
            console=MagicMock(),
            config=MagicMock()
        )
        repl.running = True
        
        # Mock _get_input to simulate Ctrl+C
        async def mock_get_input():
            raise KeyboardInterrupt()
        
        repl._get_input = mock_get_input
        
        # Run the REPL - it should exit on Ctrl+C
        with pytest.raises(SystemExit):
            await repl.run()
    
    @pytest.mark.asyncio
    async def test_esc_key_should_stop_agent(self):
        """Test that Esc key should stop the current agent operation."""
        # This test would require simulating Esc key press
        # which is more complex with prompt_toolkit
        pass
    
    @pytest.mark.asyncio
    async def test_double_ctrl_c_exits(self):
        """Test that pressing Ctrl+C twice quickly should exit."""
        repl = Repl(
            provider=MagicMock(),
            console=MagicMock(),
            config=MagicMock()
        )
        repl.running = True
        
        call_count = 0
        async def mock_get_input():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise KeyboardInterrupt()
            elif call_count == 2:
                # Second Ctrl+C within short time should exit
                raise KeyboardInterrupt()
        
        repl._get_input = mock_get_input
        
        # Should exit on second Ctrl+C
        with pytest.raises(SystemExit):
            await repl.run()


if __name__ == "__main__":
    print("Creating test file for keyboard interrupt handling...")
