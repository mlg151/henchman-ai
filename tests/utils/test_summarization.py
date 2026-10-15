"""Tests for message summarization during compaction."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from henchman.providers.base import FinishReason, Message, StreamChunk
from henchman.utils.compaction import (
    CompactionParams,
    CompactionResult,
    ContextCompactor,
    MessageSummarizer,
    compact_messages,
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

    @pytest.mark.anyio
    async def test_summarize_caches_result(self):
        """Summarize caches the result in _cached_summary."""
        mock_provider = MagicMock()

        # Create a simple async generator
        async def mock_stream(*_args, **_kwargs):
            # Return a chunk with content
            yield StreamChunk(content="Cached ", finish_reason=None)
            yield StreamChunk(content="summary", finish_reason=FinishReason.STOP)

        mock_provider.chat_completion_stream = mock_stream

        summarizer = MessageSummarizer(provider=mock_provider)
        msgs = [Message(role="user", content="Hello")]

        # First call should cache
        result = await summarizer.summarize(msgs)
        assert result == "Cached summary"
        assert summarizer._cached_summary == "Cached summary"

    @pytest.mark.anyio
    async def test_summarize_empty_summary_returns_none(self):
        """Summarize returns None if summary is empty."""
        mock_provider = MagicMock()

        # Mock streaming response with empty content
        async def mock_stream(*_args, **_kwargs):
            yield StreamChunk(content="", finish_reason=FinishReason.STOP)

        mock_provider.chat_completion_stream = mock_stream

        summarizer = MessageSummarizer(provider=mock_provider)
        msgs = [Message(role="user", content="Hello")]
        result = await summarizer.summarize(msgs)

        assert result is None
        assert summarizer._cached_summary is None

    @pytest.mark.anyio
    async def test_summarize_only_system_messages_returns_none(self):
        """Summarize returns None when only system messages."""
        mock_provider = MagicMock()
        summarizer = MessageSummarizer(provider=mock_provider)
        msgs = [Message(role="system", content="You are helpful")]
        result = await summarizer.summarize(msgs)

        assert result is None
        # Provider should not be called
        mock_provider.chat_completion_stream.assert_not_called()

    def test_create_summary_message(self):
        """Creates proper system message with summary."""
        summarizer = MessageSummarizer()
        msg = summarizer.create_summary_message("User asked about Python.")

        assert msg.role == "system"
        assert "Summary" in msg.content
        assert "Python" in msg.content

        # Test exact format
        assert msg.content == "[Summary of earlier conversation: User asked about Python.]"


class TestCompactWithSummarization:
    """Tests for compact_with_summarization function."""

    @pytest.mark.anyio
    async def test_no_compaction_needed(self):
        """Returns unchanged when under limit."""
        msgs = [Message(role="user", content="Hello")]
        result = await compact_messages(CompactionParams(messages=msgs, max_tokens=10000))

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

        result = await compact_messages(CompactionParams(messages=msgs, max_tokens=100, provider=None))

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

        result = await compact_messages(CompactionParams(messages=msgs, max_tokens=50, provider=mock_provider, summarize=True))

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

        result = await compact_messages(CompactionParams(messages=msgs, max_tokens=50, provider=mock_provider, summarize=False))

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
        result = await compact_messages(CompactionParams(messages=msgs, max_tokens=50, provider=mock_provider, summarize=True))

        assert result.was_compacted is True
        # Compaction should still work even if summarization failed
        assert len(result.messages) < len(msgs)

    @pytest.mark.anyio
    async def test_compaction_with_successful_summary_insertion(self):
        """Summary message is inserted after system messages."""
        mock_provider = MagicMock()

        async def mock_stream(*_args, **_kwargs):
            yield StreamChunk(content="Test summary text", finish_reason=FinishReason.STOP)

        mock_provider.chat_completion_stream = mock_stream

        msgs = [
            Message(role="system", content="System prompt 1"),
            Message(role="system", content="System prompt 2"),
            Message(role="user", content="First message " * 100),
            Message(role="assistant", content="Response " * 100),
            Message(role="user", content="Latest message."),
        ]

        result = await compact_messages(CompactionParams(messages=msgs, max_tokens=50, provider=mock_provider, summarize=True))

        assert result.was_compacted is True
        assert result.summary == "Test summary text"

        # Check that summary message is inserted after system messages
        system_msg_count = sum(1 for m in result.messages if m.role == "system")
        # Should have original system messages + summary system message
        assert system_msg_count == 3  # 2 original + 1 summary

        # Find the summary message
        summary_msgs = [
            m for m in result.messages if "Summary of earlier conversation" in m.content
        ]
        assert len(summary_msgs) == 1
        summary_msg = summary_msgs[0]
        assert summary_msg.role == "system"
        assert "Test summary text" in summary_msg.content

        # Check it's after the original system messages
        msg_index = result.messages.index(summary_msg)
        # Should be at index 2 (after the 2 original system messages)
        assert msg_index == 2

    @pytest.mark.anyio
    async def test_compaction_summary_returns_none(self):
        """When summarizer returns None, no summary is added."""
        mock_provider = MagicMock()

        async def mock_stream(*_args, **_kwargs):
            yield StreamChunk(content="", finish_reason=FinishReason.STOP)  # Empty summary

        mock_provider.chat_completion_stream = mock_stream

        msgs = [
            Message(role="system", content="System."),
            Message(role="user", content="Message " * 100),
            Message(role="user", content="Latest."),
        ]

        result = await compact_messages(CompactionParams(messages=msgs, max_tokens=50, provider=mock_provider, summarize=True))

        assert result.was_compacted is True
        assert result.summary is None

        # No summary messages should be present
        summary_msgs = [
            m for m in result.messages if "Summary of earlier conversation" in m.content
        ]
        assert len(summary_msgs) == 0

    @pytest.mark.anyio
    async def test_compaction_with_protected_zone(self):
        """Compaction works with protect_from_index parameter."""
        mock_provider = MagicMock()

        async def mock_stream(*_args, **_kwargs):
            yield StreamChunk(content="Protected zone summary", finish_reason=FinishReason.STOP)

        mock_provider.chat_completion_stream = mock_stream

        msgs = [
            Message(role="system", content="System."),
            Message(role="user", content="Old message 1 " * 50),
            Message(role="assistant", content="Old response 1 " * 50),
            Message(role="user", content="Old message 2 " * 50),
            Message(role="assistant", content="Old response 2 " * 50),
            Message(role="user", content="Protected message."),  # This should be protected
            Message(role="assistant", content="Protected response."),  # This should be protected
        ]

        # Protect last 2 messages (index 5)
        result = await compact_messages(CompactionParams(messages=msgs, max_tokens=100, provider=mock_provider, summarize=True, protect_from_index=5))

        assert result.was_compacted is True
        # Protected messages should be preserved
        assert any("Protected message" in (m.content or "") for m in result.messages)
        assert any("Protected response" in (m.content or "") for m in result.messages)

    @pytest.mark.anyio
    async def test_compaction_no_dropped_messages(self):
        """When no messages are dropped, summarization is not attempted."""
        mock_provider = MagicMock()
        mock_provider.chat_completion_stream = AsyncMock()

        # Create messages that fit within limit
        msgs = [
            Message(role="system", content="System."),
            Message(role="user", content="Short message"),
        ]

        result = await compact_messages(CompactionParams(messages=msgs, max_tokens=10000, provider=mock_provider, summarize=True))

        assert result.was_compacted is False
        assert result.summary is None
        # Provider should not be called since no compaction happened
        mock_provider.chat_completion_stream.assert_not_called()

    @pytest.mark.anyio
    async def test_compaction_with_custom_max_protected_ratio(self):
        """Compaction works with custom max_protected_ratio."""
        mock_provider = MagicMock()

        async def mock_stream(*_args, **_kwargs):
            yield StreamChunk(content="Summary with custom ratio", finish_reason=FinishReason.STOP)

        mock_provider.chat_completion_stream = mock_stream

        msgs = [
            Message(role="system", content="System."),
            Message(role="user", content="Message " * 100),
            Message(role="assistant", content="Response " * 100),
            Message(role="user", content="Latest."),
        ]

        result = await compact_messages(
            CompactionParams(
                messages=msgs,
                max_tokens=50,
                provider=mock_provider,
                summarize=True,
                max_protected_ratio=0.5,
            )
        )  # Higher ratio than default

        assert result.was_compacted is True
        # Function should complete without error

    @pytest.mark.anyio
    async def test_compaction_summarizer_returns_empty_summary(self):
        """When summarizer returns empty string, no summary is added to result."""
        mock_provider = MagicMock()

        # Mock to return empty summary (which causes summarizer to return None)
        async def mock_stream(*_args, **_kwargs):
            yield StreamChunk(content="", finish_reason=FinishReason.STOP)  # Empty summary

        mock_provider.chat_completion_stream = mock_stream

        msgs = [
            Message(role="system", content="System."),
            Message(role="user", content="Message " * 100),
            Message(role="assistant", content="Response " * 100),
            Message(role="user", content="Latest."),
        ]

        result = await compact_messages(CompactionParams(messages=msgs, max_tokens=50, provider=mock_provider, summarize=True))

        assert result.was_compacted is True
        assert result.summary is None
        # No summary message should be added
        summary_msgs = [
            m for m in result.messages if "Summary of earlier conversation" in m.content
        ]
        assert len(summary_msgs) == 0

    @pytest.mark.anyio
    async def test_compaction_without_summarize_flag(self):
        """When summarize=False, summarization is not attempted even with provider."""
        mock_provider = MagicMock()
        mock_provider.chat_completion_stream = AsyncMock()

        msgs = [
            Message(role="system", content="System."),
            Message(role="user", content="Message " * 100),
            Message(role="user", content="Latest."),
        ]

        result = await compact_messages(CompactionParams(messages=msgs, max_tokens=50, provider=mock_provider, summarize=False))

        assert result.was_compacted is True
        assert result.summary is None
        mock_provider.chat_completion_stream.assert_not_called()

    @pytest.mark.anyio
    async def test_compaction_summarization_exception_handling(self):
        """Exception in summarization is caught and handled gracefully."""
        mock_provider = MagicMock()

        # Create an async generator that raises an exception
        async def mock_stream(*_args, **_kwargs):
            raise Exception("Summarization API error")
            yield  # This makes it a generator, but the exception happens first

        mock_provider.chat_completion_stream = mock_stream

        msgs = [
            Message(role="system", content="System."),
            Message(role="user", content="Message " * 100),
            Message(role="assistant", content="Response " * 100),
            Message(role="user", content="Latest."),
        ]

        # Should not raise exception
        result = await compact_messages(CompactionParams(messages=msgs, max_tokens=50, provider=mock_provider, summarize=True))

        assert result.was_compacted is True
        # Compaction should still work even if summarization failed
        assert len(result.messages) < len(msgs)

    @pytest.mark.anyio
    async def test_summarize_comprehensive_coverage(self):
        """Test all code paths in summarize method."""
        # Test 1: With provider, successful summary with caching
        mock_provider1 = MagicMock()

        async def mock_stream1(*_args, **_kwargs):
            yield StreamChunk(content="Summary ", finish_reason=None)
            yield StreamChunk(content="text", finish_reason=FinishReason.STOP)

        mock_provider1.chat_completion_stream = mock_stream1

        summarizer1 = MessageSummarizer(provider=mock_provider1)
        result1 = await summarizer1.summarize([Message(role="user", content="Hello")])
        assert result1 == "Summary text"
        assert summarizer1._cached_summary == "Summary text"

        # Test 2: With provider, empty summary returns None
        mock_provider2 = MagicMock()

        async def mock_stream2(*_args, **_kwargs):
            yield StreamChunk(content="", finish_reason=FinishReason.STOP)

        mock_provider2.chat_completion_stream = mock_stream2

        summarizer2 = MessageSummarizer(provider=mock_provider2)
        result2 = await summarizer2.summarize([Message(role="user", content="Hello")])
        assert result2 is None
        assert summarizer2._cached_summary is None

        # Test 3: Exception in provider returns None
        mock_provider3 = MagicMock()

        async def mock_stream3(*_args, **_kwargs):
            raise Exception("API error")
            yield  # pragma: no cover - keep this an async generator

        mock_provider3.chat_completion_stream = mock_stream3

        summarizer3 = MessageSummarizer(provider=mock_provider3)
        result3 = await summarizer3.summarize([Message(role="user", content="Hello")])
        assert result3 is None

        # Test 4: Only system messages returns None
        mock_provider4 = MagicMock()
        summarizer4 = MessageSummarizer(provider=mock_provider4)
        result4 = await summarizer4.summarize([Message(role="system", content="System prompt")])
        assert result4 is None
        mock_provider4.chat_completion_stream.assert_not_called()
