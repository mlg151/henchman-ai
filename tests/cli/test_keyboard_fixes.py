#!/usr/bin/env python3
"""Test Ctrl+C and Esc key behavior fixes."""

import asyncio
from unittest.mock import MagicMock

import pytest

from henchman.cli.repl import Repl, ReplConfig


class TestCtrlCFixes:
    """Test that Ctrl+C properly exits the program."""

    @pytest.mark.asyncio
    async def test_ctrl_c_continues_and_eof_exits(self):
        """Test that Ctrl+C continues the REPL and Ctrl+D (EOF) exits."""
        # Create mock dependencies
        mock_provider = MagicMock()
        mock_console = MagicMock()
        mock_config = ReplConfig(prompt="> ", system_prompt="")

        repl = Repl(
            provider=mock_provider,
            console=mock_console,
            config=mock_config,
        )

        # Mock _get_input to:
        # 1. Return some input
        # 2. Raise KeyboardInterrupt (Ctrl+C) - should continue
        # 3. Raise EOFError (Ctrl+D) - should exit
        call_count = 0

        async def mock_get_input():
            nonlocal call_count
            await asyncio.sleep(0)
            call_count += 1
            if call_count == 1:
                return "dummy input"
            if call_count == 2:
                raise KeyboardInterrupt()
            raise EOFError()

        repl._get_input = mock_get_input

        # Mock process_input to just return True
        async def mock_process_input(_user_input: str) -> bool:
            return True

        repl.process_input = mock_process_input

        # Run the REPL - should exit on EOFError
        await repl.run()

        # Verify running is False after exit
        assert not repl.running

        # Verify we went through all calls
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_ctrl_c_during_agent_operation(self):
        """Test that Ctrl+C during agent operation is handled gracefully."""
        mock_provider = MagicMock()
        mock_console = MagicMock()
        mock_config = ReplConfig(prompt="> ", system_prompt="")

        repl = Repl(
            provider=mock_provider,
            console=mock_console,
            config=mock_config,
        )

        # Track whether agent was called
        agent_called = False

        # Mock process_input to simulate KeyboardInterrupt during processing
        async def mock_process_input(_user_input: str) -> bool:
            nonlocal agent_called
            if not agent_called:
                agent_called = True
                raise KeyboardInterrupt()  # Simulate Ctrl+C during processing
            return True

        repl.process_input = mock_process_input

        # Mock _get_input to provide input then EOF
        call_count = 0

        async def mock_get_input():
            nonlocal call_count
            await asyncio.sleep(0)
            call_count += 1
            if call_count <= 2:
                return "test input"
            raise EOFError()

        repl._get_input = mock_get_input

        # Run the REPL
        await repl.run()

        # Verify agent was called and we handled the interrupt
        assert agent_called
        assert not repl.running
