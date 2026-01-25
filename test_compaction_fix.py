#!/usr/bin/env python3
"""Simple test to verify compaction fix."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from henchman.providers.base import Message, ToolCall
from henchman.utils.compaction import ContextCompactor

def test_basic_tool_sequence():
    """Test basic tool sequence preservation."""
    print("=== Testing Basic Tool Sequence ===\n")
    
    messages = [
        Message(role="user", content="test"),
        Message(
            role="assistant",
            content="",
            tool_calls=[
                ToolCall(id="1", name="t1", arguments={}),
                ToolCall(id="2", name="t2", arguments={}),
            ]
        ),
        Message(role="tool", content="r1", tool_call_id="1"),
        Message(role="tool", content="r2", tool_call_id="2"),
    ]
    
    compactor = ContextCompactor(max_tokens=1000)
    compacted = compactor.compact(messages)
    
    print(f"Original: {len(messages)} messages")
    print(f"Compacted: {len(compacted)} messages")
    
    # Should preserve all messages
    assert len(compacted) == 4, f"Expected 4 messages, got {len(compacted)}"
    
    # Check sequence
    print("\nChecking sequence...")
    for i, msg in enumerate(compacted):
        if msg.role == "tool":
            print(f"  Tool at index {i}:")
            assert i > 0, f"Tool at index {i} has no preceding message"
            prev = compacted[i-1]
            assert prev.role == "assistant", f"Tool at {i} doesn't follow assistant (follows {prev.role})"
            assert prev.tool_calls, f"Assistant at {i-1} has no tool_calls"
            assert msg.tool_call_id in [tc.id for tc in prev.tool_calls],                 f"Tool call ID {msg.tool_call_id} not in assistant's tool calls"
            print(f"    OK - follows assistant with matching tool call")
    
    print("\n✓ Test passed!")

def test_with_pruning():
    """Test that tool sequences are preserved when pruning occurs."""
    print("\n=== Testing With Pruning ===")
    
    # Create many messages to force pruning
    messages = [
        Message(role="system", content="System prompt"),
        Message(role="user", content="Old message 1"),
        Message(role="assistant", content="Old response 1"),
        Message(role="user", content="Old message 2"),
        Message(role="assistant", content="Old response 2"),
        # Recent tool sequence
        Message(role="user", content="Do task"),
        Message(
            role="assistant",
            content="",
            tool_calls=[ToolCall(id="call_1", name="task", arguments={})]
        ),
        Message(role="tool", content="result", tool_call_id="call_1"),
        Message(role="assistant", content="Task done"),
    ]
    
    # Small token limit to force pruning
    compactor = ContextCompactor(max_tokens=50)
    compacted = compactor.compact(messages)
    
    print(f"Original: {len(messages)} messages")
    print(f"Compacted: {len(compacted)} messages")
    
    # Validate the compacted sequence
    print("\nValidating compacted sequence...")
    for i, msg in enumerate(compacted):
        if msg.role == "tool":
            print(f"  Found tool at index {i}")
            assert i > 0, f"Tool at index {i} has no preceding message"
            prev = compacted[i-1]
            assert prev.role == "assistant", f"Tool at {i} doesn't follow assistant"
            assert prev.tool_calls, f"Assistant at {i-1} has no tool_calls"
            print(f"    OK - follows assistant with tool_calls")
    
    print("\n✓ Test passed!")

if __name__ == "__main__":
    test_basic_tool_sequence()
    test_with_pruning()
    print("\n=== All tests passed! ===")
