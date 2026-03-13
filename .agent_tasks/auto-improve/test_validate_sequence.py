"""Comprehensive tests for validate_compacted_sequence function."""

from henchman.providers.base import Message, ToolCall
from henchman.utils.intelligent_context import SequenceValidator


def test_validate_compacted_sequence_empty():
    """Test empty message list."""
    assert SequenceValidator.validate_compacted_sequence([]) is True


def test_validate_compacted_sequence_single_system():
    """Test single system message."""
    messages = [Message(role="system", content="You are a helpful assistant")]
    assert SequenceValidator.validate_compacted_sequence(messages) is True


def test_validate_compacted_sequence_single_user():
    """Test single user message."""
    messages = [Message(role="user", content="Hello")]
    assert SequenceValidator.validate_compacted_sequence(messages) is True


def test_validate_compacted_sequence_single_assistant():
    """Test single assistant message."""
    messages = [Message(role="assistant", content="Hi there")]
    assert SequenceValidator.validate_compacted_sequence(messages) is True


def test_validate_compacted_sequence_single_tool():
    """Test single tool message (invalid)."""
    messages = [Message(role="tool", content="Result", tool_call_id="tc1")]
    assert SequenceValidator.validate_compacted_sequence(messages) is False


def test_validate_compacted_sequence_valid_tool_sequence():
    """Test valid tool call sequence."""
    tool_call = ToolCall(id="tc1", name="test_tool", arguments={})
    messages = [
        Message(role="user", content="Use tool"),
        Message(role="assistant", content="Using tool", tool_calls=[tool_call]),
        Message(role="tool", content="Tool result", tool_call_id="tc1"),
    ]
    assert SequenceValidator.validate_compacted_sequence(messages) is True


def test_validate_compacted_sequence_tool_without_preceding_assistant():
    """Test tool message without preceding assistant."""
    messages = [
        Message(role="user", content="Hello"),
        Message(role="tool", content="Result", tool_call_id="tc1"),
    ]
    assert SequenceValidator.validate_compacted_sequence(messages) is False


def test_validate_compacted_sequence_tool_after_user_fails():
    """Test tool message directly after user (no tool calls)."""
    messages = [
        Message(role="user", content="Hello"),
        Message(role="assistant", content="I'll help"),  # No tool_calls
        Message(role="tool", content="Result", tool_call_id="tc1"),
    ]
    assert SequenceValidator.validate_compacted_sequence(messages) is False


def test_validate_compacted_sequence_wrong_tool_id():
    """Test tool with mismatched ID."""
    tool_call = ToolCall(id="tc1", name="test_tool", arguments={})
    messages = [
        Message(role="assistant", content="Using tool", tool_calls=[tool_call]),
        Message(role="tool", content="Result", tool_call_id="wrong_id"),
    ]
    assert SequenceValidator.validate_compacted_sequence(messages) is False


def test_validate_compacted_sequence_multiple_tool_calls():
    """Test multiple tool calls with correct IDs."""
    tool_call1 = ToolCall(id="tc1", name="tool1", arguments={})
    tool_call2 = ToolCall(id="tc2", name="tool2", arguments={})
    messages = [
        Message(role="assistant", content="Using tools", tool_calls=[tool_call1, tool_call2]),
        Message(role="tool", content="Result 1", tool_call_id="tc1"),
        Message(role="tool", content="Result 2", tool_call_id="tc2"),
    ]
    assert SequenceValidator.validate_compacted_sequence(messages) is True


def test_validate_compacted_sequence_assistant_after_assistant_valid():
    """Test assistant after assistant when first has tool calls."""
    tool_call = ToolCall(id="tc1", name="test_tool", arguments={})
    messages = [
        Message(role="assistant", content="Using tool", tool_calls=[tool_call]),
        Message(role="tool", content="Result", tool_call_id="tc1"),
        Message(role="assistant", content="Continuing after tool"),
    ]
    assert SequenceValidator.validate_compacted_sequence(messages) is True


def test_validate_compacted_sequence_assistant_after_assistant_invalid():
    """Test assistant after assistant when first has no tool calls."""
    messages = [
        Message(role="assistant", content="First response"),
        Message(role="assistant", content="Second response without user"),
    ]
    assert SequenceValidator.validate_compacted_sequence(messages) is False


