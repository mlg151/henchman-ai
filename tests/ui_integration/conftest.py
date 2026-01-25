"""
Test fixtures for UI integration tests.
"""
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, Mock

import pytest
from rich.console import Console

from henchman.cli.repl import Repl, ReplConfig
from henchman.core.agent import Agent
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import ModelProvider, ToolCall
from henchman.tools.registry import ToolRegistry


@pytest.fixture
def mock_provider() -> Mock:
    """Mock provider that returns deterministic responses."""
    provider = Mock(spec=ModelProvider)

    # Configure mock to return a tool call for read_file
    async def mock_chat_completion(*_, **__):
        # Return a mock response that triggers a tool call
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.tool_calls = [
            Mock(
                function=Mock(
                    name="read_file",
                    arguments='{"path": "/tmp/test.txt"}'
                )
            )
        ]
        return mock_response

    provider.chat_completion = AsyncMock(side_effect=mock_chat_completion)
    return provider


@pytest.fixture
def console_with_recording() -> Console:
    """Console instance that records output."""
    return Console(record=True, width=80)


@pytest.fixture
def repl_with_tools(mock_provider, console_with_recording) -> Repl:
    """REPL instance with all tools registered."""
    repl = Repl(
        provider=mock_provider,
        console=console_with_recording,
        config=ReplConfig()
    )
    return repl


@pytest.fixture
def mock_agent_with_tools() -> Mock:
    """Mock agent that can make tool calls."""
    agent = Mock(spec=Agent)

    # Configure agent to yield tool call events
    async def mock_run_agent(*_, **__):
        yield AgentEvent(
            type=EventType.TOOL_CALL_REQUEST,
            data=ToolCall(
                tool_name="read_file",
                arguments={"path": "/tmp/test.txt"}
            )
        )
        yield AgentEvent(type=EventType.FINISHED, data=None)

    agent.run = AsyncMock(side_effect=mock_run_agent)
    return agent


@pytest.fixture
async def running_repl(repl_with_tools, mock_agent_with_tools) -> AsyncGenerator[Repl, None]:
    """REPL instance with mock agent for testing."""
    # Replace the agent with our mock
    repl_with_tools.agent = mock_agent_with_tools

    # We don't actually run the REPL loop, just prepare it for testing
    yield repl_with_tools


@pytest.fixture
def sample_tool_registry() -> ToolRegistry:
    """Tool registry with all built-in tools registered."""
    registry = ToolRegistry()

    # Register mock tools
    mock_tool = Mock()
    mock_tool.name = "read_file"
    mock_tool.description = "Read contents of a file"
    mock_tool.execute = AsyncMock(return_value="File content: Hello World")

    registry.register(mock_tool)
    return registry
