#!/usr/bin/env python3
"""Test that demonstrates the bug."""

import sys
sys.path.insert(0, '/home/matthew/mlg-cli/src')

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

def test_should_read_file_finds_most_recent_entry():
    """Test that should_read_file should find MOST RECENT entry, not FIRST."""
    memory = WorkingMemory(current_task="Test")
    
    # Add two entries for same file (simulating file read at different times)
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "First read", "1-50"))
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Second read", "60-100"))
    
    # Ask for lines that are in SECOND (more recent) read
    should_read, reason = memory.should_read_file("/test/file.py", 70, 90)
    
    # BUG: Currently finds FIRST entry (1-50), checks 70-90 against 1-50
    # 70 >= 1 and 90 <= 50 → 70 >= 1 true, 90 <= 50 false → returns True
    # Should return False because 70-90 is in 60-100 (most recent read)
    
    print(f"Test: File read twice: first 1-50, then 60-100")
    print(f"Ask for lines 70-90 (in second read)")
    print(f"Current result: should_read={should_read}, reason='{reason}'")
    print(f"Expected: should_read=False (lines 70-90 are in most recent read 60-100)")
    
    if should_read:
        print("\n✓ Test FAILS as expected (bug reproduced)")
        return True  # Test fails (bug exists)
    else:
        print("\n✗ Test PASSES unexpectedly (bug might be fixed?)")
        return False  # Test passes (bug fixed)

def test_should_read_file_finds_most_recent_entry_2():
    """Another test case: most recent read is subset of earlier read."""
    memory = WorkingMemory(current_task="Test")
    
    # First read whole file, then read specific part
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "First read", "1-100"))
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Second read", "10-50"))
    
    # Ask for lines that were in first read but NOT in second (more recent) read
    should_read, reason = memory.should_read_file("/test/file.py", 60, 80)
    
    # Most recent read was 10-50, so lines 60-80 were NOT read recently
    # Should return True (need to read)
    
    print(f"\nTest: File read twice: first 1-100, then 10-50")
    print(f"Ask for lines 60-80 (in first read but not second)")
    print(f"Current result: should_read={should_read}, reason='{reason}'")
    print(f"Expected: should_read=True (lines 60-80 not in most recent read 10-50)")
    
    if not should_read:
        print("\n✓ Test FAILS as expected (bug reproduced)")
        return True  # Test fails (bug exists)
    else:
        print("\n✗ Test PASSES unexpectedly (bug might be fixed?)")
        return False  # Test passes (bug fixed)

if __name__ == "__main__":
    print("Running bug reproduction tests...")
    print("=" * 60)
    
    test1_fails = test_should_read_file_finds_most_recent_entry()
    test2_fails = test_should_read_file_finds_most_recent_entry_2()
    
    print("\n" + "=" * 60)
    if test1_fails or test2_fails:
        print("Summary: Bug confirmed! Tests fail as expected.")
        print("The bug is: should_read_file finds FIRST entry, not MOST RECENT.")
        sys.exit(0)  # Exit with success (tests failed as expected)
    else:
        print("Summary: All tests pass! Bug might already be fixed.")
        sys.exit(1)  # Exit with error (tests passed unexpectedly)