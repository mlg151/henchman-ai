#!/usr/bin/env python3
"""Verify the bug fix for lines_read=None vs lines_read="" consistency."""

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

def main():
    print("Verifying bug fix: lines_read=None vs lines_read=\"\" consistency")
    print("=" * 60)
    
    # Test 1: lines_read=None
    print("\nTest 1: lines_read=None")
    memory1 = WorkingMemory(current_task="Test")
    entry1 = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read=None,
        key_insights=[],
    )
    memory1.add_recent_file(entry1)
    should_read1, reason1 = memory1.should_read_file("/test/file.py")
    print(f"  Result: should_read={should_read1}, reason='{reason1}'")
    
    # Test 2: lines_read=""
    print("\nTest 2: lines_read=\"\"")
    memory2 = WorkingMemory(current_task="Test")
    entry2 = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="",
        key_insights=[],
    )
    memory2.add_recent_file(entry2)
    should_read2, reason2 = memory2.should_read_file("/test/file.py")
    print(f"  Result: should_read={should_read2}, reason='{reason2}'")
    
    # Check consistency
    print("\n" + "=" * 60)
    print("Consistency check:")
    print(f"  Both return True: {should_read1 == should_read2 == True}")
    print(f"  Same reason: {reason1 == reason2}")
    
    if should_read1 == should_read2 == True and reason1 == reason2:
        print("✓ BUG FIXED: lines_read=None and lines_read=\"\" are now consistent!")
        print(f"  Both return: '{reason1}'")
    else:
        print("✗ BUG STILL EXISTS:")
        print(f"  lines_read=None: '{reason1}'")
        print(f"  lines_read=\"\": '{reason2}'")
    
    # Additional test: mixed entries
    print("\n" + "=" * 60)
    print("Additional test: Mixed entries (None and empty string)")
    memory3 = WorkingMemory(current_task="Test")
    entry3a = WorkingMemoryEntry("/test/file.py", "Test 1", None, [])
    entry3b = WorkingMemoryEntry("/test/file.py", "Test 2", "", [])
    memory3.add_recent_file(entry3a)
    memory3.add_recent_file(entry3b)
    should_read3, reason3 = memory3.should_read_file("/test/file.py")
    print(f"  Result: should_read={should_read3}, reason='{reason3}'")
    
    if "no lines have been read" in reason3.lower():
        print("✓ Correct: Mixed None and empty string entries treated as 'no lines read'")
    else:
        print(f"✗ Unexpected: '{reason3}'")

if __name__ == "__main__":
    main()