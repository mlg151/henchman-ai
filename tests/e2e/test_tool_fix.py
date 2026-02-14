"""End-to-end test for the tool system fix."""

import asyncio
import tempfile
from pathlib import Path

import pytest
from rich.console import Console

from henchman.cli.repl import Repl, ReplConfig
from henchman.core.events import EventType
from henchman.providers.base import FinishReason, ModelProvider, StreamChunk, ToolCall


class E2EProvider(ModelProvider):
    """Provider for end-to-end testing."""

    def __init__(self):
        self.call_count = 0
        self.responses = [
            # First response: use ls tool
            {
                "tool_calls": [ToolCall(id="call_1", name="ls", arguments={"path": "."})],
                "content": "",
                "finish_reason": FinishReason.TOOL_CALLS,
            },
            # Second response: continue after tool result
            {
                "content": "Here are the files in the current directory.",
                "finish_reason": FinishReason.STOP,
            },
        ]

    @property
    def name(self) -> str:
        return "e2e"

    async def chat_completion_stream(self, messages, tools=None, **kwargs):
        self.call_count += 1
        response = self.responses[min(self.call_count - 1, len(self.responses) - 1)]

        yield StreamChunk(
            content=response.get("content", ""),
            tool_calls=response.get("tool_calls"),
            finish_reason=response["finish_reason"],
        )


@pytest.mark.asyncio
async def test_e2e_tool_execution():
    """End-to-end test of tool execution."""
    console = Console()
    provider = E2EProvider()
    config = ReplConfig()

    repl = Repl(provider=provider, console=console, config=config)
    repl.config.auto_approve_tools = True

    # Verify tools are registered
    assert len(repl.tool_registry.list_tools()) > 0
    assert len(repl.agent.tools) > 0

    # Run agent
    events = []
    tool_results = []

    async for event in repl.agent.run("List files in current directory"):
        events.append(event.type)

        if event.type == EventType.TOOL_CALL_REQUEST:
            # Execute the tool
            result = await repl.tool_registry.execute(event.data.name, event.data.arguments)
            tool_results.append(result)

            # Submit result to agent
            repl.agent.submit_tool_result(event.data.id, result.content)

    # Verify tool call was requested and executed
    assert EventType.TOOL_CALL_REQUEST in events
    assert len(tool_results) == 1
    assert tool_results[0].success is True

    # Continue after tool result - this triggers the second response
    continuation_events = []
    async for event in repl.agent.continue_with_tool_results():
        continuation_events.append(event.type)

    # Total events from full flow should be 2+ (tool request + content)
    all_events = events + continuation_events
    assert len(all_events) >= 2


@pytest.mark.asyncio
async def test_shell_tool_execution():
    """Test shell tool execution."""
    console = Console()

    # Create a provider that requests shell command
    class ShellProvider(ModelProvider):
        async def chat_completion_stream(self, messages, tools=None, **kwargs):
            yield StreamChunk(
                content="",
                tool_calls=[
                    ToolCall(
                        id="shell_1", name="shell", arguments={"command": "echo 'test output'"}
                    )
                ],
                finish_reason=FinishReason.TOOL_CALLS,
            )

        @property
        def name(self) -> str:
            return "shell_test"

    provider = ShellProvider()
    config = ReplConfig(auto_approve_tools=True)

    repl = Repl(provider=provider, console=console, config=config)

    # Run agent
    events = []
    async for event in repl.agent.run("Run echo command"):
        events.append(event.type)

        if event.type == EventType.TOOL_CALL_REQUEST:
            # Execute shell tool
            result = await repl.tool_registry.execute(event.data.name, event.data.arguments)
            assert result.success is True
            assert "test output" in result.content.lower()

            # Submit result
            repl.agent.submit_tool_result(event.data.id, result.content)

    assert EventType.TOOL_CALL_REQUEST in events


@pytest.mark.asyncio
async def test_file_read_tool():
    """Test file read tool."""
    console = Console()

    # Create a test file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Line 1\nLine 2\nLine 3\n")
        test_file = f.name

    try:
        # Create a provider that requests file read
        class FileReadProvider(ModelProvider):
            async def chat_completion_stream(self, messages, tools=None, **kwargs):
                yield StreamChunk(
                    content="",
                    tool_calls=[
                        ToolCall(id="read_1", name="read_file", arguments={"path": test_file})
                    ],
                    finish_reason=FinishReason.TOOL_CALLS,
                )

            @property
            def name(self) -> str:
                return "file_read_test"

        provider = FileReadProvider()
        config = ReplConfig()

        repl = Repl(provider=provider, console=console, config=config)
        repl.config.auto_approve_tools = True

        # Run agent
        events = []
        async for event in repl.agent.run(f"Read file {test_file}"):
            events.append(event.type)

            if event.type == EventType.TOOL_CALL_REQUEST:
                # Execute read file tool
                result = await repl.tool_registry.execute(event.data.name, event.data.arguments)
                assert result.success is True
                assert "Line 1" in result.content
                assert "Line 2" in result.content
                assert "Line 3" in result.content

                # Submit result
                repl.agent.submit_tool_result(event.data.id, result.content)

        assert EventType.TOOL_CALL_REQUEST in events
    finally:
        # Clean up
        Path(test_file).unlink()


def test_all_builtin_tools_registered():
    """Test that all built-in tools are registered by default."""
    console = Console()

    class TestProvider(ModelProvider):
        @property
        def name(self) -> str:
            return "test"

        async def chat_completion_stream(self, messages, tools=None, **kwargs):
            yield StreamChunk(content="test", finish_reason=FinishReason.STOP)

    provider = TestProvider()
    config = ReplConfig()

    repl = Repl(provider=provider, console=console, config=config)
    repl.config.auto_approve_tools = True

    # Check that all expected tools are registered
    expected_tools = [
        "ask_user",
        "edit_file",
        "glob",
        "grep",
        "ls",
        "read_file",
        "shell",
        "web_fetch",
        "write_file",
    ]

    registered_tools = repl.tool_registry.list_tools()

    for tool in expected_tools:
        assert tool in registered_tools, f"Tool {tool} not registered"

    # Agent (Tech Lead) has base tools plus delegate_task
    agent_tools = repl.agent.tools.list_tools()
    for tool in expected_tools:
        assert tool in agent_tools, f"Tool {tool} not in agent tools"
    assert "delegate_task" in agent_tools, "delegate_task not in agent tools"


if __name__ == "__main__":
    # Run tests

    asyncio.run(test_e2e_tool_execution())
    print("✓ test_e2e_tool_execution")

    asyncio.run(test_shell_tool_execution())
    print("✓ test_shell_tool_execution")

    asyncio.run(test_file_read_tool())
    print("✓ test_file_read_tool")

    test_all_builtin_tools_registered()
    print("✓ test_all_builtin_tools_registered")

    print("\nAll end-to-end tests passed!")
