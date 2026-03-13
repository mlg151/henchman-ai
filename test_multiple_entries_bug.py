#!/usr/bin/env python3
"""Test bug with multiple entries for same file."""

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

def test_multiple_entries_same_file():
    """Test that should_read_file finds the correct entry when same file appears multiple times."""
    memory = WorkingMemory(current_task="Test")
    
    # Add two entries for same file (shouldn't happen but could)
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "First read", "1-50"))
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Second read", "60-100"))
    
    print("Test: Same file read twice with different ranges")
    print(f"  recent_files length: {len(memory.recent_files)}")
    print(f"  First entry lines_read: {memory.recent_files[0].lines_read}")
    print(f"  Second entry lines_read: {memory.recent_files[1].lines_read}")
    
    # Ask for lines that are in SECOND (more recent) read but not first
    should_read, reason = memory.should_read_file("/test/file.py", 70, 90)
    print(f"\n  Ask for lines 70-90 (in second read 60-100):")
    print(f"    should_read: {should_read} (expected: False - lines 70-90 are in 60-100)")
    print(f"    reason: {reason}")
    
    # Bug: finds FIRST entry (1-50), checks 70-90 against 1-50
    # 70 >= 1 and 90 <= 50 → 70 >= 1 true, 90 <= 50 false → returns True
    # But should return False because 70-90 is in 60-100!
    
    # Ask for lines that are in FIRST read
    should_read2, reason2 = memory.should_read_file("/test/file.py", 10, 30)
    print(f"\n  Ask for lines 10-30 (in first read 1-50):")
    print(f"    should_read: {should_read2} (expected: False - lines 10-30 are in 1-50)")
    print(f"    reason: {reason2}")
    
    # This works: finds first entry, checks 10-30 against 1-50, returns False
    
    # Now prune to keep only most recent entry
    memory.prune_recent_files(max_entries=1)
    print(f"\n  After pruning to keep only 1 entry:")
    print(f"    recent_files length: {len(memory.recent_files)}")
    print(f"    Remaining entry lines_read: {memory.recent_files[0].lines_read}")
    
    # Now ask for lines 10-30 again
    should_read3, reason3 = memory.should_read_file("/test/file.py", 10, 30)
    print(f"\n  After pruning, ask for lines 10-30 (were in pruned entry):")
    print(f"    should_read: {should_read3} (expected: True - entry was pruned)")
    print(f"    reason: {reason3}")
    
    # File not found in recent_files (pruned), returns True
    
    print("\nConclusion: Bug! should_read_file finds FIRST matching entry, not MOST RECENT.")
    print("If same file appears multiple times, we should check against most recent entry.")
    print("Or better: update existing entry instead of adding duplicate.")

if __name__ == "__main__":
    test_multiple_entries_same_file()