import asyncio
from unittest.mock import MagicMock

import pytest
from rich.console import Console

import henchman.cli.input  # Import for KeyMonitor access
from henchman.cli.repl import Repl
from henchman.core.events import AgentEvent, EventType


@pytest.mark.asyncio
async def test_esc_interrupt(mocker):
    # Setup
    provider = MagicMock()

    # Create an infinite slow event stream
    async def slow_stream():
        yield AgentEvent(type=EventType.CONTENT, data="Thinking...")
        while True:  # Infinite loop
            await asyncio.sleep(1)
            yield AgentEvent(type=EventType.CONTENT, data="Still thinking...")

    provider.run.return_value = slow_stream()

    # Mock the console
    mock_console = MagicMock(spec=Console)

    repl = Repl(provider=provider, console=mock_console)

    # Mock the warning method of the renderer
    repl.renderer.warning = MagicMock()

    # Create a mock monitor instance
    mock_monitor_instance = MagicMock(spec=henchman.cli.input.KeyMonitor)
    mock_monitor_instance.stop_requested = False
    mock_monitor_instance.exit_requested = False
    mock_monitor_instance._stop_event = asyncio.Event()  # For the finally block

    # We need to make sure that the `_run_agent` method uses our mock `KeyMonitor` instance.
    # The `_run_agent` method imports `KeyMonitor` locally and then instantiates it.
    # So we need to patch the `KeyMonitor` class itself, and ensure its `return_value` is our `mock_monitor_instance`.
    mocker.patch("henchman.cli.input.KeyMonitor", return_value=mock_monitor_instance)

    # Run agent
    agent_repl_task = asyncio.create_task(repl._run_agent("hello"))

    # Directly signal the interrupt on the mock monitor instance that repl._run_agent is using
    mock_monitor_instance.stop_requested = True

    # Wait for the agent_repl_task to finish (it should be cancelled internally)
    await agent_repl_task

    # Check output
    repl.renderer.warning.assert_called_once_with("\n[Interrupted by Esc]")
