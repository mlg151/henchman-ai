#!/usr/bin/env python3
"""Test context compaction with tool call sequences."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.henchman.providers.base import Message, ToolCall
from src.henchman.utils.compaction import ContextCompactor

def test_compaction_preserves_tool_sequence():
    """Test that compaction preserves tool call → tool message sequences."""
    
    print("=== Testing Context Compaction with Tool Sequences ===\n")
    
    # Create a valid tool call sequence
    messages = [
        Message(role="system", content="You are a helpful assistant."),
        Message(role="user", content="List files in /tmp"),
        Message(
            role="assistant",
            content="",
            tool_calls=[ToolCall(id="call_123", name="ls", arguments={"path": "/tmp"})]
        ),
        Message(role="tool", content="file1.txt\nfile2.txt", tool_call_id="call_123"),
        Message(role="assistant", content="Here are the files..."),
    ]
    
    print(f"Original messages: {len(messages)}")
    for i, msg in enumerate(messages):
        print(f"  {i}: role={msg.role}, content_length={len(msg.content or '')}, "
              f"tool_calls={msg.tool_calls is not None}, tool_call_id={msg.tool_call_id}")
    
    # Test compaction with high token limit (should preserve all)
    compactor = ContextCompactor(max_tokens=10000)
    compacted = compactor.compact(messages)
    
    print(f"\nCompacted messages: {len(compacted)}")
    for i, msg in enumerate(compacted):
        print(f"  {i}: role={msg.role}, content_length={len(msg.content or '')}, "
              f"tool_calls={msg.tool_calls is not None}, tool_call_id={msg.tool_call_id}")
    
    # Check if sequence is preserved
    print("\n=== Sequence Validation ===")
    
    # Check that tool messages follow assistant messages with tool_calls
    for i, msg in enumerate(compacted):
        if msg.role == "tool":
            if i == 0:
                print(f"  ERROR: Tool message at index {i} has no preceding message")
                return False
            
            prev_msg = compacted[i-1]
            if prev_msg.role != "assistant" or not prev_msg.tool_calls:
                print(f"  ERROR: Tool message at index {i} doesn't follow assistant with tool_calls")
                print(f"    Previous message: role={prev_msg.role}, tool_calls={prev_msg.tool_calls is not None}")
                return False
            
            # Check tool call ID matches
            tool_call_ids = [tc.id for tc in prev_msg.tool_calls]
            if msg.tool_call_id not in tool_call_ids:
                print(f"  ERROR: Tool call ID mismatch")
                print(f"    Tool message tool_call_id: {msg.tool_call_id}")
                print(f"    Assistant tool_call_ids: {tool_call_ids}")
                return False
    
    print("  ✓ Tool call sequences preserved correctly")
    return True

def test_compaction_with_multiple_tools():
    """Test compaction with multiple tool calls."""
    
    print("\n\n=== Testing Compaction with Multiple Tool Calls ===\n")
    
    messages = [
        Message(role="user", content="Do several things"),
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
        Message(role="assistant", content="All done"),
    ]
    
    print(f"Original messages: {len(messages)}")
    
    compactor = ContextCompactor(max_tokens=10000)
    compacted = compactor.compact(messages)
    
    print(f"Compacted messages: {len(compacted)}")
    
    # Validate
    valid = True
    for i, msg in enumerate(compacted):
        if msg.role == "tool":
            if i == 0 or compacted[i-1].role != "assistant":
                print(f"  ERROR: Tool message at index {i} out of sequence")
                valid = False
    
    if valid:
        print("  ✓ Multiple tool sequence preserved")
    return valid

if __name__ == "__main__":
    test1 = test_compaction_preserves_tool_sequence()
    test2 = test_compaction_with_multiple_tools()
    
    print("\n=== Summary ===")
    if test1 and test2:
        print("✓ All compaction tests passed")
    else:
        print("✗ Some compaction tests failed")
        print("  This could be causing the 400 error if compaction breaks tool sequences")
