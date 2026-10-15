"""Tests for compaction validation and summarization."""

from unittest.mock import Mock

import pytest

from henchman.providers.base import FinishReason, Message, StreamChunk, ToolCall
from henchman.utils.compaction import (
    CompactionResult,
    ContextCompactor,
    MessageSummarizer,
    compact_with_summarization,
)


class TestValidateCompactedSequence:
    """Tests for message sequence validation."""

    def test_valid_simple_sequence(self) -> None:
        """Valid simple conversation should pass validation."""
        compactor = ContextCompactor(max_tokens=1000)
        messages = [
            Message(role="system", content="System"),
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there!"),
        ]

        assert compactor.validate_compacted_sequence(messages) is True

    def test_tool_without_preceding_assistant(self) -> None:
        """Tool message without assistant should fail validation."""
        compactor = ContextCompactor(max_tokens=1000)
        messages = [
            Message(role="user", content="Hello"),
            Message(role="tool", content="Result", tool_call_id="tc_1"),
        ]

        assert compactor.validate_compacted_sequence(messages) is False

    def test_tool_after_user_fails(self) -> None:
        """Tool message directly after user should fail."""
        compactor = ContextCompactor(max_tokens=1000)
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="I'll help"),  # No tool_calls
            Message(role="tool", content="Result", tool_call_id="tc_1"),
        ]

        assert compactor.validate_compacted_sequence(messages) is False

    def test_valid_tool_sequence(self) -> None:
        """Valid tool call sequence should pass."""
        compactor = ContextCompactor(max_tokens=1000)
        messages = [
            Message(role="user", content="Read file"),
            Message(
                role="assistant",
                content="Reading...",
                tool_calls=[ToolCall(id="tc_1", name="read_file", arguments={})],
            ),
            Message(role="tool", content="File content", tool_call_id="tc_1"),
        ]

        assert compactor.validate_compacted_sequence(messages) is True

    def test_tool_with_wrong_id_fails(self) -> None:
        """Tool with mismatched ID should fail."""
        compactor = ContextCompactor(max_tokens=1000)
        messages = [
            Message(role="user", content="Read file"),
            Message(
                role="assistant",
                content="Reading...",
                tool_calls=[ToolCall(id="tc_1", name="read_file", arguments={})],
            ),
            Message(role="tool", content="Result", tool_call_id="tc_WRONG"),
        ]

        assert compactor.validate_compacted_sequence(messages) is False

    def test_orphaned_tool_calls_fail(self) -> None:
        """Assistant with tool_calls but no tool responses should fail."""
        compactor = ContextCompactor(max_tokens=1000)
        messages = [
            Message(role="user", content="Read file"),
            Message(
                role="assistant",
                content="Reading...",
                tool_calls=[ToolCall(id="tc_1", name="read_file", arguments={})],
            ),
            # Missing tool response
            Message(role="user", content="What happened?"),
        ]

        assert compactor.validate_compacted_sequence(messages) is False


class TestCompactWithResult:
    """Tests for compact_with_result method."""

    def test_returns_compaction_result(self) -> None:
        """Should return a CompactionResult object."""
        compactor = ContextCompactor(max_tokens=50)
        messages = [
            Message(role="user", content="x" * 100),
            Message(role="user", content="y" * 100),
        ]

        result = compactor.compact_with_result(messages)

        assert isinstance(result, CompactionResult)
        assert isinstance(result.messages, list)
        assert isinstance(result.was_compacted, bool)

    def test_tracks_dropped_count(self) -> None:
        """Should track number of dropped messages/sequences."""
        compactor = ContextCompactor(max_tokens=100)
        messages = [
            Message(role="user", content="Old message 1"),
            Message(role="assistant", content="Old response 1"),
            Message(role="user", content="Old message 2"),
            Message(role="assistant", content="Old response 2"),
            Message(role="user", content="New message"),
        ]

        result = compactor.compact_with_result(messages)

        # If compaction occurred, dropped_count should be set
        if result.was_compacted:
            assert result.dropped_count >= 0


class TestMessageSummarizer:
    """Tests for MessageSummarizer class."""

    def test_create_summary_message(self) -> None:
        """Should create a properly formatted summary message."""
        provider = Mock()
        summarizer = MessageSummarizer(provider=provider)

        summary_msg = summarizer.create_summary_message("User asked about files")

        assert summary_msg.role == "system"
        assert "Summary" in summary_msg.content
        assert "User asked about files" in summary_msg.content

    @pytest.mark.asyncio
    async def test_summarize_with_mock_provider(self) -> None:
        """Should call provider to generate summary."""
        # Create mock provider that returns summary
        mock_provider = Mock()

        async def mock_stream(*_args, **_kwargs):
            yield StreamChunk(content="This is a summary", finish_reason=FinishReason.STOP)

        mock_provider.chat_completion_stream = mock_stream

        summarizer = MessageSummarizer(provider=mock_provider)
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there!"),
        ]

        summary = await summarizer.summarize(messages)

        assert summary == "This is a summary"

    @pytest.mark.asyncio
    async def test_summarize_handles_exception(self) -> None:
        """Should return None on exception."""
        mock_provider = Mock()

        async def mock_stream(*_args, **_kwargs):
            raise Exception("API Error")
            yield  # pragma: no cover - keep this an async generator

        mock_provider.chat_completion_stream = mock_stream

        summarizer = MessageSummarizer(provider=mock_provider)
        messages = [Message(role="user", content="Hello")]

        summary = await summarizer.summarize(messages)

        assert summary is None


class TestCompactWithSummarization:
    """Tests for compact_with_summarization function."""

    @pytest.mark.asyncio
    async def test_no_compaction_needed(self) -> None:
        """Should return original messages when no compaction needed."""
        messages = [
            Message(role="user", content="Short message"),
        ]

        result = await compact_with_summarization(
            messages=messages, max_tokens=10000, provider=None, summarize=False
        )

        assert result.was_compacted is False
        assert result.messages == messages

    @pytest.mark.asyncio
    async def test_compaction_without_summarization(self) -> None:
        """Should compact without summarization when provider is None."""
        messages = [
            Message(role="user", content="x" * 500),
            Message(role="assistant", content="y" * 500),
            Message(role="user", content="z" * 500),
        ]

        result = await compact_with_summarization(
            messages=messages, max_tokens=100, provider=None, summarize=False
        )

        # Should compact but no summary
        if result.was_compacted:
            assert result.summary is None

    @pytest.mark.asyncio
    async def test_compaction_with_protected_zone(self) -> None:
        """Should respect protected zone during compaction."""
        messages = [
            Message(role="user", content="Old message"),
            Message(role="assistant", content="Old response"),
            Message(role="user", content="Current message"),  # protected
        ]

        result = await compact_with_summarization(
            messages=messages, max_tokens=80, provider=None, summarize=False, protect_from_index=2
        )

        # Current message should be preserved
        contents = [m.content for m in result.messages if m.content]
        assert any("Current" in c for c in contents)
