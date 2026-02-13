"""Tests for context compaction with tool call sequences."""

from henchman.providers.base import Message, ToolCall
from henchman.utils.compaction import ContextCompactor


class TestCompactionWithToolSequences:
    """Test that compaction preserves tool call sequences correctly."""

    def test_compaction_preserves_single_tool_sequence(self) -> None:
        """Test compaction preserves assistant → tool sequence."""
        messages = [
            Message(role="system", content="You are helpful"),
            Message(role="user", content="List files"),
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="call_1", name="ls", arguments={})],
            ),
            Message(role="tool", content="file1.txt", tool_call_id="call_1"),
            Message(role="assistant", content="Here are files"),
        ]

        compactor = ContextCompactor(max_tokens=1000)
        compacted = compactor.compact(messages)

        # Should preserve all messages (within token limit)
        assert len(compacted) == 5
        # Check sequence is preserved
        assert compacted[2].role == "assistant" and compacted[2].tool_calls
        assert compacted[3].role == "tool" and compacted[3].tool_call_id == "call_1"

    def test_compaction_preserves_multiple_tool_calls(self) -> None:
        """Test compaction preserves assistant with multiple tool calls."""
        messages = [
            Message(role="user", content="Do tasks"),
            Message(
                role="assistant",
                content="",
                tool_calls=[
                    ToolCall(id="call_1", name="task1", arguments={}),
                    ToolCall(id="call_2", name="task2", arguments={}),
                ],
            ),
            Message(role="tool", content="result1", tool_call_id="call_1"),
            Message(role="tool", content="result2", tool_call_id="call_2"),
            Message(role="assistant", content="Done"),
        ]

        compactor = ContextCompactor(max_tokens=1000)
        compacted = compactor.compact(messages)

        # Should preserve all messages
        assert len(compacted) == 5
        # Check tool messages follow assistant
        assert compacted[1].role == "assistant" and len(compacted[1].tool_calls) == 2
        assert compacted[2].role == "tool" and compacted[2].tool_call_id == "call_1"
        assert compacted[3].role == "tool" and compacted[3].tool_call_id == "call_2"

    def test_compaction_does_not_split_tool_sequence_when_pruning(self) -> None:
        """Test compaction doesn't split tool sequences when pruning needed."""
        # Create many messages to force pruning
        messages = [
            Message(role="system", content="System"),
            Message(role="user", content="Old message 1"),
            Message(role="assistant", content="Old response 1"),
            Message(role="user", content="Old message 2"),
            Message(role="assistant", content="Old response 2"),
            # Recent tool call sequence
            Message(role="user", content="List files"),
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="call_1", name="ls", arguments={})],
            ),
            Message(role="tool", content="files", tool_call_id="call_1"),
            Message(role="assistant", content="Here they are"),
        ]

        # Use very small token limit to force pruning
        compactor = ContextCompactor(max_tokens=50)
        compacted = compactor.compact(messages)

        # Should either keep entire tool sequence or none of it
        # Never keep tool message without its assistant
        for i, msg in enumerate(compacted):
            if msg.role == "tool":
                # Must have preceding assistant with tool_calls
                assert i > 0
                prev_msg = compacted[i - 1]
                assert prev_msg.role == "assistant"
                assert prev_msg.tool_calls is not None
                # Tool call ID must match
                tool_call_ids = [tc.id for tc in prev_msg.tool_calls]
                assert msg.tool_call_id in tool_call_ids

    def test_compaction_preserves_nested_tool_sequences(self) -> None:
        """Test compaction preserves multiple tool sequences in conversation."""
        messages = [
            Message(role="user", content="First task"),
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="call_a", name="task_a", arguments={})],
            ),
            Message(role="tool", content="result_a", tool_call_id="call_a"),
            Message(role="assistant", content="First done"),
            Message(role="user", content="Second task"),
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="call_b", name="task_b", arguments={})],
            ),
            Message(role="tool", content="result_b", tool_call_id="call_b"),
            Message(role="assistant", content="Second done"),
        ]

        compactor = ContextCompactor(max_tokens=1000)
        compacted = compactor.compact(messages)

        # Check both sequences are preserved correctly
        tool_messages = [msg for msg in compacted if msg.role == "tool"]
        assistant_with_tools = [
            msg for msg in compacted if msg.role == "assistant" and msg.tool_calls
        ]

        assert len(tool_messages) == 2
        assert len(assistant_with_tools) == 2

        # Verify each tool message follows its assistant
        for i, msg in enumerate(compacted):
            if msg.role == "tool":
                prev_msg = compacted[i - 1]
                assert prev_msg.role == "assistant"
                assert prev_msg.tool_calls is not None
                assert msg.tool_call_id in [tc.id for tc in prev_msg.tool_calls]

    def test_compaction_with_empty_tool_results(self) -> None:
        """Test compaction with tool messages that have empty content."""
        messages = [
            Message(role="user", content="Check something"),
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="call_1", name="check", arguments={})],
            ),
            Message(role="tool", content="", tool_call_id="call_1"),  # Empty result
            Message(role="assistant", content="Checked"),
        ]

        compactor = ContextCompactor(max_tokens=1000)
        compacted = compactor.compact(messages)

        # Should preserve sequence even with empty tool result
        assert len(compacted) == 4
        assert compacted[1].role == "assistant" and compacted[1].tool_calls
        assert compacted[2].role == "tool" and compacted[2].tool_call_id == "call_1"

    def test_compaction_validation_sequence_integrity(self) -> None:
        """Validate that compacted sequences are always valid for OpenAI API."""
        # Create various test sequences
        test_cases = [
            # Single tool call
            [
                Message(role="user", content="test"),
                Message(
                    role="assistant",
                    content="",
                    tool_calls=[ToolCall(id="1", name="t", arguments={})],
                ),
                Message(role="tool", content="r", tool_call_id="1"),
            ],
            # Multiple tool calls
            [
                Message(role="user", content="test"),
                Message(
                    role="assistant",
                    content="",
                    tool_calls=[
                        ToolCall(id="1", name="t1", arguments={}),
                        ToolCall(id="2", name="t2", arguments={}),
                    ],
                ),
                Message(role="tool", content="r1", tool_call_id="1"),
                Message(role="tool", content="r2", tool_call_id="2"),
            ],
            # Mixed content
            [
                Message(role="system", content="Help"),
                Message(role="user", content="hi"),
                Message(role="assistant", content="hello"),
                Message(role="user", content="do task"),
                Message(
                    role="assistant",
                    content="",
                    tool_calls=[ToolCall(id="1", name="t", arguments={})],
                ),
                Message(role="tool", content="done", tool_call_id="1"),
                Message(role="assistant", content="finished"),
            ],
        ]

        compactor = ContextCompactor(max_tokens=1000)

        for messages in test_cases:
            compacted = compactor.compact(messages)

            # Validate sequence
            # Track the last assistant message with tool_calls
            last_assistant_with_tools = None
            for i, msg in enumerate(compacted):
                if msg.role == "assistant" and msg.tool_calls:
                    last_assistant_with_tools = msg
                elif msg.role == "tool":
                    # Must have a preceding assistant with tool_calls (not necessarily immediately before)
                    assert last_assistant_with_tools is not None, (
                        f"Tool message at index {i} has no preceding assistant with tool_calls"
                    )

                    # Tool call ID must match one of the tool calls in the last assistant message
                    tool_call_ids = [tc.id for tc in last_assistant_with_tools.tool_calls]
                    assert msg.tool_call_id in tool_call_ids, (
                        f"Tool call ID {msg.tool_call_id} not in {tool_call_ids}"
                    )

    def test_edge_case_tool_message_at_beginning(self) -> None:
        """Test edge case: tool message should never appear at beginning."""
        # This would be invalid input, but compaction should handle it
        messages = [
            Message(role="tool", content="result", tool_call_id="call_1"),  # Invalid!
            Message(role="assistant", content="response"),
        ]

        compactor = ContextCompactor(max_tokens=1000)
        compacted = compactor.compact(messages)

        # Compaction shouldn't make it worse
        # If tool is at beginning, it's already invalid
        # We just ensure we don't crash
        assert compacted is not None

    def test_compaction_with_large_token_count(self) -> None:
        """Test compaction when tool sequences exceed token budget."""
        # Create messages that will exceed token budget
        messages = [
            Message(role="system", content="System prompt " * 100),  # Large system
            Message(role="user", content="User message " * 100),
            # Tool sequence
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="call_1", name="tool", arguments={"data": "x" * 100})],
            ),
            Message(role="tool", content="Result " * 100, tool_call_id="call_1"),
            Message(role="assistant", content="Response " * 100),
        ]

        # Very small token budget
        compactor = ContextCompactor(max_tokens=100)
        compacted = compactor.compact(messages)

        # Should keep system and maybe last user, but tool sequence might be dropped
        # If tool sequence is kept, it must be kept entirely
        if any(msg.role == "tool" for msg in compacted):
            # Find the tool message
            for i, msg in enumerate(compacted):
                if msg.role == "tool":
                    # Must have preceding assistant with tool_calls
                    assert i > 0
                    assert compacted[i - 1].role == "assistant"
                    assert compacted[i - 1].tool_calls is not None


