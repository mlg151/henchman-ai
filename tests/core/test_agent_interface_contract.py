"""Contract tests for AgentInterface."""

from collections.abc import AsyncIterator
from unittest.mock import MagicMock

import pytest

from henchman.agents.identity import AgentIdentity
from henchman.core.agent import Agent
from henchman.core.agent_interface import AgentInterface
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import ModelProvider
from henchman.tools.registry import ToolRegistry


class MockAgent:
    """A minimal implementation of AgentInterface for testing."""
    def __init__(self):
        self.provider = MagicMock(spec=ModelProvider)
        self.tool_registry = ToolRegistry()
        self.messages = []
        self.identity = AgentIdentity(
            role="test",
            id="test-id",
            name="Test Agent",
            description="A test agent"
        )
        self._errors = []

    async def run(self, user_input: str) -> AsyncIterator[AgentEvent]:
        yield AgentEvent(type=EventType.CONTENT, data="Hello")

    async def continue_with_tool_results(self) -> AsyncIterator[AgentEvent]:
        yield AgentEvent(type=EventType.FINISHED, data="Done")

    def record_delegation_errors(self, errors: list[str]) -> None:
        self._errors.extend(errors)

    def get_delegation_errors(self) -> list[str]:
        return self._errors

def test_mock_agent_satisfies_interface():
    """Verify that MockAgent satisfies AgentInterface."""
    mock_agent = MockAgent()
    assert isinstance(mock_agent, AgentInterface)

def test_real_agent_satisfies_interface(real_agent):
    """Verify that the real Agent satisfies AgentInterface."""
    assert isinstance(real_agent, AgentInterface)

@pytest.fixture
def real_agent():
    provider = MagicMock(spec=ModelProvider)
    return Agent(provider=provider)

@pytest.mark.asyncio
async def test_consumer_with_interface(mock_agent):
    """A dummy consumer that only knows about AgentInterface."""
    async def consumer(agent: AgentInterface):
        events = []
        async for event in agent.run("test"):
            events.append(event)
        return events

    events = await consumer(mock_agent)
    assert len(events) > 0
    assert events[0].type == EventType.CONTENT

@pytest.fixture
def mock_agent():
    return MockAgent()
