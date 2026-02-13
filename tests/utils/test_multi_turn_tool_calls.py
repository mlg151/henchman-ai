"""Test for multi-turn tool call ID matching bug."""

import pytest

from henchman.providers.base import Message, ToolCall
from henchman.utils.validation import validate_message_sequence


class TestMultiTurnToolCalls:
    """Tests for multi-turn tool call ID validation."""

    def test_multiple_tool_call_rounds(self):
        """Test that tool results match their correct assistant messages in multi-turn."""
        # Simulate a multi-turn conversation with multiple tool-calling rounds
        messages = [
            Message(role="system", content="You are helpful"),
            Message(role="user", content="First request"),
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="call_1", name="read_file", arguments={})],
            ),
            Message(role="tool", content="file content", tool_call_id="call_1"),
            Message(role="assistant", content="I read the file. What next?"),
            Message(role="user", content="Now write a file"),
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="call_2", name="write_file", arguments={})],
            ),
            Message(role="tool", content="file written", tool_call_id="call_2"),
            Message(role="assistant", content="Done writing."),
            Message(role="user", content="Do another thing"),
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="call_3", name="shell", arguments={})],
            ),
            Message(role="tool", content="shell output", tool_call_id="call_3"),
        ]

        # This should not raise - each tool result matches its correct assistant
        validate_message_sequence(messages)

    def test_wrong_tool_call_id_detected(self):
        """Test that mismatched tool call IDs are detected."""
        messages = [
            Message(role="user", content="Request"),
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="call_A", name="tool1", arguments={})],
            ),
            Message(role="tool", content="result", tool_call_id="call_B"),  # Wrong ID!
        ]

        with pytest.raises(ValueError, match="doesn't match"):
            validate_message_sequence(messages)

    def test_multiple_tool_calls_same_assistant(self):
        """Test multiple tool calls in single assistant message."""
        messages = [
            Message(role="user", content="Do two things"),
            Message(
                role="assistant",
                content="",
                tool_calls=[
                    ToolCall(id="call_X", name="tool1", arguments={}),
                    ToolCall(id="call_Y", name="tool2", arguments={}),
                ],
            ),
            Message(role="tool", content="result1", tool_call_id="call_X"),
            Message(role="tool", content="result2", tool_call_id="call_Y"),
            Message(role="assistant", content="Both done."),
        ]

        # Should not raise
        validate_message_sequence(messages)

    def test_tool_result_matches_wrong_round(self):
        """Test that tool results can't match an earlier round's tool calls."""
        messages = [
            Message(role="user", content="First"),
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="call_old", name="tool1", arguments={})],
            ),
            Message(role="tool", content="result1", tool_call_id="call_old"),
            Message(role="assistant", content="Done with first."),
            Message(role="user", content="Second"),
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="call_new", name="tool2", arguments={})],
            ),
            # This tool result uses the OLD tool call ID - should fail!
            Message(role="tool", content="result2", tool_call_id="call_old"),
        ]

        with pytest.raises(ValueError, match="doesn't match"):
            validate_message_sequence(messages)