def validate_compacted_sequence(compacted: list[Message]) -> None:
    """Validate that compacted sequence follows OpenAI API rules.

    Raises AssertionError if sequence is invalid.
    """
    for i, msg in enumerate(compacted):
        if msg.role == "tool":
            # Tool messages must follow assistant with tool_calls
            assert i > 0, f"Tool message at index {i} has no preceding message"
            prev_msg = compacted[i - 1]
            assert prev_msg.role == "assistant", (
                f"Tool message at {i} doesn't follow assistant (follows {prev_msg.role})"
            )
            assert prev_msg.tool_calls is not None, (
                f"Preceding assistant at {i - 1} has no tool_calls"
            )

            # Tool call ID must match one of the assistant's tool calls
            tool_call_ids = [tc.id for tc in prev_msg.tool_calls]
            assert msg.tool_call_id in tool_call_ids, (
                f"Tool call ID {msg.tool_call_id} not found in {tool_call_ids}"
            )

        elif msg.role == "assistant" and msg.tool_calls:
            # Assistant with tool_calls should be followed by tool messages
            # Check next messages are tools for these calls
            tool_call_ids = {tc.id for tc in msg.tool_calls}
            j = i + 1
            while j < len(compacted) and compacted[j].role == "tool":
                if compacted[j].tool_call_id in tool_call_ids:
                    tool_call_ids.remove(compacted[j].tool_call_id)
                j += 1

            # All tool calls should have responses
            assert len(tool_call_ids) == 0, (
                f"Assistant at {i} has tool calls without responses: {tool_call_ids}"
            )
