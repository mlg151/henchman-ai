#!/usr/bin/env python3
"""Test to demonstrate the bug in should_read_file when start=X, end=None."""

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

def test_bug_start_in_gap():
    """Test that should_read_file incorrectly returns True when start is in a gap between read ranges."""
    memory = WorkingMemory(current_task="Test")
    
    # Add two non-overlapping reads: lines 1-50 and lines 80-100
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "First read", "1-50"))
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Second read", "80-100"))
    
    # Want to read from line 70 to EOF
    # Line 70 is in the gap between 50 and 80 (not read)
    # So should return True (need to read)
    should_read, reason = memory.should_read_file("/test/file.py", start=70)
    
    print(f"Test 1 - start=70 (in gap): should_read={should_read}, reason={reason}")
    
    # Current buggy behavior: 
    # - max_read_end = 100
    # - start=70 <= max_read_end=100 → True
    # - Returns True with message "May need to read lines beyond 100"
    # But the real issue is that line 70 hasn't been read at all!
    
    # Actually, the current code returns True, which is correct (we need to read).
    # But the reason is wrong - it says "May need to read lines beyond 100"
    # when the real issue is "Line 70 hasn't been read (it's in a gap)"
    
    # Test 2: start=90 (within second range 80-100)
    # Should return True because we might need to read beyond 100
    should_read2, reason2 = memory.should_read_file("/test/file.py", start=90)
    print(f"Test 2 - start=90 (in range 80-100): should_read={should_read2}, reason={reason2}")
    
    # Test 3: start=30 (within first range 1-50)
    # Should return True because we might need to read beyond 100
    should_read3, reason3 = memory.should_read_file("/test/file.py", start=30)
    print(f"Test 3 - start=30 (in range 1-50): should_read={should_read3}, reason={reason3}")

def test_bug_start_none_end_y():
    """Test that should_read_file incorrectly returns True when end=Y and start=None."""
    memory = WorkingMemory(current_task="Test")
    
    # Add two non-overlapping reads: lines 1-50 and lines 80-100
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "First read", "1-50"))
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Second read", "80-100"))
    
    # Want to read from beginning to line 70
    # Lines 1-50 have been read, lines 51-70 haven't
    # So should return True (need to read)
    should_read, reason = memory.should_read_file("/test/file.py", end=70)
    
    print(f"\nTest 4 - end=70 (gap at 51-70): should_read={should_read}, reason={reason}")
    
    # Current buggy behavior:
    # - min_read_start = 1
    # - end=70 >= min_read_start=1 → True
    # - Returns True with message "May need to read lines before 1"
    # But lines 1-50 HAVE been read! The issue is lines 51-70.

if __name__ == "__main__":
    test_bug_start_in_gap()
    test_bug_start_none_end_y()