"""Test message sequence validation."""

import os
import sys

# Add src to path so we can import henchman
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import pytest

from henchman.providers.base import Message, ToolCall
from henchman.utils.validation import (
    format_message_sequence_for_debug,
    is_valid_message_sequence,
    repair_message_sequence,
    validate_message_sequence,
)


class TestMessageSequenceValidation:
    """Test validation of message sequences."""

    def test_valid_single_tool_sequence(self) -> None:
        """Test valid single tool call sequence."""
        messages = [
            Message(role="user", content="test"),
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="call_1", name="tool", arguments={})],
            ),
            Message(role="tool", content="result", tool_call_id="call_1"),
        ]

        # Should not raise
        validate_message_sequence(messages)
        assert is_valid_message_sequence(messages) is True

    def test_valid_multiple_tool_calls(self) -> None:
        """Test valid multiple tool calls."""
        messages = [
            Message(role="user", content="test"),
            Message(
                role="assistant",
                content="",
                tool_calls=[
                    ToolCall(id="call_1", name="tool1", arguments={}),
                    ToolCall(id="call_2", name="tool2", arguments={}),
                ],
            ),
            Message(role="tool", content="result1", tool_call_id="call_1"),
            Message(role="tool", content="result2", tool_call_id="call_2"),
        ]

        validate_message_sequence(messages)
        assert is_valid_message_sequence(messages) is True

    def test_invalid_tool_without_assistant(self) -> None:
        """Test invalid: tool message without preceding assistant."""
        messages = [
            Message(role="tool", content="result", tool_call_id="call_1"),  # Invalid!
        ]

        with pytest.raises(ValueError, match="doesn't follow any assistant"):
            validate_message_sequence(messages)

        assert is_valid_message_sequence(messages) is False

    def test_invalid_tool_without_tool_calls(self) -> None:
        """Test invalid: tool message follows assistant without tool_calls."""
        messages = [
            Message(role="user", content="test"),
            Message(role="assistant", content="response"),  # No tool_calls!
            Message(role="tool", content="result", tool_call_id="call_1"),
        ]

        with pytest.raises(
            ValueError, match="doesn't follow any assistant message with tool_calls"
        ):
            validate_message_sequence(messages)

        assert is_valid_message_sequence(messages) is False

    def test_invalid_mismatched_tool_call_id(self) -> None:
        """Test invalid: tool call ID doesn't match."""
        messages = [
            Message(role="user", content="test"),
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="call_1", name="tool", arguments={})],
            ),
            Message(role="tool", content="result", tool_call_id="call_2"),  # Wrong ID!
        ]

        with pytest.raises(ValueError, match="doesn't match any tool call"):
            validate_message_sequence(messages)

        assert is_valid_message_sequence(messages) is False

    def test_invalid_missing_tool_response(self) -> None:
        """Test invalid: assistant has tool call without response."""
        messages = [
            Message(role="user", content="test"),
            Message(
                role="assistant",
                content="",
                tool_calls=[
                    ToolCall(id="call_1", name="tool1", arguments={}),
                    ToolCall(id="call_2", name="tool2", arguments={}),
                ],
            ),
            Message(role="tool", content="result1", tool_call_id="call_1"),
            # Missing response for call_2!
        ]

        with pytest.raises(ValueError, match="has tool calls without responses"):
            validate_message_sequence(messages)

        assert is_valid_message_sequence(messages) is False

    def test_invalid_zero_tool_responses(self) -> None:
        """Test invalid: assistant has tool_calls but ZERO tool responses.

        This was the bug that caused the 400 error — old validation skipped
        this case entirely because pending_tool_calls was never populated.
        """
        messages = [
            Message(role="user", content="test"),
            Message(
                role="assistant",
                content="I'll check",
                tool_calls=[ToolCall(id="call_1", name="tool", arguments={})],
            ),
            Message(role="user", content="what happened?"),
        ]

        with pytest.raises(ValueError, match="has tool calls without responses"):
            validate_message_sequence(messages)

        assert is_valid_message_sequence(messages) is False

    def test_invalid_tool_separated_by_user(self) -> None:
        """Test invalid: tool message separated from assistant by a user message."""
        messages = [
            Message(role="user", content="do it"),
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="call_1", name="tool", arguments={})],
            ),
            Message(role="user", content="interruption"),
            Message(role="tool", content="result", tool_call_id="call_1"),
        ]

        assert is_valid_message_sequence(messages) is False

    def test_valid_complex_sequence(self) -> None:
        """Test valid complex sequence with multiple exchanges."""
        messages = [
            Message(role="system", content="You are helpful"),
            Message(role="user", content="First request"),
            Message(role="assistant", content="First response"),
            Message(role="user", content="Do task"),
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="call_a", name="task", arguments={})],
            ),
            Message(role="tool", content="task done", tool_call_id="call_a"),
            Message(role="assistant", content="Task completed"),
            Message(role="user", content="Another task"),
            Message(
                role="assistant",
                content="",
                tool_calls=[
                    ToolCall(id="call_b", name="task1", arguments={}),
                    ToolCall(id="call_c", name="task2", arguments={}),
                ],
            ),
            Message(role="tool", content="result1", tool_call_id="call_b"),
            Message(role="tool", content="result2", tool_call_id="call_c"),
            Message(role="assistant", content="All done"),
        ]

        validate_message_sequence(messages)
        assert is_valid_message_sequence(messages) is True

    def test_format_debug_output(self) -> None:
        """Test debug formatting."""
        messages = [
            Message(role="user", content="test"),
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="call_1", name="tool", arguments={})],
            ),
            Message(role="tool", content="result", tool_call_id="call_1"),
        ]

        debug_output = format_message_sequence_for_debug(messages)

        assert "user" in debug_output
        assert "assistant" in debug_output
        assert "tool" in debug_output
        assert "call_1" in debug_output

    def test_empty_sequence(self) -> None:
        """Test empty sequence is valid."""
        messages: list[Message] = []

        validate_message_sequence(messages)
        assert is_valid_message_sequence(messages) is True

    def test_sequence_without_tools(self) -> None:
        """Test sequence without tools is valid."""
        messages = [
            Message(role="user", content="hello"),
            Message(role="assistant", content="hi"),
            Message(role="user", content="how are you"),
            Message(role="assistant", content="good"),
        ]

        validate_message_sequence(messages)
        assert is_valid_message_sequence(messages) is True


