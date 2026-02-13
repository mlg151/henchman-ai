from unittest.mock import MagicMock

import pytest

from henchman.agents.identity import AgentIdentity
from henchman.core.agent import Agent
from henchman.providers.base import FinishReason, ModelProvider, StreamChunk


@pytest.fixture
def mock_provider():
    provider = MagicMock(spec=ModelProvider)
    return provider


@pytest.fixture
def agent_identity():
    return AgentIdentity(
        id="test-agent",
        name="Test Agent",
        role="tester",
        description="Testing agent",
    )


@pytest.mark.asyncio
async def test_agent_emits_source_agent(mock_provider, agent_identity):
    agent = Agent(provider=mock_provider, identity=agent_identity)

    # Mock provider to return a simple chunk
    chunk = StreamChunk(
        content="Hello",
        finish_reason=FinishReason.STOP
    )

    async def async_gen(*_args, **_kwargs):  # noqa: ARG001
        yield chunk

    mock_provider.chat_completion_stream.return_value = async_gen()

    events = []
    async for event in agent.run("Hi"):
        events.append(event)

    assert len(events) > 0
    for event in events:
        assert event.source_agent == "test-agent"


@pytest.mark.asyncio
async def test_agent_no_identity_emits_none_source_agent(mock_provider):
    agent = Agent(provider=mock_provider)

    chunk = StreamChunk(
        content="Hello",
        finish_reason=FinishReason.STOP
    )

    async def async_gen(*_args, **_kwargs):  # noqa: ARG001
        yield chunk

    mock_provider.chat_completion_stream.return_value = async_gen()

    events = []
    async for event in agent.run("Hi"):
        events.append(event)

    assert len(events) > 0
    for event in events:
        assert event.source_agent is None
