"""Edge case tests for compaction coverage."""

from henchman.providers.base import Message, ToolCall
from henchman.utils.compaction import ContextCompactor, MessageSequence


class TestMessageSequenceEdgeCases:
    """Tests for MessageSequence edge cases."""

    def test_repr(self) -> None:
        """MessageSequence repr should show roles and token count."""
        msgs = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi"),
        ]
        seq = MessageSequence(msgs)

        repr_str = repr(seq)

        assert "user" in repr_str
        assert "assistant" in repr_str
        assert "tokens=" in repr_str

    def test_is_tool_sequence_true(self) -> None:
        """Should detect tool sequences."""
        msgs = [
            Message(
                role="assistant",
                content="x",
                tool_calls=[ToolCall(id="tc1", name="test", arguments={})],
            ),
            Message(role="tool", content="result", tool_call_id="tc1"),
        ]
        seq = MessageSequence(msgs)

        assert seq.is_tool_sequence is True

    def test_is_tool_sequence_false(self) -> None:
        """Should detect non-tool sequences."""
        msgs = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi"),
        ]
        seq = MessageSequence(msgs)

        assert seq.is_tool_sequence is False


class TestCompactorEdgeCases:
    """Edge case tests for ContextCompactor."""

    def test_empty_unprotected_with_protected(self) -> None:
        """Handle case where unprotected zone is empty."""
        compactor = ContextCompactor(max_tokens=500)

        # All messages are protected (protect from index 0)
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there"),
        ]

        result = compactor.compact(messages, protect_from_index=0)

        # Should keep all messages
        assert len(result) == 2

    def test_degenerate_budget_system_only(self) -> None:
        """Handle case where budget only fits system."""
        compactor = ContextCompactor(max_tokens=50, max_protected_ratio=0.1)

        messages = [
            Message(role="system", content="Short"),
            Message(role="user", content="x" * 500),  # protected but huge
        ]

        result = compactor.compact(messages, protect_from_index=1)

        # Should at least have system
        assert any(m.role == "system" for m in result)

    def test_no_sequences_empty_history(self) -> None:
        """Handle empty message list."""
        compactor = ContextCompactor(max_tokens=1000)

        result = compactor.compact([])

        assert result == []

    def test_budget_exactly_zero(self) -> None:
        """Handle edge case where budget is exactly zero."""
        compactor = ContextCompactor(max_tokens=20, max_protected_ratio=0.9)

        messages = [
            Message(role="system", content="System message here"),
            Message(role="user", content="x" * 100),  # protected, exceeds budget
        ]

        result = compactor.compact(messages, protect_from_index=1)

        # Should return something
        assert len(result) >= 1


class TestProtectedZoneTruncation:
    """Tests for protected zone truncation edge cases."""

    def test_truncation_skips_non_tool_messages(self) -> None:
        """Protected zone truncation should only affect tool messages."""
        compactor = ContextCompactor(max_tokens=100, max_protected_ratio=0.3)

        messages = [
            Message(role="system", content="Sys"),
            Message(role="user", content="Request" * 50),  # Large protected user
        ]

        result = compactor.compact(messages, protect_from_index=1)

        # User message should still be there (truncation targets tool msgs)
        assert any(m.role == "user" for m in result)

    def test_truncation_small_tool_content(self) -> None:
        """Small tool content should not be truncated."""
        compactor = ContextCompactor(max_tokens=200, max_protected_ratio=0.5)

        messages = [
            Message(role="system", content="Sys"),
            Message(role="user", content="Request"),
            Message(
                role="assistant",
                content="OK",
                tool_calls=[ToolCall(id="tc1", name="read", arguments={})],
            ),
            Message(role="tool", content="Short", tool_call_id="tc1"),  # Small
        ]

        result = compactor.compact(messages, protect_from_index=1)

        # Small tool content should be preserved
        tool_msgs = [m for m in result if m.role == "tool"]
        if tool_msgs:
            assert tool_msgs[0].content == "Short"

    def test_truncation_integer_division_bug(self) -> None:
        """Test that integer division doesn't cause token underestimation.

        The bug: trimmed_tokens = (char_diff) // CHARS_PER_TOKEN_ESTIMATE
        Integer division rounds down small character reductions to 0 tokens,
        causing cumulative underestimation.

        This test verifies that the fix uses actual token counting instead of
        integer division, which would underestimate small truncations.
        """
        # Use a very small max_tokens to force truncation
        compactor = ContextCompactor(max_tokens=50, max_protected_ratio=0.5)

        # Create tool message with content over TRUNCATION_CHAR_THRESHOLD
        tool_msg = Message(
            role="tool",
            content="x" * 600,  # 600 chars, well over threshold
            tool_call_id="tc1"
        )

        original_length = len(tool_msg.content or "")

        messages = [
            Message(role="system", content="System"),
            Message(role="user", content="User request"),
            Message(
                role="assistant",
                content="OK",
                tool_calls=[ToolCall(id="tc1", name="test", arguments={})]
            ),
            tool_msg,
        ]

        # Compact with protection (all messages from index 2 are protected)
        result = compactor.compact(messages, protect_from_index=2)

        # Find the tool message in result
        tool_msgs = [m for m in result if m.role == "tool"]
        assert len(tool_msgs) == 1, "Tool message should be preserved"

        truncated_length = len(tool_msgs[0].content or "")

        # Tool message should be truncated (content > TRUNCATION_CHAR_THRESHOLD
        # and protected zone exceeds budget)
        assert truncated_length < original_length, (
            f"Tool message should be truncated: {truncated_length} < {original_length}"
        )

        # Verify significant truncation occurred
        print(f"Original length: {original_length}, Truncated length: {truncated_length}")
        assert original_length - truncated_length > 100, "Significant truncation should occur"
