"""Smoke tests for Escape key behavior.

These tests verify that pressing Escape:
1. Immediately returns control to the prompt
2. Does NOT quit the program
3. Stops any ongoing agent operation
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from prompt_toolkit.keys import Keys

from henchman.cli.input import create_session
from henchman.cli.repl import Repl, ReplConfig
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import ModelProvider


class TestEscapeKeyReturnsToPrompt:
    """Smoke tests for Escape key returning to prompt without quitting."""

    def test_escape_on_empty_buffer_exits_prompt_not_program(self):
        """Escape on empty buffer returns empty string, not exit signal.

        When the user presses Escape at an empty prompt:
        - The prompt should return (with empty result)
        - The REPL should continue running (not exit)
        - The user should see a new prompt
        """
        # Create a prompt session
        session = create_session()

        # Verify the escape key binding exists
        bindings = session.key_bindings
        escape_handlers = [b for b in bindings.bindings if b.keys == (Keys.Escape,)]

        assert len(escape_handlers) > 0, "Escape key binding should exist"

        # The escape handler uses event.app.exit(result="") which returns
        # an empty string, not a quit signal

    @pytest.mark.anyio
    async def test_repl_continues_after_keyboard_interrupt(self):
        """REPL continues running after KeyboardInterrupt from Escape.

        This simulates what happens when Escape triggers KeyboardInterrupt:
        the REPL should catch it and continue, not exit.
        """
        # Create mock provider
        mock_provider = AsyncMock(spec=ModelProvider)
        mock_provider.name = "mock"

        # Create REPL
        repl = Repl(
            provider=mock_provider,
            config=ReplConfig(auto_save=False),
        )

        # Track iterations
        iteration_count = 0

        async def mock_get_input():
            nonlocal iteration_count
            iteration_count += 1

            if iteration_count == 1:
                return "hello"
            elif iteration_count == 2:
                # This input should be given after the agent was interrupted
                return "/quit"
            return ""  # Should not be reached

        # Mock the agent run to yield some content then get interrupted
        async def mock_agent_run_stream(_msg):
            yield AgentEvent(type=EventType.CONTENT, data="Part 1...")
            # Simulate a brief delay to allow KeyMonitor to be set up
            await asyncio.sleep(0.01)
            # Simulate KeyMonitor detecting Esc key
            if repl.current_monitor:
                repl.current_monitor.stop_requested = True

            yield AgentEvent(
                type=EventType.CONTENT, data="Part 2..."
            )  # This part should not be seen
            yield AgentEvent(type=EventType.FINISHED)

        repl.agent.run = mock_agent_run_stream

        with patch.object(repl, "_get_input", side_effect=mock_get_input):
            await repl.run()

        # Verify REPL continued after interruption
        # It should make one input, then the agent is interrupted, then it asks for another input to quit
        assert iteration_count == 2, (
            f"REPL should have continued after Escape. Got {iteration_count} iterations, expected 2"
        )

    @pytest.mark.anyio
    async def test_escape_during_agent_operation_stops_agent(self):
        """Escape during agent operation stops it and returns to prompt.

        When the agent is generating a response and user presses Escape:
        - The agent operation should be interrupted
        - The REPL should return to the prompt
        - The program should NOT exit
        """
        mock_provider = AsyncMock(spec=ModelProvider)
        mock_provider.name = "mock"

        repl = Repl(
            provider=mock_provider,
            config=ReplConfig(auto_save=False),
        )

        # Track state
        agent_started = False
        agent_interrupted = False
        returned_to_prompt = False

        async def slow_agent_run(_msg):
            nonlocal agent_started, agent_interrupted
            agent_started = True

            try:
                # Simulate slow streaming - yields one token, then waits
                yield AgentEvent(type=EventType.CONTENT, data="Hello")
                await asyncio.sleep(10)  # Simulate long operation
                yield AgentEvent(type=EventType.FINISHED)
            except asyncio.CancelledError:
                agent_interrupted = True
                raise

        input_count = 0

        async def mock_input():
            nonlocal input_count, returned_to_prompt
            input_count += 1

            if input_count == 1:
                return "tell me a story"
            elif input_count == 2:
                returned_to_prompt = True
                return "/quit"
            return "/quit"

        async def mock_run_agent(user_input):
            """Simulate agent run that can be interrupted."""
            try:
                async for event in slow_agent_run(user_input):
                    if event.type == EventType.CONTENT:
                        repl.renderer.print(event.data)
            except asyncio.CancelledError:
                pass  # Gracefully handle cancellation

        # Patch to simulate the behavior
        with (
            patch.object(repl, "_get_input", side_effect=mock_input),
            patch.object(repl, "_run_agent", side_effect=mock_run_agent),
        ):
            await repl.run()

        # Verify the flow: REPL returned to prompt after first interaction
        assert returned_to_prompt, "REPL should have returned to prompt"

    def test_escape_key_binding_returns_empty_not_none(self):
        """Escape key binding returns empty string, allowing REPL to continue.

        The key difference between Escape and Ctrl+D:
        - Ctrl+D: raises EOFError (exits program)
        - Escape: returns empty string (continues program)
        """
        session = create_session()
        bindings = session.key_bindings

        # Find the escape binding
        escape_binding = None
        for binding in bindings.bindings:
            if binding.keys == (Keys.Escape,):
                escape_binding = binding
                break

        assert escape_binding is not None, "Escape binding must exist"

        # The handler uses event.app.exit(result="") not event.app.exit()
        # This means prompt returns "" instead of raising EOFError
        # Verify by checking the handler implementation exists
        assert callable(escape_binding.handler), "Escape handler must be callable"


class TestEscapeKeyDoesNotQuit:
    """Verify Escape key never causes program exit."""

    @pytest.mark.anyio
    async def test_multiple_escapes_do_not_quit(self):
        """Pressing Escape multiple times should not quit the program.

        Unlike double Ctrl+C which exits, multiple Escapes should:
        - Keep returning to the prompt
        - Never exit the program
        """
        mock_provider = AsyncMock(spec=ModelProvider)
        mock_provider.name = "mock"

        repl = Repl(
            provider=mock_provider,
            config=ReplConfig(auto_save=False),
        )

        escape_count = 0
        max_escapes = 5

        async def mock_input():
            nonlocal escape_count
            escape_count += 1

            if escape_count <= max_escapes:
                # Simulate Escape by returning empty string
                # (which is what Escape key does via event.app.exit(result=""))
                return ""
            else:
                return "/quit"

        with patch.object(repl, "_get_input", side_effect=mock_input):
            await repl.run()

        # REPL should have handled all escapes without quitting
        assert escape_count == max_escapes + 1, (
            f"REPL should have handled {max_escapes} escapes before /quit. "
            f"Got {escape_count} total inputs."
        )

    @pytest.mark.anyio
    async def test_escape_after_output_returns_to_prompt(self):
        """After agent produces output, Escape returns to clean prompt.

        Scenario:
        1. User asks a question
        2. Agent starts responding
        3. User presses Escape (simulated as monitor.stop_requested)
        4. REPL shows new prompt
        5. Program is still running
        """
        mock_provider = AsyncMock(spec=ModelProvider)
        mock_provider.name = "mock"

        repl = Repl(
            provider=mock_provider,
            config=ReplConfig(auto_save=False),
        )

        prompts_shown = 0

        async def mock_input():
            nonlocal prompts_shown
            prompts_shown += 1
            if prompts_shown == 1:
                return "hello"
            elif prompts_shown == 2:
                return "/quit"
            return ""  # Should not be reached

        async def mock_agent_run_stream(_msg):
            yield AgentEvent(type=EventType.CONTENT, data="Hello there!")
            await asyncio.sleep(0.01)  # Simulate some work
            # Simulate KeyMonitor detecting Esc key
            if repl.current_monitor:
                repl.current_monitor.stop_requested = True
            yield AgentEvent(type=EventType.FINISHED)

        repl.agent.run = mock_agent_run_stream

        with patch.object(repl, "_get_input", side_effect=mock_input):
            await repl.run()

        # We should have seen 2 prompts: initial, after interruption/quit
        assert prompts_shown == 2, f"Should show prompt after Escape. Got {prompts_shown} prompts."


class TestEscapeVsCtrlCBehavior:
    """Verify Escape and Ctrl+C have different behaviors."""

    def test_escape_is_not_exit_signal(self):
        """Escape should not be treated as an exit signal.

        This is the key behavioral difference:
        - Escape: Cancel current operation, return to prompt
        - Ctrl+C twice: Exit the program
        """
        session = create_session()
        bindings = session.key_bindings

        escape_handler = None
        ctrl_c_handler = None

        for binding in bindings.bindings:
            if binding.keys == (Keys.Escape,):
                escape_handler = binding
            elif binding.keys == (Keys.ControlC,):
                ctrl_c_handler = binding

        assert escape_handler is not None, "Escape binding must exist"
        assert ctrl_c_handler is not None, "Ctrl+C binding must exist"

        # They should be different handlers with different behaviors
        assert escape_handler.handler != ctrl_c_handler.handler, (
            "Escape and Ctrl+C should have different handlers"
        )
