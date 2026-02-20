from unittest.mock import MagicMock

import pytest

from henchman.agents.identity import AgentIdentity
from henchman.core.agent import Agent
from henchman.providers.base import FinishReason, Message, ModelProvider, StreamChunk, ToolCall


@pytest.fixture
def mock_provider():
    provider = MagicMock(spec=ModelProvider)
    return provider


@pytest.fixture
def mock_stream_chunk():
    """Create a mock stream chunk."""
    return StreamChunk(content="Hello", finish_reason=FinishReason.STOP)


@pytest.fixture
def mock_async_generator(mock_stream_chunk):
    """Create an async generator for testing."""
    async def async_gen(*args: object, **kwargs: object) -> object:  # noqa: ARG001
        yield mock_stream_chunk
    return async_gen


@pytest.fixture
def agent_identity():
    return AgentIdentity(
        id="test-agent",
        name="Test Agent",
        role="tester",
        description="Testing agent",
    )


@pytest.fixture
def sample_tool_call():
    return ToolCall(
        id="test-tool-call-123",
        name="test_tool",
        arguments={"param": "value"}
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
    chunk = StreamChunk(content="Hello", finish_reason=FinishReason.STOP)

    async def async_gen(*_args, **_kwargs):  # noqa: ARG001
        yield chunk

    mock_provider.chat_completion_stream = async_gen

    events = []
    async for event in agent.run("Hi"):
        events.append(event)

    assert len(events) > 0
    for event in events:
        assert event.source_agent == "test-agent"


@pytest.mark.asyncio
async def test_agent_no_identity_emits_none_source_agent(mock_provider):
    agent = Agent(provider=mock_provider)

    chunk = StreamChunk(content="Hello", finish_reason=FinishReason.STOP)

    async def async_gen(*_args, **_kwargs):  # noqa: ARG001
        yield chunk

    mock_provider.chat_completion_stream = async_gen

    events = []
    async for event in agent.run("Hi"):
        events.append(event)

    assert len(events) > 0
    for event in events:
        assert event.source_agent is None


def test_agent_clear_history_keeps_system_prompt(mock_provider):
    """Test that clear_history() keeps system messages."""
    agent = Agent(provider=mock_provider, system_prompt="You are a helpful assistant")

    # Add some messages
    agent.messages.append(Message(role="user", content="Hello"))
    agent.messages.append(Message(role="assistant", content="Hi there"))

    assert len(agent.messages) == 3  # system + user + assistant

    agent.clear_history()

    # Should only have system message left
    assert len(agent.messages) == 1
    assert agent.messages[0].role == "system"
    assert agent.messages[0].content == "You are a helpful assistant"


def test_agent_clear_history_no_system_prompt(mock_provider):
    """Test that clear_history() works with no system prompt."""
    agent = Agent(provider=mock_provider)  # No system prompt

    # Add some messages
    agent.messages.append(Message(role="user", content="Hello"))
    agent.messages.append(Message(role="assistant", content="Hi there"))

    assert len(agent.messages) == 2

    agent.clear_history()

    # Should have no messages
    assert len(agent.messages) == 0


def test_agent_submit_tool_result(mock_provider):
    """Test submitting tool results."""
    agent = Agent(provider=mock_provider)

    initial_count = len(agent.messages)
    agent.submit_tool_result("test-tool-call-123", "Tool result data")

    assert len(agent.messages) == initial_count + 1
    assert agent.messages[-1].role == "tool"
    assert agent.messages[-1].content == "Tool result data"
    assert agent.messages[-1].tool_call_id == "test-tool-call-123"


def test_agent_get_messages_for_api(mock_provider):
    """Test getting messages for API with compaction."""
    agent = Agent(provider=mock_provider, max_tokens=100)

    # Add some messages
    for i in range(5):
        agent.messages.append(Message(role="user", content=f"Message {i}"))
        agent.messages.append(Message(role="assistant", content=f"Response {i}"))

    api_messages = agent.get_messages_for_api()

    # Should return messages (compaction may or may not happen based on token count)
    assert isinstance(api_messages, list)
    assert all(isinstance(msg, Message) for msg in api_messages)


def test_agent_stall_detection_skip_short_response(mock_provider):
    """Test that short responses skip stall detection."""
    agent = Agent(provider=mock_provider)

    # Short response should skip
    assert agent._should_skip_stall_check("Hi", False) is True

    # Longer response should not skip
    long_response = "This is a longer response that should be checked for stalling."
    assert agent._should_skip_stall_check(long_response, False) is False


def test_agent_stall_detection_skip_with_tool_calls(mock_provider):
    """Test that responses with tool calls skip stall detection."""
    agent = Agent(provider=mock_provider)

    # With tool calls should skip
    assert agent._should_skip_stall_check("Any response", True) is True

    # Should reset stall count
    agent._stall_nudge_count = 3
    agent._should_skip_stall_check("Any response", True)
    assert agent._stall_nudge_count == 0


def test_agent_stall_detection_disabled(mock_provider):
    """Test stall detection when disabled."""
    agent = Agent(provider=mock_provider)
    agent.stall_detection_enabled = False

    assert agent._should_skip_stall_check("Any response", False) is True


def test_agent_detect_stalling_patterns_colon_ending(mock_provider):
    """Test detection of stalling pattern: ending with colon."""
    agent = Agent(provider=mock_provider)

    # Ends with colon - should detect stalling (regardless of length)
    assert agent._detect_stalling_patterns("Let me create a file:") is True
    assert agent._detect_stalling_patterns("I will now write the code:") is True

    # "Let me create a file" contains "let me " and is short (< 120 chars) - should detect
    assert agent._detect_stalling_patterns("Let me create a file") is True

    # Long response without colon and without stall phrase - should not detect
    long_response = "This is a very long response that does not contain any stall phrases and goes on for quite a while to exceed the maximum length threshold for intent phrase detection."
    assert len(long_response.strip()) > agent.MAX_RESPONSE_LENGTH_FOR_INTENT_PHRASE
    assert agent._detect_stalling_patterns(long_response) is False


def test_agent_detect_stalling_patterns_intent_phrases(mock_provider):
    """Test detection of stalling pattern: intent phrases."""
    agent = Agent(provider=mock_provider)

    # Intent phrases should trigger stalling
    assert agent._detect_stalling_patterns("Let me start by creating the file") is True
    assert agent._detect_stalling_patterns("I'll write the code now") is True
    assert agent._detect_stalling_patterns("First, I will implement the feature") is True

    # Questions with "should I" should not trigger
    assert agent._detect_stalling_patterns("Should I create the file?") is False

    # Regular responses should not trigger
    assert agent._detect_stalling_patterns("The file has been created") is False
    assert agent._detect_stalling_patterns("I created the file as requested") is False


@pytest.mark.asyncio
async def test_agent_check_for_stalling_no_stall(mock_provider):
    """Test stall check when no stalling is detected."""
    agent = Agent(provider=mock_provider)

    # Normal response with tool calls
    result = await agent._check_for_stalling("Created the file", True)
    assert result is None
    assert agent._stall_nudge_count == 0

    # Normal response without tool calls but not stalling
    result = await agent._check_for_stalling("The file has been created successfully", False)
    assert result is None


@pytest.mark.asyncio
async def test_agent_check_for_stalling_with_nudge(mock_provider):
    """Test stall check when stalling is detected."""
    agent = Agent(provider=mock_provider)

    # Stalling response
    stalling_response = "Let me start by creating the file:"
    result = await agent._check_for_stalling(stalling_response, False)

    assert result == agent.STALL_NUDGE_MESSAGE
    assert agent._stall_nudge_count == 1


@pytest.mark.asyncio
async def test_agent_check_for_stalling_max_nudges(mock_provider):
    """Test stall check when max nudges reached."""
    agent = Agent(provider=mock_provider)
    agent._stall_nudge_count = agent.MAX_STALL_NUDGES

    # Stalling response at max nudges
    stalling_response = "Let me start by creating the file:"
    result = await agent._check_for_stalling(stalling_response, False)

    assert result is None  # Should stop nudging
    assert agent._stall_failure is True  # Should set failure flag


@pytest.mark.asyncio
async def test_agent_run_with_stalling_nudge(mock_provider):
    """Test run() method with stalling detection and nudge."""
    agent = Agent(provider=mock_provider)

    # Mock provider to return a stalling response
    chunk = StreamChunk(
        content="Let me start by creating the file:",
        finish_reason=FinishReason.STOP
    )

    async def async_gen(*_args, **_kwargs):
        yield chunk

    mock_provider.chat_completion_stream = async_gen

    events = []
    async for event in agent.run("Create a file"):
        events.append(event)

    # Should have events (even with stalling)
    assert len(events) > 0
    # The stalling response should trigger stall detection
    # Note: We can't easily test the loop behavior with simple mocks


@pytest.mark.asyncio
async def test_agent_continue_with_tool_results(mock_provider, sample_tool_call):
    """Test continue_with_tool_results() method."""
    agent = Agent(provider=mock_provider)

    # Create a proper conversation history with assistant tool call
    agent.messages.append(Message(
        role="assistant",
        content="",
        tool_calls=[sample_tool_call]
    ))

    # Add a tool result to continue from
    agent.submit_tool_result(sample_tool_call.id, "Tool executed successfully")

    # Mock provider response
    chunk = StreamChunk(
        content="Thanks for the tool result",
        finish_reason=FinishReason.STOP
    )

    async def async_gen(*_args, **_kwargs):
        yield chunk

    mock_provider.chat_completion_stream = async_gen

    events = []
    async for event in agent.continue_with_tool_results():
        events.append(event)

    assert len(events) > 0
    # Should have content event
    from henchman.core.events import EventType
    assert any(event.type == EventType.CONTENT for event in events)


def test_agent_constants():
    """Test that constants are properly defined."""
    assert Agent.DEFAULT_MAX_TOKENS == 8000
    assert Agent.DEFAULT_TOKEN_RATIO == 0.85
    assert Agent.MAX_STALL_NUDGES == 2
    assert Agent.MIN_RESPONSE_LENGTH_FOR_STALL_CHECK == 20
    assert Agent.MAX_RESPONSE_LENGTH_FOR_INTENT_PHRASE == 120
    assert len(Agent.STALL_PHRASES) > 0
    assert "let me start by" in Agent.STALL_PHRASES
    assert "i'll create" in Agent.STALL_PHRASES


def test_agent_properties(mock_provider):
    """Test agent properties."""
    agent = Agent(provider=mock_provider)

    # history property
    assert agent.history == agent.messages

    # tools property
    assert agent.tools == agent.tool_registry


@pytest.mark.asyncio
async def test_agent_emit_with_identity(mock_provider, agent_identity):
    """Test _emit() method with identity."""
    from henchman.core.events import EventType

    agent = Agent(provider=mock_provider, identity=agent_identity)

    # Use a valid EventType for testing
    event = agent._emit(type=EventType.CONTENT, data={"key": "value"})

    assert event.type == EventType.CONTENT
    assert event.data == {"key": "value"}
    assert event.source_agent == "test-agent"


@pytest.mark.asyncio
async def test_agent_emit_without_identity(mock_provider):
    """Test _emit() method without identity."""
    from henchman.core.events import EventType

    agent = Agent(provider=mock_provider)

    # Use a valid EventType for testing
    event = agent._emit(type=EventType.CONTENT, data={"key": "value"})

    assert event.type == EventType.CONTENT
    assert event.data == {"key": "value"}
    assert event.source_agent is None
