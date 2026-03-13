"""Test to actually reproduce infinite loop."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from henchman.agents.orchestrator_execution import ExecutionController
from henchman.agents.orchestrator_types import AgentLoopParams, LoopState
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import ToolCall, Message


class ExhaustedGeneratorAgent:
    """Agent with an exhausted generator that keeps returning the same exhausted generator."""
    def __init__(self):
        self.messages = []
        self._call_count = 0
    
    async def run(self, input_text):
        self._call_count += 1
        # Create a generator that's already exhausted
        async def exhausted_gen():
            # This generator immediately raises StopAsyncIteration
            if False:
                yield
        return exhausted_gen()
    
    def continue_with_tool_results(self):
        # Return another exhausted generator
        self._call_count += 1
        async def exhausted_gen():
            if False:
                yield
        return exhausted_gen()


@pytest.mark.asyncio
async def test_actual_infinite_loop():
    """Test actual infinite loop scenario."""
    # Create mock orchestrator WITHOUT validator (to trigger AttributeError)
    mock_orchestrator = MagicMock()
    # Don't set validator attribute at all
    
    # Create execution controller
    controller = ExecutionController(mock_orchestrator)
    
    # Create agent with exhausted generator
    agent = ExhaustedGeneratorAgent()
    
    # Create params
    params = AgentLoopParams(agent=agent, input_text="Test")
    
    # Collect events
    events = []
    iteration_count = 0
    try:
        async for event in controller.run_agent_loop(params):
            events.append(event)
            iteration_count += 1
            if iteration_count > 10:
                pytest.fail(f"Infinite loop detected - {iteration_count} iterations")
                break
    except AttributeError as e:
        print(f"AttributeError (expected): {e}")
        # This is expected if validator doesn't exist
        pass
    except Exception as e:
        print(f"Unexpected exception: {e}")
        pytest.fail(f"Unexpected exception: {e}")
    
    print(f"Test completed after {iteration_count} iterations")
    
    # Should have 0 iterations (loop should break or raise exception)
    assert iteration_count == 0, f"Expected 0 iterations, got {iteration_count}"


@pytest.mark.asyncio
async def test_infinite_loop_with_missing_validator():
    """Test infinite loop when validator attribute is missing."""
    # Create mock orchestrator with missing validator
    mock_orchestrator = MagicMock()
    # Set validator to None (not missing, but None)
    mock_orchestrator.validator = None
    
    # Create execution controller
    controller = ExecutionController(mock_orchestrator)
    
    # Create simple agent
    class SimpleAgent:
        def __init__(self):
            self.messages = []
        
        async def run(self, input_text):
            # Yield nothing, generator immediately exhausted
            if False:
                yield
    
    agent = SimpleAgent()
    
    # Create params
    params = AgentLoopParams(agent=agent, input_text="Test")
    
    # This should raise AttributeError when trying to call validator methods
    events = []
    iteration_count = 0
    try:
        async for event in controller.run_agent_loop(params):
            events.append(event)
            iteration_count += 1
            if iteration_count > 5:
                pytest.fail(f"Loop didn't break - {iteration_count} iterations")
                break
    except AttributeError as e:
        print(f"AttributeError (expected): {e}")
        # Expected - validator is None
    except Exception as e:
        print(f"Unexpected exception: {e}")
    
    print(f"Test completed after {iteration_count} iterations")