class TestRepairMessageSequence:
    """Test repair_message_sequence for broken tool sequences."""

    def test_repair_empty_sequence(self) -> None:
        """Test repairing an empty sequence returns empty."""
        result = repair_message_sequence([])
        assert result == []

    def test_repair_valid_sequence_unchanged(self) -> None:
        """Test that a valid sequence is returned unchanged."""
        messages = [
            Message(role="user", content="test"),
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="call_1", name="tool", arguments={})],
            ),
            Message(role="tool", content="result", tool_call_id="call_1"),
        ]
        result = repair_message_sequence(messages)
        assert len(result) == 3
        assert is_valid_message_sequence(result)

    def test_repair_orphaned_tool_at_start(self) -> None:
        """Test removing orphaned tool message at the start."""
        messages = [
            Message(role="tool", content="orphan", tool_call_id="call_x"),
            Message(role="user", content="hello"),
            Message(role="assistant", content="hi"),
        ]
        result = repair_message_sequence(messages)
        assert len(result) == 2
        assert result[0].role == "user"
        assert is_valid_message_sequence(result)

    def test_repair_orphaned_tool_after_compaction(self) -> None:
        """Test the exact scenario from the bug: tool after compaction."""
        messages = [
            Message(role="system", content="You are helpful"),
            Message(role="system", content="[Summary of earlier conversation]"),
            Message(role="user", content="do something"),
            Message(role="assistant", content="sure"),
            Message(role="tool", content="result", tool_call_id="call_1"),  # Orphaned!
            Message(role="user", content="Continue on"),
        ]
        assert not is_valid_message_sequence(messages)

        result = repair_message_sequence(messages)
        assert is_valid_message_sequence(result)
        assert len(result) == 5  # Orphaned tool removed
        assert all(m.role != "tool" for m in result)

    def test_repair_mismatched_tool_call_id(self) -> None:
        """Test removing tool message with wrong tool_call_id."""
        messages = [
            Message(role="user", content="test"),
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="call_1", name="tool", arguments={})],
            ),
            Message(role="tool", content="result", tool_call_id="call_wrong"),  # Mismatched!
        ]
        result = repair_message_sequence(messages)
        assert is_valid_message_sequence(result)
        # The orphaned tool is removed, assistant's tool_calls stripped
        assert not any(m.role == "tool" for m in result)
        assert result[1].tool_calls is None

    def test_repair_strips_assistant_tool_calls_without_responses(self) -> None:
        """Test stripping tool_calls from assistant when responses are missing."""
        # Case: assistant has tool_calls but partial responses
        messages = [
            Message(role="user", content="test"),
            Message(
                role="assistant",
                content="I'll do both",
                tool_calls=[
                    ToolCall(id="call_1", name="t1", arguments={}),
                    ToolCall(id="call_2", name="t2", arguments={}),
                ],
            ),
            Message(role="tool", content="r1", tool_call_id="call_1"),
            # call_2 response missing (dropped by compaction)
        ]
        assert not is_valid_message_sequence(messages)

        result = repair_message_sequence(messages)
        assert is_valid_message_sequence(result)

    def test_repair_zero_tool_responses(self) -> None:
        """Test repair when assistant has tool_calls with zero responses.

        This was the root cause of the 400 error — old validation didn't
        catch this, so repair never ran.
        """
        messages = [
            Message(role="user", content="test"),
            Message(
                role="assistant",
                content="I'll check",
                tool_calls=[ToolCall(id="call_1", name="tool", arguments={})],
            ),
            Message(role="user", content="what happened?"),
        ]
        assert not is_valid_message_sequence(messages)

        result = repair_message_sequence(messages)
        assert is_valid_message_sequence(result)
        # Assistant message should have tool_calls stripped
        assistant_msgs = [m for m in result if m.role == "assistant"]
        assert len(assistant_msgs) == 1
        assert assistant_msgs[0].tool_calls is None

    def test_repair_preserves_valid_tool_sequences(self) -> None:
        """Test that valid tool sequences are preserved during repair."""
        messages = [
            Message(role="system", content="system"),
            Message(role="user", content="task"),
            Message(
                role="assistant",
                content="",
                tool_calls=[
                    ToolCall(id="call_1", name="t1", arguments={}),
                    ToolCall(id="call_2", name="t2", arguments={}),
                ],
            ),
            Message(role="tool", content="r1", tool_call_id="call_1"),
            Message(role="tool", content="r2", tool_call_id="call_2"),
            Message(role="assistant", content="Done"),
        ]
        result = repair_message_sequence(messages)
        assert len(result) == 6  # Nothing removed
        assert is_valid_message_sequence(result)

    def test_repair_mixed_valid_and_orphaned(self) -> None:
        """Test repairing a sequence with both valid and orphaned tool messages."""
        messages = [
            Message(role="system", content="system"),
            Message(role="user", content="task"),
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="call_1", name="t1", arguments={})],
            ),
            Message(role="tool", content="r1", tool_call_id="call_1"),  # Valid
            Message(role="assistant", content="next step"),
            Message(role="tool", content="orphan", tool_call_id="call_2"),  # Orphaned!
            Message(role="user", content="Continue"),
        ]
        result = repair_message_sequence(messages)
        assert is_valid_message_sequence(result)
        # Orphaned tool removed, but valid pair preserved
        valid_tools = [m for m in result if m.role == "tool"]
        assert len(valid_tools) == 1
        assert valid_tools[0].tool_call_id == "call_1"

    def test_repair_multiple_orphans(self) -> None:
        """Test removing multiple orphaned tool messages."""
        messages = [
            Message(role="system", content="system"),
            Message(role="tool", content="o1", tool_call_id="c1"),  # Orphaned
            Message(role="user", content="hi"),
            Message(role="tool", content="o2", tool_call_id="c2"),  # Orphaned
            Message(role="assistant", content="hello"),
            Message(role="tool", content="o3", tool_call_id="c3"),  # Orphaned
        ]
        result = repair_message_sequence(messages)
        assert is_valid_message_sequence(result)
        assert not any(m.role == "tool" for m in result)

    def test_repair_tool_separated_by_user_message(self) -> None:
        """Test repair of tool messages separated from assistant by user msg."""
        messages = [
            Message(role="user", content="do it"),
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="call_1", name="tool", arguments={})],
            ),
            Message(role="user", content="interruption"),
            Message(role="tool", content="result", tool_call_id="call_1"),
        ]
        assert not is_valid_message_sequence(messages)

        result = repair_message_sequence(messages)
        assert is_valid_message_sequence(result)
        # Tool_calls should be stripped, orphaned tool removed
        assert not any(m.role == "tool" for m in result)
