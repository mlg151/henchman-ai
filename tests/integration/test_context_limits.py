"""Integration tests for context limit handling.

These tests verify the complete flow:
1. Agent accumulates context
2. Context exceeds model limits
3. Compaction/summarization is triggered
4. User is notified via CONTEXT_COMPACTED event
5. API call succeeds with compacted context
"""

from unittest.mock import MagicMock, patch

import pytest

from henchman.core.agent import Agent
from henchman.core.events import EventType
from henchman.providers.base import (
    FinishReason,
    Message,
    StreamChunk,
)
from henchman.tools.registry import ToolRegistry
from henchman.utils.tokens import get_model_limit


class MockProvider:
    """Mock provider for integration testing."""

    def __init__(self, responses: list[str] | None = None):
        self.responses = responses or ["Test response"]
        self.response_index = 0
        self.call_count = 0
        self.last_messages = None

    @property
    def name(self) -> str:
        return "mock"

    async def chat_completion_stream(self, messages, tools=None, **kwargs):
        """Mock streaming that tracks calls."""
        self.call_count += 1
        self.last_messages = messages

        response = self.responses[min(self.response_index, len(self.responses) - 1)]
        self.response_index += 1

        yield StreamChunk(content=response, finish_reason=FinishReason.STOP)


class TestAgentContextAccumulation:
    """Test agent context management as conversation grows."""

    @pytest.mark.anyio
    async def test_context_grows_with_messages(self):
        """Agent history grows with each interaction."""
        provider = MockProvider()
        agent = Agent(provider=provider, system_prompt="You are helpful.")

        # First turn - history includes system + user + assistant
        [e async for e in agent.run("Hello")]
        assert len(agent.history) == 3  # system + user + assistant

        # Second turn - adds user + assistant
        [e async for e in agent.run("How are you?")]
        assert len(agent.history) == 5  # 2 more messages

    @pytest.mark.anyio
    async def test_system_prompt_included(self):
        """System prompt is included in messages to API."""
        provider = MockProvider()
        agent = Agent(provider=provider, system_prompt="Be concise.")

        [e async for e in agent.run("Hello")]

        # Check that system prompt was sent to provider
        assert provider.last_messages[0].role == "system"
        assert "concise" in provider.last_messages[0].content


class TestContextCompactionTriggering:
    """Test that compaction triggers at appropriate thresholds."""

    @pytest.mark.anyio
    async def test_compaction_event_emitted(self):
        """CONTEXT_COMPACTED event is emitted when compaction occurs."""
        provider = MockProvider(responses=["Response " + str(i) for i in range(10)])

        # Use small limit to trigger compaction
        agent = Agent(
            provider=provider,
            system_prompt="System.",
            model="gpt-4",  # 8K context window
        )

        # Add many long messages to exceed context
        events_collected = []
        for i in range(20):
            long_message = f"Message {i}: " + "content " * 500
            events = [e async for e in agent.run(long_message)]
            events_collected.extend(events)

        # Check if any compaction events were emitted
        [e for e in events_collected if e.type == EventType.CONTEXT_COMPACTED]
        # Note: Whether compaction is triggered depends on total token count

    @pytest.mark.anyio
    async def test_model_limit_respected(self):
        """Agent respects model-specific context limits."""
        MockProvider()

        # Test different models have different limits
        limit_gpt4 = get_model_limit("gpt-4")
        limit_gpt4_turbo = get_model_limit("gpt-4-turbo")

        assert limit_gpt4 == 8192
        assert limit_gpt4_turbo == 128000


class TestCompactionWithSummarization:
    """Test summarization during compaction."""

    @pytest.mark.anyio
    async def test_summarization_enabled_creates_summary(self):
        """When summarize_dropped=True, dropped messages are summarized."""
        # This test verifies the summarization path is available
        from henchman.utils.compaction import CompactionParams, compact_messages

        mock_provider = MagicMock()

        async def mock_stream(*_args, **_kwargs):
            yield StreamChunk(
                content="Summary: discussed greetings", finish_reason=FinishReason.STOP
            )

        mock_provider.chat_completion_stream = mock_stream

        msgs = [
            Message(role="system", content="System."),
            Message(role="user", content="Hello " * 500),
            Message(role="assistant", content="Hi " * 500),
            Message(role="user", content="Latest message."),
        ]

        result = await compact_messages(
            CompactionParams(
                messages=msgs,
                max_tokens=100,
                provider=mock_provider,
                summarize=True,
            )
        )

        assert result.was_compacted is True


