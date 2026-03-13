"""Tests targeting missing coverage lines in utils modules."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from henchman.providers.base import Message, ToolCall
from henchman.utils.compaction import CompactionResult
from henchman.utils.retry import RetryConfig, with_retry
from henchman.utils.validation import validate_message_sequence

# ---------------------------------------------------------------------------
# validation.py – lines 54-58: duplicate tool_call_id raises ValueError
# ---------------------------------------------------------------------------


class TestValidateDuplicateToolCallId:
    """Cover lines 54-58 in validation.py: duplicate tool response detected."""

    def test_duplicate_tool_call_id_raises(self) -> None:
        """Lines 54-58: ValueError raised when tool_call_id appears twice."""
        assistant_msg = Message(
            role="assistant",
            content="",
            tool_calls=[
                ToolCall(id="tc-1", name="tool_a", arguments="{}"),
                ToolCall(id="tc-2", name="tool_b", arguments="{}"),
            ],
        )
        # Two tool messages with the same tool_call_id (duplicate)
        tool_response_1 = Message(role="tool", content="result a", tool_call_id="tc-1")
        tool_response_2 = Message(role="tool", content="duplicate", tool_call_id="tc-1")

        with pytest.raises(ValueError, match="Duplicate tool response"):
            validate_message_sequence(
                [assistant_msg, tool_response_1, tool_response_2]
            )


# ---------------------------------------------------------------------------
# compaction.py – line 1026: _compact_with_summarization_impl returns early
# ---------------------------------------------------------------------------


class TestCompactWithSummarizationNotCompacted:
    """Cover line 1026 in compaction.py: result not compacted → return early."""

    @pytest.mark.anyio
    async def test_returns_early_when_not_compacted(self) -> None:
        """Line 1026: CompactionResult(was_compacted=False) is returned as-is."""
        from henchman.utils.compaction import SummarizationConfig, _compact_with_summarization_impl

        messages = [Message(role="user", content="hello")]

        mock_result = CompactionResult(messages=messages, was_compacted=False)

        with patch(
            "henchman.utils.compaction.ContextCompactor"
        ) as mock_compactor_cls:
            mock_compactor = MagicMock()
            mock_compactor.compact_with_result.return_value = mock_result
            mock_compactor_cls.return_value = mock_compactor

            with patch(
                "henchman.utils.compaction.TokenCounter"
            ) as mock_tc:
                # Exceed max_tokens to skip the early return at line 1019-1020
                mock_tc.count_messages.return_value = 9999

                config = SummarizationConfig(
                    protect_from_index=0,
                    summarize=True,
                )
                result = await _compact_with_summarization_impl(
                    messages=messages,
                    max_tokens=100,
                    config=config,
                )

        assert result.was_compacted is False


# ---------------------------------------------------------------------------
# retry.py – line 120: RuntimeError when max_retries=-1 (empty loop range)
# ---------------------------------------------------------------------------


class TestRetryWithNegativeMaxRetries:
    """Cover line 120 in retry.py: unreachable RuntimeError path via empty range."""

    @pytest.mark.anyio
    async def test_raises_runtime_error_with_empty_range(self) -> None:
        """Line 120: range(max_retries + 1) = range(0) → last_exception is None → RuntimeError."""
        config = RetryConfig(max_retries=-1)

        @with_retry(config)
        async def _never_called() -> str:
            """Function that should never execute."""
            return "should not reach here"

        with pytest.raises(RuntimeError, match="Retry logic error"):
            await _never_called()


# ---------------------------------------------------------------------------
# compaction.py – branches 189->exit, 194->189, 729->738
# ---------------------------------------------------------------------------


class TestCompactionBranches:
    """Cover missing branches in MessageSequenceGrouper and ContextCompactor."""

    def test_tool_call_loop_exits_naturally(self) -> None:
        """Branch 189->exit: for-loop in _handle_tool_call_sequence completes w/o break."""
        from henchman.utils.compaction import MessageSequenceGrouper

        assistant = Message(
            role="assistant",
            content="",
            tool_calls=[ToolCall(id="tc-orphan", name="my_tool", arguments="{}")],
        )
        # Another assistant message follows (not a user message, not a matching tool response)
        another_assistant = Message(role="assistant", content="follow-up", tool_calls=None)

        messages = [assistant, another_assistant]

        # This should NOT raise; the for-loop should complete without finding a tool response
        sequences = MessageSequenceGrouper.group_into_sequences(messages)
        assert len(sequences) >= 1

    def test_non_matching_tool_message_skipped(self) -> None:
        """Branch 194->189: tool message with non-matching tool_call_id is skipped."""
        from henchman.utils.compaction import MessageSequenceGrouper

        assistant = Message(
            role="assistant",
            content="",
            tool_calls=[ToolCall(id="expected-id", name="my_tool", arguments="{}")],
        )
        # Tool response with a DIFFERENT tool_call_id (doesn't match)
        tool_response = Message(
            role="tool", content="result", tool_call_id="different-id"
        )

        messages = [assistant, tool_response]

        sequences = MessageSequenceGrouper.group_into_sequences(messages)
        assert isinstance(sequences, list)

    def test_all_sequences_fit_in_budget_direct(self) -> None:
        """Branch 729->738: for-loop completes without break (all sequences fit)."""
        from henchman.utils.compaction import ContextCompactor

        # Very large budget so all sequences fit and loop completes naturally
        compactor = ContextCompactor(max_tokens=100000)

        messages = [
            Message(role="user", content="hi"),
            Message(role="assistant", content="hello"),
            Message(role="user", content="bye"),
        ]
        result = compactor.compact(messages, protect_from_index=0)
        # All messages should be kept since they fit
        assert isinstance(result, list)
        assert len(result) > 0

    def test_select_sequences_all_fit_in_budget(self) -> None:
        """Branch 729->738: for-loop in _select_sequences_to_keep completes without break."""
        from henchman.utils.compaction import ContextCompactor, MessageSequence

        compactor = ContextCompactor(max_tokens=50)

        # Build mock sequences where all fit in budget
        seq1 = MagicMock(spec=MessageSequence)
        seq1.token_count = 5
        seq2 = MagicMock(spec=MessageSequence)
        seq2.token_count = 5
        # Last sequence (user) with small token count
        last_seq = MagicMock(spec=MessageSequence)
        last_seq.token_count = 3
        last_seq.messages = [Message(role="user", content="hi")]

        # sequences_to_consider = [seq1, seq2], budget = 50 - 3 = 47; both fit
        result = compactor._select_sequences_to_keep(
            sequences=[seq1, seq2, last_seq],
            protected_msgs=[],
            system_tokens=0,
            protected_tokens=0,
        )
        kept, last, _ = result
        # Both seq1 and seq2 should be kept (all fit)
        assert len(kept) == 2
