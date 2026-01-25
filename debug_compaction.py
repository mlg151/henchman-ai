#!/usr/bin/env python3
"""Debug test for compaction issue."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from henchman.providers.base import Message, ToolCall
from henchman.utils.compaction import ContextCompactor

def test_problem_case():
    """Test the specific case that's failing."""
    print("=== Debugging Compaction Issue ===\n")
    
    # This is the test case from test_compaction_validation_sequence_integrity
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
    
    print(f"Original messages ({len(messages)}):")
    for i, msg in enumerate(messages):
        print(f"  {i}: role={msg.role}, tool_calls={msg.tool_calls}, tool_call_id={msg.tool_call_id}")
    
    compactor = ContextCompactor(max_tokens=1000)
    
    # Test grouping
    sequences = compactor._group_into_sequences(messages)
    print(f"\nGrouped into {len(sequences)} sequences:")
    for i, seq in enumerate(sequences):
        print(f"  Sequence {i}: {seq}")
    
    # Test compaction
    compacted = compactor.compact(messages)
    print(f"\nCompacted messages ({len(compacted)}):")
    for i, msg in enumerate(compacted):
        print(f"  {i}: role={msg.role}, tool_calls={msg.tool_calls}, tool_call_id={msg.tool_call_id}")
    
    # Validate
    print("\n=== Validation ===")
    for i, msg in enumerate(compacted):
        if msg.role == "tool":
            print(f"  Tool message at index {i}:")
            if i == 0:
                print("    ERROR: No preceding message")
            else:
                prev = compacted[i-1]
                print(f"    Preceding: role={prev.role}, tool_calls={prev.tool_calls}")
                if prev.role != "assistant":
                    print(f"    ERROR: Doesn't follow assistant (follows {prev.role})")
                elif not prev.tool_calls:
                    print("    ERROR: Preceding assistant has no tool_calls")
                else:
                    tool_ids = [tc.id for tc in prev.tool_calls]
                    if msg.tool_call_id not in tool_ids:
                        print(f"    ERROR: Tool call ID {msg.tool_call_id} not in {tool_ids}")
                    else:
                        print("    OK")

if __name__ == "__main__":
    test_problem_case()
