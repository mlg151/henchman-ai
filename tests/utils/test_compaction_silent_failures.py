"""Tests for BUG-019: Message Summarization Failures Are Completely Silent.

Verifies that compaction.py logs warnings when summarization fails
instead of silently passing.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.providers.base import Message
from henchman.utils.compaction import (
    CompactionResult,
    _attempt_summarization,
    _generate_summary_with_provider,
)


@pytest.mark.asyncio
async def test_generate_summary_logs_warning_on_failure() -> None:
    """When _generate_summary_with_provider fails, a warning should be logged."""

    async def _stream(*_args: object, **_kwargs: object) -> object:  # type: ignore[misc]
        """Async generator that raises on first iteration."""
        raise RuntimeError("LLM provider is down")
        yield  # pragma: no cover — makes this an async generator

    provider = MagicMock()
    provider.chat_completion_stream = _stream

    with patch("henchman.utils.compaction.logger") as mock_logger:
        result = await _generate_summary_with_provider(
            provider,
            [Message(role="user", content="test")],
            lambda _msgs: "formatted",
        )

    assert result is None
    mock_logger.warning.assert_called_once()
    args, _ = mock_logger.warning.call_args
    assert "summarization" in args[0].lower() or "failed" in args[0].lower()


@pytest.mark.asyncio
async def test_generate_summary_no_warning_on_empty_summary() -> None:
    """When provider returns empty content, no warning is logged (not a failure)."""
    provider = MagicMock()

    async def mock_stream(**_kwargs):
        class Chunk:
            def __init__(self) -> None:
                self.content = ""
                self.finish_reason = "stop"
        yield Chunk()

    provider.chat_completion_stream.return_value = mock_stream()

    with patch("henchman.utils.compaction.logger") as mock_logger:
        result = await _generate_summary_with_provider(
            provider,
            [Message(role="user", content="test")],
            lambda _msgs: "formatted",
        )

    assert result is None
    mock_logger.warning.assert_not_called()


@pytest.mark.asyncio
async def test_attempt_summarization_logs_warning_on_failure() -> None:
    """When _attempt_summarization fails, a warning should be logged."""
    provider = MagicMock()
    # Messages appearing in original_messages but NOT in result.messages are "dropped"
    kept_msg = Message(role="system", content="sys")
    dropped_msg = Message(role="user", content="hello")
    original_messages = [kept_msg, dropped_msg]
    # result.messages only has the kept message, so dropped_msg is "dropped"
    result = CompactionResult(messages=[kept_msg])

    with (
        patch("henchman.utils.compaction.MessageSummarizer") as mock_summarizer_cls,
        patch("henchman.utils.compaction.logger") as mock_logger,
    ):
        mock_summarizer = MagicMock()
        mock_summarizer.summarize = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        mock_summarizer_cls.return_value = mock_summarizer

        output = await _attempt_summarization(result, original_messages, provider)

    assert output is result  # Returns the original result on failure
    mock_logger.warning.assert_called_once()
