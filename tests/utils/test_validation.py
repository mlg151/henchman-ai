"""Test message sequence validation."""

import sys
import os

# Add src to path so we can import henchman
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import pytest

from henchman.providers.base import Message, ToolCall
from henchman.utils.validation import (
    validate_message_sequence,
    is_valid_message_sequence,
    format_message_sequence_for_debug,
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
                tool_calls=[ToolCall(id="call_1", name="tool", arguments={})]
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
                ]
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
        
        with pytest.raises(ValueError, match="Tool message at index 0 has no preceding message"):
            validate_message_sequence(messages)
        
        assert is_valid_message_sequence(messages) is False
    
    def test_invalid_tool_without_tool_calls(self) -> None:
        """Test invalid: tool message follows assistant without tool_calls."""
        messages = [
            Message(role="user", content="test"),
            Message(role="assistant", content="response"),  # No tool_calls!
            Message(role="tool", content="result", tool_call_id="call_1"),
        ]
        
        with pytest.raises(ValueError, match="doesn't follow any assistant message with tool_calls"):
            validate_message_sequence(messages)
        
        assert is_valid_message_sequence(messages) is False
    
    def test_invalid_mismatched_tool_call_id(self) -> None:
        """Test invalid: tool call ID doesn't match."""
        messages = [
            Message(role="user", content="test"),
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="call_1", name="tool", arguments={})]
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
                ]
            ),
            Message(role="tool", content="result1", tool_call_id="call_1"),
            # Missing response for call_2!
        ]
        
        with pytest.raises(ValueError, match="has tool calls without responses"):
            validate_message_sequence(messages)
        
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
                tool_calls=[ToolCall(id="call_a", name="task", arguments={})]
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
                ]
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
                tool_calls=[ToolCall(id="call_1", name="tool", arguments={})]
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
        messages = []
        
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

