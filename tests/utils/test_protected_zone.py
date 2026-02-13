"""Tests for protected zone in context compaction."""

from henchman.providers.base import Message, ToolCall
from henchman.utils.compaction import ContextCompactor
from henchman.utils.tokens import TokenCounter


class TestProtectedZone:
    """Tests for protect_from_index parameter in compaction."""

    def test_no_protection_by_default(self) -> None:
        """Without protect_from_index, all messages can be pruned."""
        compactor = ContextCompactor(max_tokens=50)

        messages = [
            Message(role="system", content="System"),
            Message(role="user", content="x" * 100),
            Message(role="assistant", content="y" * 100),
            Message(role="user", content="z" * 100),
        ]

        result = compactor.compact(messages, protect_from_index=-1)

        # With no protection, should prune to fit
        assert len(result) < len(messages)

    def test_protection_preserves_current_turn(self) -> None:
        """Messages at/after protect_from_index are kept."""
        # Use a larger budget to not trigger safety limits
        compactor = ContextCompactor(max_tokens=500)

        messages = [
            Message(role="system", content="System prompt"),
            Message(role="user", content="Old message"),
            Message(role="assistant", content="Old response"),
            Message(role="user", content="Current turn message"),  # index 3
            Message(role="assistant", content="Current response"),
        ]

        # Calculate tokens to set up a scenario where pruning is needed
        # but protected zone should be preserved
        total_tokens = TokenCounter.count_messages(messages)
        compactor = ContextCompactor(max_tokens=total_tokens - 30)

        result = compactor.compact(messages, protect_from_index=3)

        # Current turn messages should be preserved
        contents = [m.content for m in result if m.content]
        assert any("Current turn" in c for c in contents)
        assert any("Current response" in c for c in contents)

    def test_protected_zone_budget_limit(self) -> None:
        """Protected zone should not exceed max_protected_ratio."""
        # 30% protected ratio with 100 token budget = 30 tokens max protected
        compactor = ContextCompactor(max_tokens=100, max_protected_ratio=0.3)

        # Create messages where protected zone exceeds 30% budget
        # Content needs to be >500 chars to trigger truncation in _truncate_protected_zone
        messages = [
            Message(role="system", content="Sys"),
            Message(role="user", content="Request"),  # protect from here
            Message(
                role="assistant",
                content="response",
                tool_calls=[ToolCall(id="tc1", name="read", arguments={})],
            ),
            Message(role="tool", content="x" * 1000, tool_call_id="tc1"),  # Large result
        ]

        result = compactor.compact(messages, protect_from_index=1)

        # Should truncate the tool result to fit protected budget
        tool_msgs = [m for m in result if m.role == "tool"]
        assert len(tool_msgs) > 0
        # The tool message should be shorter than original
        assert len(tool_msgs[0].content) < 1000

    def test_tool_sequences_in_protected_zone(self) -> None:
        """Tool sequences in protected zone stay intact (but may be truncated)."""
        compactor = ContextCompactor(max_tokens=500, max_protected_ratio=0.5)

        messages = [
            Message(role="system", content="System"),
            Message(role="user", content="Do something"),  # index 1, protected
            Message(
                role="assistant",
                content="I'll help",
                tool_calls=[
                    ToolCall(id="tc1", name="read_file", arguments={}),
                    ToolCall(id="tc2", name="write_file", arguments={}),
                ],
            ),
            Message(role="tool", content="file content", tool_call_id="tc1"),
            Message(role="tool", content="write success", tool_call_id="tc2"),
        ]

        result = compactor.compact(messages, protect_from_index=1)

        # Both tool results should still be present
        tool_msgs = [m for m in result if m.role == "tool"]
        assert len(tool_msgs) == 2

    def test_unprotected_pruned_before_protected(self) -> None:
        """Unprotected old messages are pruned before touching protected zone."""
        compactor = ContextCompactor(max_tokens=200)

        # Build up history with old messages then new protected turn
        messages = [
            Message(role="system", content="System"),
            Message(role="user", content="Old request 1"),
            Message(role="assistant", content="Old response 1"),
            Message(role="user", content="Old request 2"),
            Message(role="assistant", content="Old response 2"),
            Message(role="user", content="Current request"),  # index 5, protected
            Message(role="assistant", content="Current response"),
        ]

        result = compactor.compact(messages, protect_from_index=5)

        # Current turn should be intact
        contents = [m.content for m in result if m.content]
        assert any("Current request" in c for c in contents), "Protected user message missing"
        assert any("Current response" in c for c in contents), "Protected assistant message missing"


class TestCompactorMaxProtectedRatio:
    """Tests for max_protected_ratio parameter."""

    def test_default_30_percent(self) -> None:
        """Default max_protected_ratio should be 0.3."""
        compactor = ContextCompactor(max_tokens=1000)
        assert compactor.max_protected_ratio == 0.3
        assert compactor.max_protected_tokens == 300

    def test_custom_ratio(self) -> None:
        """Should accept custom max_protected_ratio."""
        compactor = ContextCompactor(max_tokens=1000, max_protected_ratio=0.5)
        assert compactor.max_protected_ratio == 0.5
        assert compactor.max_protected_tokens == 500

    def test_zero_ratio_no_protection(self) -> None:
        """Zero ratio means no protected zone budget."""
        compactor = ContextCompactor(max_tokens=1000, max_protected_ratio=0.0)
        assert compactor.max_protected_tokens == 0
