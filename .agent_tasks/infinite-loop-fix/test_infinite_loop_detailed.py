"""Detailed test to reproduce the infinite loop bug."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from henchman.agents.orchestrator_execution import ExecutionController
from henchman.agents.orchestrator_types import AgentLoopParams, LoopState
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import ToolCall, Message


class MockAgent:
    def __init__(self):
        self.messages = []
        self._call_count = 0
    
    async def run(self, input_text):
        self._call_count += 1
        # First call: yield content ending with colon (simulating colon stall)
        if self._call_count == 1:
            self.messages.append(Message(role="assistant", content="Let me create the script:"))
            yield AgentEvent(type=EventType.CONTENT, data="Let me create the script:")
        # Generator is now exhausted
    
    def continue_with_tool_results(self):
        # This creates a new generator
        self._call_count += 1
        # Simulate infinite loop: always return a generator that yields nothing
        async def empty_generator():
            # Yield nothing, generator immediately exhausted
            if False:
                yield
        return empty_generator()


@pytest.mark.asyncio
async def test_infinite_loop_colon_stall_scenario():
    """Test infinite loop when generator exhausted but colon stall creates new generator."""
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
    iteration_count = 0
    try:
        async for event in controller.run_agent_loop(params):
            events.append(event)
            iteration_count += 1
            # Break after too many iterations to avoid actual infinite loop
            if iteration_count > 5:
                pytest.fail(f"Infinite loop detected - {iteration_count} iterations without breaking")
                break
    except Exception as e:
        print(f"Exception: {e}")
        pytest.fail(f"Unexpected exception: {e}")
    
    print(f"Test completed after {iteration_count} iterations")
    print(f"Events collected: {len(events)}")
    
    # The loop should have completed
    assert iteration_count <= 5, "Loop should have broken, not continued indefinitely"


@pytest.mark.asyncio
async def test_generator_exhaustion_without_colon_stall():
    """Test that loop breaks when generator exhausted without colon stall."""
    # Create mock orchestrator with validator
    mock_orchestrator = MagicMock()
    mock_orchestrator.validator = MagicMock()
    mock_orchestrator.validator.check_thinking_pattern = MagicMock(return_value=None)
    mock_orchestrator.validator.check_stall_failure = MagicMock(return_value=None)
    
    # Create execution controller
    controller = ExecutionController(mock_orchestrator)
    
    # Create mock agent without colon stall
    class SimpleAgent:
        def __init__(self):
            self.messages = []
        
        async def run(self, input_text):
            # Yield content without colon
            self.messages.append(Message(role="assistant", content="Simple response"))
            yield AgentEvent(type=EventType.CONTENT, data="Simple response")
            # Generator exhausted
    
    agent = SimpleAgent()
    
    # Create params
    params = AgentLoopParams(agent=agent, input_text="Test")
    
    # Collect events
    events = []
    iteration_count = 0
    async for event in controller.run_agent_loop(params):
        events.append(event)
        iteration_count += 1
    
    print(f"Test completed after {iteration_count} iterations")
    print(f"Events collected: {len(events)}")
    
    # Should have exactly 1 iteration
    assert iteration_count == 1, f"Expected 1 iteration, got {iteration_count}"
    assert len(events) == 1, f"Expected 1 event, got {len(events)}"