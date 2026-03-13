"""Test to reproduce the infinite loop bug."""
from unittest.mock import MagicMock

import pytest

from henchman.agents.orchestrator_execution import ExecutionController
from henchman.agents.orchestrator_types import AgentLoopParams
from henchman.core.events import AgentEvent, EventType


class MockAgent:
    def __init__(self):
        self.messages = []

    async def run(self, input_text):
        # Simulate a generator that yields some events then stops
        yield AgentEvent(type=EventType.CONTENT, data="Test content")
        # Generator ends without yielding tool calls

    def continue_with_tool_results(self):
        # This shouldn't be called if generator is exhausted
        raise RuntimeError("continue_with_tool_results called on exhausted generator")


@pytest.mark.asyncio
async def test_infinite_loop_on_generator_exhaustion():
    """Test that the loop breaks when generator is exhausted with no pending tool calls."""
    # Create mock orchestrator with validator
    mock_orchestrator = MagicMock()
    mock_orchestrator.validator = MagicMock()
    mock_orchestrator.validator.check_thinking_pattern = MagicMock(return_value=None)
    mock_orchestrator.validator.check_stall_failure = MagicMock(return_value=None)

    # Create execution controller
    controller = ExecutionController(mock_orchestrator)

    # Create mock agent
    agent = MockAgent()

    # Create params
    params = AgentLoopParams(agent=agent, input_text="Test")

    # Collect events to see what happens
    events = []
    try:
        async for event in controller.run_agent_loop(params):
            events.append(event)
            # Break after a few iterations to avoid actual infinite loop
            if len(events) > 10:
                pytest.fail("Infinite loop detected - loop didn't break after generator exhaustion")
    except Exception as e:
        print(f"Exception: {e}")

    # The loop should have completed
    assert len(events) == 1  # Should have yielded the content event
    print("Test passed - loop completed without hanging")
