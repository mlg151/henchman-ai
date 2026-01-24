#!/usr/bin/env python3
"""Test Ctrl+C and Esc key behavior fixes."""

import asyncio
from unittest.mock import MagicMock

import pytest
from prompt_toolkit.keys import Keys

from henchman.cli.input import create_session
from henchman.cli.repl import Repl, ReplConfig


class TestCtrlCFixes:
    """Test that Ctrl+C properly exits the program."""

    @pytest.mark.asyncio
    async def test_single_ctrl_c_exits(self):
        """Test that a single Ctrl+C should exit the REPL."""
        # Create mock dependencies
        mock_provider = MagicMock()
        mock_console = MagicMock()
        mock_config = ReplConfig(prompt="> ", system_prompt="")

        repl = Repl(
            provider=mock_provider,
            console=mock_console,
            config=mock_config
        )

        # Mock _get_input to raise KeyboardInterrupt immediately
        async def mock_get_input():
            raise KeyboardInterrupt()

        repl._get_input = mock_get_input

        # The run method should exit when KeyboardInterrupt is raised
        # Currently it continues, but after our fix it should exit
        await repl.run()

        # Verify running is False after exit
        assert not repl.running

        # Verify goodbye was printed
        mock_console.print.assert_any_call("[dim]Goodbye![/]")

    @pytest.mark.asyncio
    async def test_ctrl_c_during_agent_operation(self):
        """Test that Ctrl+C during agent operation stops the agent."""
        mock_provider = MagicMock()
        mock_console = MagicMock()
        mock_config = ReplConfig(prompt="> ", system_prompt="")

        repl = Repl(
            provider=mock_provider,
            console=mock_console,
            config=mock_config
        )

        # Mock agent to simulate long-running operation
        mock_agent = MagicMock()
        async def mock_agent_run(*_args, **_kwargs):
            # Simulate agent thinking for a bit
            await asyncio.sleep(0.1)
            # Then raise KeyboardInterrupt to simulate Ctrl+C
            raise KeyboardInterrupt()
            yield # Make it an async generator

        mock_agent.run = mock_agent_run
        repl.agent = mock_agent

        # Mock process_input to use our agent
        async def mock_process_input(user_input):
            await repl._run_agent(user_input)
            return True

        repl.process_input = mock_process_input

        # Mock _get_input to provide input then Ctrl+C
        call_count = 0
        async def mock_get_input():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "test input"
            else:
                raise KeyboardInterrupt()

        repl._get_input = mock_get_input

        # Run should handle Ctrl+C gracefully
        await repl.run()
        assert not repl.running


class TestEscKeyFixes:
    """Test that Esc key properly stops operations."""

    @pytest.mark.asyncio
    async def test_esc_clears_buffer(self):
        """Test that Esc key clears the input buffer."""
        # Test the existing behavior
        from prompt_toolkit.buffer import Buffer

        session = create_session()

        # Create a mock event
        mock_event = MagicMock()
        mock_buffer = Buffer()
        mock_buffer.text = "test input"
        mock_event.current_buffer = mock_buffer

        # Get the escape handler
        bindings = session.key_bindings
        escape_handler = None
        for binding in bindings.bindings:
            if hasattr(binding, 'keys') and Keys.Escape in binding.keys:
                escape_handler = binding.handler
                break

        assert escape_handler is not None, "Escape key binding not found"

        # Test clearing buffer with text
        mock_buffer.text = "some input"
        escape_handler(mock_event)
        assert mock_buffer.text == "", "Escape should clear buffer text"

    @pytest.mark.asyncio
    async def test_esc_on_empty_buffer_should_cancel(self):
        """Test that Esc on empty buffer should signal cancellation."""
        # Currently this doesn't do anything, but after our fix
        # it should raise a special exception or signal
        session = create_session()

        mock_event = MagicMock()
        mock_buffer = MagicMock()
        mock_buffer.text = ""
        mock_event.current_buffer = mock_buffer

        # Get escape handler
        bindings = session.key_bindings
        escape_handler = None
        for binding in bindings.bindings:
            if hasattr(binding, 'keys') and Keys.Escape in binding.keys:
                escape_handler = binding.handler
                break

        # Currently does nothing on empty buffer
        # After fix, should raise an exception or set a flag
        with pytest.raises(KeyboardInterrupt):
            escape_handler(mock_event)
        # No assertion - just verifying it doesn't crash


class TestSignalHandling:
    """Test signal handling integration."""

    @pytest.mark.asyncio
    async def test_graceful_shutdown_on_sigint(self):
        """Test that SIGINT (Ctrl+C) causes graceful shutdown."""
        # This would test OS-level signal handling
        # For now, just a placeholder
        pass


if __name__ == "__main__":
    print("Keyboard interrupt tests created.")
    print("Run with: pytest tests/cli/test_keyboard_fixes.py -v")
