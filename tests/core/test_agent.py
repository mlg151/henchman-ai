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


def test_agent_auto_detects_model_from_provider():
    """Agent picks up default_model from provider for context sizing."""
    provider = MagicMock(spec=ModelProvider)
    provider.default_model = "deepseek-chat"
    agent = Agent(provider=provider)
    assert agent.model == "deepseek-chat"
    # 85% of 128000 = 108800
    assert agent.max_tokens == int(128000 * 0.85)


def test_agent_explicit_model_overrides_provider():
    """Explicit model param takes precedence over provider.default_model."""
    provider = MagicMock(spec=ModelProvider)
    provider.default_model = "deepseek-chat"
    agent = Agent(provider=provider, model="gpt-4")
    assert agent.model == "gpt-4"
    # 85% of 8192
    assert agent.max_tokens == int(8192 * 0.85)


def test_agent_explicit_max_tokens_overrides_all():
    """Explicit max_tokens overrides model-based calculation."""
    provider = MagicMock(spec=ModelProvider)
    provider.default_model = "deepseek-chat"
    agent = Agent(provider=provider, max_tokens=50000)
    assert agent.max_tokens == 50000


def test_agent_no_model_no_provider_model_uses_default():
    """Falls back to 8000 when no model info available."""
    provider = MagicMock(spec=ModelProvider)
    # MagicMock spec=ModelProvider won't have default_model
    del provider.default_model
    agent = Agent(provider=provider)
    assert agent.max_tokens == 8000


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
