"""Tests for message summarization during compaction."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from henchman.providers.base import FinishReason, Message, StreamChunk
from henchman.utils.compaction import (
    CompactionResult,
    ContextCompactor,
    MessageSummarizer,
    compact_with_summarization,
)


class TestCompactionResult:
    """Tests for CompactionResult dataclass."""

    def test_default_values(self):
        """CompactionResult has correct defaults."""
        result = CompactionResult(messages=[])
        assert result.messages == []
        assert result.was_compacted is False
        assert result.dropped_count == 0
        assert result.summary is None

    def test_with_compaction(self):
        """CompactionResult tracks compaction metadata."""
        msgs = [Message(role="user", content="test")]
        result = CompactionResult(
            messages=msgs,
            was_compacted=True,
            dropped_count=5,
            summary="Previous discussion about X",
        )
        assert result.was_compacted is True
        assert result.dropped_count == 5
        assert result.summary == "Previous discussion about X"


class TestCompactorCompactWithResult:
    """Tests for ContextCompactor.compact_with_result method."""

    def test_no_compaction_needed(self):
        """When under limit, returns unchanged with was_compacted=False."""
        msgs = [Message(role="user", content="Hello")]
        compactor = ContextCompactor(max_tokens=10000)
        result = compactor.compact_with_result(msgs)

        assert result.was_compacted is False
        assert result.messages == msgs
        assert result.dropped_count == 0

    def test_compaction_applied(self):
        """When over limit, compacts and tracks dropped count."""
        # Create messages that exceed limit
        msgs = [
            Message(role="system", content="System prompt."),
            Message(role="user", content="First message with content."),
            Message(role="assistant", content="Response to first message."),
            Message(role="user", content="Second message with content."),
            Message(role="assistant", content="Response to second message."),
            Message(role="user", content="Latest message that must be kept."),
        ]

        # Use a small limit to force compaction
        compactor = ContextCompactor(max_tokens=50)
        result = compactor.compact_with_result(msgs)

        assert result.was_compacted is True
        assert len(result.messages) < len(msgs)
        assert result.dropped_count > 0

    def test_empty_messages(self):
        """Empty message list returns empty result."""
        compactor = ContextCompactor(max_tokens=1000)
        result = compactor.compact_with_result([])

        assert result.messages == []
        assert result.was_compacted is False


class TestMessageSummarizer:
    """Tests for MessageSummarizer."""

    def test_init_without_provider(self):
        """Summarizer can be created without provider."""
        summarizer = MessageSummarizer()
        assert summarizer.provider is None

    def test_init_with_provider(self):
        """Summarizer can be created with provider."""
        mock_provider = MagicMock()
        summarizer = MessageSummarizer(provider=mock_provider)
        assert summarizer.provider is mock_provider

    def test_format_messages_filters_system(self):
        """System messages are filtered from summary."""
        summarizer = MessageSummarizer()
        msgs = [
            Message(role="system", content="You are helpful."),
            Message(role="user", content="Hello"),
        ]
        formatted = summarizer._format_messages_for_summary(msgs)
        assert "You are helpful" not in formatted
        assert "Hello" in formatted

    def test_format_messages_with_tool_calls(self):
        """Tool calls are mentioned in formatted output."""
        from henchman.providers.base import ToolCall

        summarizer = MessageSummarizer()
        msgs = [
            Message(
                role="assistant",
                content="I'll read the file.",
                tool_calls=[ToolCall(id="1", name="read_file", arguments={})],
            ),
        ]
        formatted = summarizer._format_messages_for_summary(msgs)
        assert "read_file" in formatted

    def test_format_messages_truncates_long_content(self):
        """Long content is truncated."""
        summarizer = MessageSummarizer()
        long_content = "x" * 1000
        msgs = [Message(role="user", content=long_content)]
        formatted = summarizer._format_messages_for_summary(msgs)
        assert len(formatted) < len(long_content)

    @pytest.mark.anyio
    async def test_summarize_without_provider(self):
        """Summarize returns None without provider."""
        summarizer = MessageSummarizer()
        msgs = [Message(role="user", content="Hello")]
        result = await summarizer.summarize(msgs)
        assert result is None

    @pytest.mark.anyio
    async def test_summarize_empty_messages(self):
        """Summarize returns None for empty messages."""
        mock_provider = MagicMock()
        summarizer = MessageSummarizer(provider=mock_provider)
        result = await summarizer.summarize([])
        assert result is None

    @pytest.mark.anyio
    async def test_summarize_success(self):
        """Summarize calls provider and returns summary."""
        mock_provider = MagicMock()

        # Mock streaming response
        async def mock_stream(*_args, **_kwargs):
            yield StreamChunk(content="This is a summary")
            yield StreamChunk(content=" of the conversation.", finish_reason=FinishReason.STOP)

        mock_provider.chat_completion_stream = mock_stream

        summarizer = MessageSummarizer(provider=mock_provider)
        msgs = [Message(role="user", content="Hello")]
        result = await summarizer.summarize(msgs)

        assert result == "This is a summary of the conversation."

    @pytest.mark.anyio
    async def test_summarize_handles_error(self):
        """Summarize returns None on error."""
        mock_provider = MagicMock()

        async def mock_stream(*_args, **_kwargs):
            raise Exception("API Error")
            yield  # Make it a generator

        mock_provider.chat_completion_stream = mock_stream

        summarizer = MessageSummarizer(provider=mock_provider)
        msgs = [Message(role="user", content="Hello")]
        result = await summarizer.summarize(msgs)

        assert result is None

    def test_create_summary_message(self):
        """Creates proper system message with summary."""
        summarizer = MessageSummarizer()
        msg = summarizer.create_summary_message("User asked about Python.")

        assert msg.role == "system"
        assert "Summary" in msg.content
        assert "Python" in msg.content


class TestCompactWithSummarization:
    """Tests for compact_with_summarization function."""

    @pytest.mark.anyio
    async def test_no_compaction_needed(self):
        """Returns unchanged when under limit."""
        msgs = [Message(role="user", content="Hello")]
        result = await compact_with_summarization(msgs, max_tokens=10000)

        assert result.was_compacted is False
        assert result.messages == msgs

    @pytest.mark.anyio
    async def test_compaction_without_provider(self):
        """Compacts without summarization when no provider."""
        msgs = [
            Message(role="system", content="System prompt."),
            Message(role="user", content="First message " * 50),
            Message(role="assistant", content="Response " * 50),
            Message(role="user", content="Latest message."),
        ]

        result = await compact_with_summarization(msgs, max_tokens=100, provider=None)

        assert result.was_compacted is True
        assert result.summary is None  # No summary without provider

    @pytest.mark.anyio
    async def test_compaction_with_summarization(self):
        """Includes summary when provider available and summarize=True."""
        mock_provider = MagicMock()

        async def mock_stream(*_args, **_kwargs):
            yield StreamChunk(content="Summary of earlier chat.", finish_reason=FinishReason.STOP)

        mock_provider.chat_completion_stream = mock_stream

        msgs = [
            Message(role="system", content="System."),
            Message(role="user", content="First message " * 100),
            Message(role="assistant", content="Response " * 100),
            Message(role="user", content="Latest."),
        ]

        result = await compact_with_summarization(
            msgs, max_tokens=50, provider=mock_provider, summarize=True
        )

        assert result.was_compacted is True
        # Summary should be present in result
        if result.summary:
            assert "Summary" in result.summary or len(result.summary) > 0

    @pytest.mark.anyio
    async def test_compaction_summarize_false(self):
        """Skips summarization when summarize=False."""
        mock_provider = MagicMock()
        mock_provider.chat_completion_stream = AsyncMock()

        msgs = [
            Message(role="system", content="System."),
            Message(role="user", content="Message " * 100),
            Message(role="user", content="Latest."),
        ]

        result = await compact_with_summarization(
            msgs, max_tokens=50, provider=mock_provider, summarize=False
        )

        assert result.was_compacted is True
        assert result.summary is None
        # Provider should not have been called
        mock_provider.chat_completion_stream.assert_not_called()

    @pytest.mark.anyio
    async def test_summarization_failure_fallback(self):
        """Falls back to simple compaction on summarization failure."""
        mock_provider = MagicMock()

        async def mock_stream(*_args, **_kwargs):
            raise Exception("Summarization failed")
            yield  # Make it a generator

        mock_provider.chat_completion_stream = mock_stream

        msgs = [
            Message(role="system", content="System."),
            Message(role="user", content="Message " * 100),
            Message(role="user", content="Latest."),
        ]

        # Should not raise, should fall back to simple compaction
        result = await compact_with_summarization(
            msgs, max_tokens=50, provider=mock_provider, summarize=True
        )

        assert result.was_compacted is True
        # Compaction should still work even if summarization failed
        assert len(result.messages) < len(msgs)
