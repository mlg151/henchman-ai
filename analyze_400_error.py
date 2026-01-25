#!/usr/bin/env python3
"""Test script to reproduce and understand the 400 error."""

import sys
import json
from pathlib import Path

# Add the project to the path
sys.path.insert(0, str(Path(__file__).parent))

from src.henchman.providers.base import Message, ToolCall, ToolDeclaration
from src.henchman.providers.openai_compat import OpenAICompatibleProvider
from src.henchman.providers.anthropic import AnthropicProvider

def test_message_sequences():
    """Test various message sequences that might cause the 400 error."""
    
    print("=== Testing Message Sequences ===\n")
    
    # Test 1: Valid sequence with tool calls
    print("Test 1: Valid tool call sequence")
    valid_sequence = [
        Message(role="user", content="List files in /tmp"),
        Message(
            role="assistant",
            content="",
            tool_calls=[ToolCall(id="call_123", name="ls", arguments={"path": "/tmp"})]
        ),
        Message(role="tool", content="file1.txt\nfile2.txt", tool_call_id="call_123"),
        Message(role="assistant", content="Here are the files...")
    ]
    print(f"  Sequence length: {len(valid_sequence)}")
    print(f"  Message 2 has tool_calls: {valid_sequence[1].tool_calls is not None}")
    print(f"  Message 3 has tool_call_id: {valid_sequence[2].tool_call_id}")
    print()
    
    # Test 2: Invalid sequence - tool message without preceding tool call
    print("Test 2: Invalid sequence - tool message without tool call")
    invalid_sequence = [
        Message(role="user", content="List files"),
        Message(role="tool", content="result", tool_call_id="call_123"),  # No preceding tool call!
    ]
    print(f"  Sequence length: {len(invalid_sequence)}")
    print(f"  Message 1 role: {invalid_sequence[0].role}")
    print(f"  Message 2 role: {invalid_sequence[1].role}, tool_call_id: {invalid_sequence[1].tool_call_id}")
    print()
    
    # Test 3: Invalid sequence - mismatched tool call ID
    print("Test 3: Invalid sequence - mismatched tool call ID")
    mismatched_sequence = [
        Message(role="user", content="List files"),
        Message(
            role="assistant",
            content="",
            tool_calls=[ToolCall(id="call_abc", name="ls", arguments={})]
        ),
        Message(role="tool", content="result", tool_call_id="call_xyz"),  # Wrong ID!
    ]
    print(f"  Sequence length: {len(mismatched_sequence)}")
    print(f"  Assistant tool call ID: {mismatched_sequence[1].tool_calls[0].id}")
    print(f"  Tool message tool_call_id: {mismatched_sequence[2].tool_call_id}")
    print()
    
    # Test 4: Assistant message with tool calls but no content
    print("Test 4: Assistant with tool calls, no content")
    assistant_no_content = Message(
        role="assistant",
        content="",  # Empty content
        tool_calls=[ToolCall(id="call_1", name="test", arguments={})]
    )
    print(f"  Content: '{assistant_no_content.content}'")
    print(f"  Has tool_calls: {assistant_no_content.tool_calls is not None}")
    print()
    
    # Test 5: Tool message with empty content
    print("Test 5: Tool message with empty content")
    tool_empty_content = Message(
        role="tool",
        content="",  # Empty content
        tool_call_id="call_1"
    )
    print(f"  Content: '{tool_empty_content.content}'")
    print(f"  tool_call_id: {tool_empty_content.tool_call_id}")
    print()

def test_provider_formatting():
    """Test how providers format different message types."""
    
    print("\n=== Testing Provider Message Formatting ===\n")
    
    # Create a mock tool declaration
    tool_decl = ToolDeclaration(
        name="test_tool",
        description="A test tool",
        parameters={
            "type": "object",
            "properties": {"input": {"type": "string"}},
            "required": ["input"]
        }
    )
    
    # Test OpenAI-compatible formatting
    print("OpenAI-Compatible Provider formatting:")
    
    # Create messages with various edge cases
    messages = [
        Message(role="user", content="Hello"),
        Message(
            role="assistant", 
            content="",
            tool_calls=[ToolCall(id="call_1", name="test_tool", arguments={"input": "test"})]
        ),
        Message(role="tool", content="result", tool_call_id="call_1"),
    ]
    
    print(f"  Number of messages: {len(messages)}")
    for i, msg in enumerate(messages):
        print(f"  Message {i}: role={msg.role}, content_length={len(msg.content or '')}, "
              f"tool_calls={msg.tool_calls is not None}, tool_call_id={msg.tool_call_id}")
    
    # Test Anthropic formatting
    print("\nAnthropic Provider formatting considerations:")
    print("  Note: Anthropic converts tool messages to user messages with 'tool_result' content")
    print("  This is a key difference from OpenAI's format")

def analyze_validation_logic():
    """Analyze the validation logic in providers."""
    
    print("\n=== Analyzing Validation Logic ===\n")
    
    print("OpenAI-Compatible Provider validation (lines 136-152):")
    print("  - Checks if messages list is empty")
    print("  - For each message:")
    print("    - tool/function messages can have empty content")
    print("    - assistant messages with tool calls can have empty content")
    print("    - all other messages must have non-empty content")
    
    print("\nAnthropic Provider validation (lines 173-189):")
    print("  - Same logic as OpenAI provider")
    
    print("\nPotential issues:")
    print("  1. System messages might need empty content check")
    print("  2. Tool messages with empty content might be valid in some cases")
    print("  3. The validation might be rejecting valid sequences")

if __name__ == "__main__":
    test_message_sequences()
    test_provider_formatting()
    analyze_validation_logic()
    
    print("\n=== Summary ===")
    print("The 400 error likely occurs when:")
    print("  1. A 'tool' role message appears without a preceding assistant message with tool_calls")
    print("  2. The tool_call_id in a tool message doesn't match any tool call ID")
    print("  3. The message sequence violates OpenAI's API expectations")
    print("\nCheck the Agent's message history to ensure proper sequencing.")