def test_validate_compacted_sequence_assistant_after_system():
    """Test assistant after system (valid in system prompt scenario)."""
    messages = [
        Message(role="system", content="You are helpful"),
        Message(role="assistant", content="Hello"),
    ]
    assert SequenceValidator.validate_compacted_sequence(messages) is True


def test_validate_compacted_sequence_empty_system_content():
    """Test system message with empty content."""
    messages = [
        Message(role="system", content=""),
        Message(role="user", content="Hello"),
    ]
    assert SequenceValidator.validate_compacted_sequence(messages) is False


def test_validate_compacted_sequence_whitespace_system_content():
    """Test system message with only whitespace."""
    messages = [
        Message(role="system", content="   \n  \t  "),
        Message(role="user", content="Hello"),
    ]
    assert SequenceValidator.validate_compacted_sequence(messages) is False


def test_validate_compacted_sequence_duplicate_consecutive_messages():
    """Test duplicate consecutive messages (compression artifact)."""
    messages = [
        Message(role="user", content="Hello"),
        Message(role="user", content="Hello"),
    ]
    assert SequenceValidator.validate_compacted_sequence(messages) is False


def test_validate_compacted_sequence_duplicate_with_tool_calls():
    """Test duplicate roles with tool calls (should be invalid due to orphaned tool calls)."""
    tool_call = ToolCall(id="tc1", name="test_tool", arguments={})
    messages = [
        Message(role="assistant", content="Using tool", tool_calls=[tool_call]),
        Message(role="assistant", content="Using tool", tool_calls=[tool_call]),
    ]
    # Should be invalid because first assistant's tool calls are orphaned
    # (no tool response before another assistant message)
    assert SequenceValidator.validate_compacted_sequence(messages) is False


def test_validate_compacted_sequence_duplicate_with_different_content():
    """Test consecutive messages with same role but different content."""
    messages = [
        Message(role="user", content="Hello"),
        Message(role="user", content="Goodbye"),
    ]
    assert SequenceValidator.validate_compacted_sequence(messages) is True


def test_validate_compacted_sequence_complex_valid_sequence():
    """Test complex valid sequence."""
    tool_call = ToolCall(id="tc1", name="read_file", arguments={})
    messages = [
        Message(role="system", content="You are a coding assistant"),
        Message(role="user", content="Read file.txt"),
        Message(role="assistant", content="Reading file", tool_calls=[tool_call]),
        Message(role="tool", content="File content", tool_call_id="tc1"),
        Message(role="user", content="Now write to file"),
        Message(role="assistant", content="Writing file"),
    ]
    assert SequenceValidator.validate_compacted_sequence(messages) is True


def test_validate_compacted_sequence_orphaned_tool_calls():
    """Test assistant with tool_calls but no tool response."""
    tool_call = ToolCall(id="tc1", name="test_tool", arguments={})
    messages = [
        Message(role="user", content="Use tool"),
        Message(role="assistant", content="Using tool", tool_calls=[tool_call]),
        Message(role="user", content="What happened?"),
    ]
    assert SequenceValidator.validate_compacted_sequence(messages) is False


def test_validate_compacted_sequence_mixed_case_roles():
    """Test that role case doesn't matter (should be lowercase in practice)."""
    # Note: In practice, roles should be lowercase, but let's test robustness
    messages = [
        Message(role="SYSTEM", content="You are helpful"),
        Message(role="USER", content="Hello"),
        Message(role="ASSISTANT", content="Hi"),
    ]
    # This should fail because roles are not lowercase
    assert SequenceValidator.validate_compacted_sequence(messages) is False


def test_validate_compacted_sequence_null_content():
    """Test messages with None content."""
    messages = [
        Message(role="user", content=None),
        Message(role="assistant", content="Response"),
    ]
    assert SequenceValidator.validate_compacted_sequence(messages) is True


def test_validate_compacted_sequence_whitespace_content():
    """Test messages with whitespace content."""
    messages = [
        Message(role="user", content="   "),
        Message(role="assistant", content="Response"),
    ]
    assert SequenceValidator.validate_compacted_sequence(messages) is True