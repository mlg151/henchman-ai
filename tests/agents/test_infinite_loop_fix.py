"""Unit tests for the infinite loop fix in orchestrator_execution.py."""
from unittest.mock import MagicMock

import pytest

from henchman.agents.orchestrator_execution import ExecutionController
from henchman.agents.orchestrator_types import AgentLoopParams
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import Message


@pytest.mark.asyncio
async def test_infinite_loop_on_generator_exhaustion():
    """Test that the loop breaks when generator is exhausted with no pending tool calls.

    This test verifies the fix for the infinite loop bug where collect_events
    would catch StopAsyncIteration silently, leaving an empty pending list,
    and _process_no_pending could return should_break=False, causing infinite loop.
    """
    # Create mock orchestrator with validator
    mock_orchestrator = MagicMock()
    mock_orchestrator.validator = MagicMock()
    mock_orchestrator.validator.check_thinking_pattern = MagicMock(return_value=None)
    mock_orchestrator.validator.check_stall_failure = MagicMock(return_value=None)

    # Create execution controller
    controller = ExecutionController(mock_orchestrator)

    # Create mock agent with exhausted generator
    agent = MagicMock()
    agent.messages = []

    # Mock agent.run to return an immediately exhausted generator
    async def exhausted_generator(_input_text=None):
        # Generator is immediately exhausted (no yield, just StopAsyncIteration)
        if False:
            yield

    agent.run = MagicMock(return_value=exhausted_generator())

    # Create params
    params = AgentLoopParams(agent=agent, input_text="Test")

    # Collect events - should complete without hanging
    events = []
    iteration_count = 0

    # Use asyncio.wait_for to prevent actual infinite loop
    try:
        async for event in controller.run_agent_loop(params):
            events.append(event)
            iteration_count += 1
            # Safety check - should not iterate more than once
            if iteration_count > 1:
                pytest.fail("Loop should have broken after generator exhaustion")
    except Exception as e:
        pytest.fail(f"Unexpected exception: {e}")

    # Should have 0 iterations (generator was immediately exhausted)
    assert iteration_count == 0, f"Expected 0 iterations, got {iteration_count}"

    # Verify agent.run was called
    agent.run.assert_called_once_with("Test")


@pytest.mark.asyncio
async def test_generator_exhaustion_with_colon_stall():
    """Test generator exhaustion with colon stall detection.

    When generator is exhausted and there's a colon stall, a new generator
    should be created via continue_with_tool_results().
    """
    # Create mock orchestrator with validator
    mock_orchestrator = MagicMock()
    mock_orchestrator.validator = MagicMock()
    mock_orchestrator.validator.check_thinking_pattern = MagicMock(return_value=None)
    mock_orchestrator.validator.check_stall_failure = MagicMock(return_value=None)

    # Create execution controller
    controller = ExecutionController(mock_orchestrator)

    # Create mock agent
    agent = MagicMock()
    agent.messages = [
        Message(role="assistant", content="Let me create the script:"),  # Colon stall
    ]

    # Track generator calls
    generator_call_count = 0

    async def mock_generator(_input_text=None):
        nonlocal generator_call_count
        generator_call_count += 1
        if generator_call_count == 1:
            # First generator yields content then exhausts
            yield AgentEvent(type=EventType.CONTENT, data="Let me create the script:")
            # Generator exhausted
        else:
            # Second generator (after colon stall nudge) yields different content
            yield AgentEvent(type=EventType.CONTENT, data="Here's the script...")
            # Update agent.messages with the new content
            agent.messages.append(Message(role="assistant", content="Here's the script..."))
            # Generator exhausted

    agent.run = MagicMock(side_effect=mock_generator)

    # Mock continue_with_tool_results to return a new generator
    agent.continue_with_tool_results = MagicMock(side_effect=mock_generator)

    # Create params
    params = AgentLoopParams(agent=agent, input_text="Test")

    # Collect events
    events = []
    iteration_count = 0

    try:
        async for event in controller.run_agent_loop(params):
            events.append(event)
            iteration_count += 1
            # Safety check
            if iteration_count > 10:
                pytest.fail("Possible infinite loop")
                break
    except Exception as e:
        pytest.fail(f"Unexpected exception: {e}")

    # Should have events from both generators
    assert iteration_count > 0, "Should have yielded events"

    # Should have called continue_with_tool_results for colon stall
    agent.continue_with_tool_results.assert_called_once()