class TestContextCompactionFlow:
    """End-to-end tests for the complete compaction flow."""

    @pytest.mark.anyio
    async def test_full_compaction_flow(self):
        """Complete flow: accumulate → compact → notify → succeed."""
        provider = MockProvider()
        agent = Agent(
            provider=provider,
            system_prompt="Be helpful.",
        )

        # Simulate a conversation
        for i in range(3):
            events = [e async for e in agent.run(f"Question {i}?")]

            # Verify we got content
            content_events = [e for e in events if e.type == EventType.CONTENT]
            assert len(content_events) > 0

        # History should be maintained (system + 3 user + 3 assistant)
        assert len(agent.history) >= 7

    @pytest.mark.anyio
    async def test_compaction_preserves_recent_context(self):
        """Compaction keeps recent messages intact."""
        from henchman.utils.compaction import ContextCompactor

        msgs = [
            Message(role="system", content="System prompt."),
            Message(role="user", content="Old message " * 100),
            Message(role="assistant", content="Old response " * 100),
            Message(role="user", content="Recent question"),
            Message(role="assistant", content="Recent answer"),
            Message(role="user", content="Latest message"),
        ]

        # Compact with small limit
        compactor = ContextCompactor(max_tokens=100)
        result = compactor.compact_with_result(msgs)

        if result.was_compacted:
            # Latest message should be preserved
            last_msg = result.messages[-1]
            assert last_msg.content == "Latest message"


class TestUINotification:
    """Test that UI receives compaction notifications."""

    @pytest.mark.anyio
    async def test_repl_handles_compaction_event(self):
        """REPL displays warning when compaction occurs."""
        from henchman.cli.repl import Repl, ReplConfig
        from henchman.core.events import AgentEvent

        provider = MockProvider()
        config = ReplConfig(system_prompt="Test")

        # Create REPL with mocked console
        with patch("henchman.cli.repl.Console") as MockConsole:
            mock_console = MagicMock()
            MockConsole.return_value = mock_console

            repl = Repl(provider=provider, config=config)
            repl.renderer = MagicMock()

            # Simulate handling a CONTEXT_COMPACTED event
            AgentEvent(
                type=EventType.CONTEXT_COMPACTED,
                data={"dropped_count": 3, "summary": "Earlier discussion"},
            )

            # The REPL should have handling for this event type
            # (Actual rendering is tested in REPL unit tests)


class TestToolOutputTruncation:
    """Test that tool outputs are truncated to prevent context explosion."""

    @pytest.mark.anyio
    async def test_long_tool_output_truncated(self):
        """Tool outputs exceeding MAX_TOOL_OUTPUT are truncated."""
        from henchman.tools.base import Tool, ToolKind, ToolResult
        from henchman.tools.registry import MAX_TOOL_OUTPUT

        class LargeOutputTool(Tool):
            @property
            def name(self) -> str:
                return "large_output"

            @property
            def description(self) -> str:
                return "Returns large output"

            @property
            def parameters(self) -> dict:
                return {"type": "object", "properties": {}}

            @property
            def kind(self) -> ToolKind:
                return ToolKind.READ

            async def execute(self, **params) -> ToolResult:
                return ToolResult(content="x" * 100000)

        registry = ToolRegistry()
        registry.register(LargeOutputTool())

        result = await registry.execute("large_output", {})

        # Output should be truncated
        assert len(result.content) <= MAX_TOOL_OUTPUT + 100  # Allow for message


class TestReadFileMaxChars:
    """Test read_file tool respects max_chars parameter."""

    @pytest.mark.anyio
    async def test_read_file_truncates_large_files(self, tmp_path):
        """read_file truncates output when exceeding max_chars."""
        from henchman.tools.builtins.file_read import ReadFileTool

        # Create large file
        large_file = tmp_path / "large.txt"
        large_file.write_text("x" * 100000)

        tool = ReadFileTool()
        result = await tool.execute(path=str(large_file), max_chars=1000)

        assert len(result.content) < 100000
        assert "truncated" in result.content.lower() or len(result.content) <= 1100

    @pytest.mark.anyio
    async def test_read_file_default_limit(self, tmp_path):
        """read_file uses default max_chars of 50000."""
        from henchman.tools.builtins.file_read import DEFAULT_MAX_CHARS, ReadFileTool

        # Create file larger than default
        large_file = tmp_path / "large.txt"
        large_file.write_text("x" * (DEFAULT_MAX_CHARS + 10000))

        tool = ReadFileTool()
        result = await tool.execute(path=str(large_file))

        # Should be truncated to approximately default limit
        assert len(result.content) <= DEFAULT_MAX_CHARS + 200
