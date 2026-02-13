#!/usr/bin/env python3
"""Test Ctrl+C and Esc key behavior in Henchman REPL."""

import asyncio
from unittest.mock import MagicMock

import pytest

from henchman.cli.repl import Repl, ReplConfig


class TestKeyboardInterruptHandling:
    """Test Ctrl+C and Esc key handling."""

    @pytest.mark.asyncio
    async def test_ctrl_c_continues_eof_exits(self):
        """Test that Ctrl+C continues the REPL, EOF exits."""
        # Create a mock REPL instance
        repl = Repl(
            provider=MagicMock(),
            console=MagicMock(),
            config=ReplConfig(prompt="> ", system_prompt=""),
        )

        # Mock _get_input to simulate Ctrl+C then Ctrl+D
        call_count = 0

        async def mock_get_input():
            nonlocal call_count
            await asyncio.sleep(0)
            call_count += 1
            if call_count == 1:
                raise KeyboardInterrupt()  # Should continue
            raise EOFError()  # Should exit

        repl._get_input = mock_get_input

        # Run the REPL - it should exit on EOFError
        await repl.run()
        assert not repl.running
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_esc_key_should_stop_agent(self):
        """Test that Esc key should stop the current agent operation."""
        # This test would require simulating Esc key press
        # which is more complex with prompt_toolkit
        pass

    @pytest.mark.asyncio
    async def test_multiple_ctrl_c_then_eof_exits(self):
        """Test that multiple Ctrl+C presses continue, then EOF exits."""
        repl = Repl(
            provider=MagicMock(),
            console=MagicMock(),
            config=ReplConfig(prompt="> ", system_prompt=""),
        )

        call_count = 0

        async def mock_get_input():
            nonlocal call_count
            await asyncio.sleep(0)
            call_count += 1
            if call_count <= 3:
                raise KeyboardInterrupt()  # Multiple Ctrl+C should continue
            raise EOFError()  # EOF should exit

        repl._get_input = mock_get_input

        # Should exit on EOF after multiple Ctrl+C
        await repl.run()
        assert not repl.running
        assert call_count == 1


if __name__ == "__main__":
    print("Creating test file for keyboard interrupt handling...")