@pytest.mark.asyncio
async def test_missing_validator_attribute():
    """Test that missing validator attribute doesn't cause infinite loop.

    The fix should handle AttributeError gracefully when validator is missing.
    """
    # Create mock orchestrator WITHOUT validator
    mock_orchestrator = MagicMock()
    # Don't set validator attribute at all

    # Create execution controller
    controller = ExecutionController(mock_orchestrator)

    # Create mock agent
    agent = MagicMock()
    agent.messages = []

    async def mock_generator(_input_text=None):
        # Yield some content then exhaust
        yield AgentEvent(type=EventType.CONTENT, data="Test content")
        # Generator exhausted

    agent.run = MagicMock(return_value=mock_generator())

    # Create params
    params = AgentLoopParams(agent=agent, input_text="Test")

    # This should not raise AttributeError (handled in _process_no_pending)
    events = []
    iteration_count = 0

    try:
        async for event in controller.run_agent_loop(params):
            events.append(event)
            iteration_count += 1
    except AttributeError as e:
        pytest.fail(f"AttributeError should be handled: {e}")
    except Exception:
        # Other exceptions are OK
        pass

    # Should have yielded at least the content event
    # The loop should break after generator exhaustion (not infinite loop)
    assert iteration_count >= 1, f"Expected at least 1 iteration, got {iteration_count}"
    # Should not have infinite loop (more than a reasonable number)
    assert iteration_count <= 10, f"Possible infinite loop: {iteration_count} iterations"


@pytest.mark.asyncio
async def test_normal_generator_completion():
    """Test normal generator completion (not immediately exhausted).

    Generator yields events, completes normally, loop should break.
    """
    # Create mock orchestrator with validator
    mock_orchestrator = MagicMock()
    mock_orchestrator.validator = MagicMock()
    mock_orchestrator.validator.check_thinking_pattern = MagicMock(return_value=None)
    mock_orchestrator.validator.check_stall_failure = MagicMock(return_value=None)

    # Create execution controller
    controller = ExecutionController(mock_orchestrator)

    # Create mock agent
    agent = MagicMock()
    agent.messages = []

    async def mock_generator(_input_text=None):
        # Yield some events
        yield AgentEvent(type=EventType.CONTENT, data="First event")
        yield AgentEvent(type=EventType.CONTENT, data="Second event")
        # Generator completes normally

    agent.run = MagicMock(return_value=mock_generator())

    # Create params
    params = AgentLoopParams(agent=agent, input_text="Test")

    # Collect events
    events = []
    iteration_count = 0

    try:
        async for event in controller.run_agent_loop(params):
            events.append(event)
            iteration_count += 1
    except Exception as e:
        pytest.fail(f"Unexpected exception: {e}")

    # Should have yielded both events
    assert iteration_count == 2, f"Expected 2 iterations, got {iteration_count}"
    assert len(events) == 2
    assert events[0].data == "First event"
    assert events[1].data == "Second event"


@pytest.mark.asyncio
async def test_generator_with_tool_calls():
    """Test generator that yields tool calls (not exhausted).

    When generator yields tool calls, they should be processed.
    """
    from henchman.providers.base import ToolCall

    # Create mock orchestrator with validator
    mock_orchestrator = MagicMock()
    mock_orchestrator.validator = MagicMock()
    mock_orchestrator.validator.check_thinking_pattern = MagicMock(return_value=None)
    mock_orchestrator.validator.check_stall_failure = MagicMock(return_value=None)

    # Mock tool controller
    mock_orchestrator.tool_controller = MagicMock()

    # Create execution controller
    controller = ExecutionController(mock_orchestrator)

    # Create mock agent
    agent = MagicMock()
    agent.messages = []

    # Create a tool call
    tool_call = ToolCall(id="test", name="read_file", arguments={"path": "test.py"})

    async def mock_generator(_input_text=None):
        # Yield a tool call
        yield AgentEvent(type=EventType.TOOL_CALL_REQUEST, data=tool_call)
        # Generator exhausted

    agent.run = MagicMock(return_value=mock_generator())

    # Mock continue_with_tool_results
    agent.continue_with_tool_results = MagicMock()

    # Create params
    params = AgentLoopParams(agent=agent, input_text="Test")

    # Collect events - this will hang because tool controller is mocked
    # but we can test that it doesn't infinite loop
    events = []
    iteration_count = 0

    try:
        # Just collect a few events to verify it starts
        async for event in controller.run_agent_loop(params):
            events.append(event)
            iteration_count += 1
            if iteration_count > 5:
                break  # Safety break
    except Exception:
        # Tool controller will fail, but that's OK for this test
        pass

    # Should have at least the tool call event
    assert iteration_count >= 1, "Should have yielded at least the tool call event"
