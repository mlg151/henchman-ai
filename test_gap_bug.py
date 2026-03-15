#!/usr/bin/env python3
"""Test to demonstrate the bug in should_read_file gap checking logic."""

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

def test_bug_gap_checking():
    """Test that should_read_file has incorrect gap checking logic."""
    memory = WorkingMemory(current_task="Test")
    
    # Add two non-overlapping reads: lines 1-50 and lines 80-100
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "First read", "1-50"))
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Second read", "80-100"))
    
    # Test 1: Request lines 70-90
    # Lines 70-79 are in gap, 80-90 are in second range
    # Should return True (need to read lines 70-79)
    should_read, reason = memory.should_read_file("/test/file.py", start=70, end=90)
    print(f"Test 1 - lines 70-90 (starts in gap): should_read={should_read}, reason={reason}")
    
    # Test 2: Request lines 60-90  
    # Lines 60-79 are in gap, 80-90 are in second range
    # Should return True (need to read lines 60-79)
    should_read2, reason2 = memory.should_read_file("/test/file.py", start=60, end=90)
    print(f"Test 2 - lines 60-90 (starts in gap): should_read={should_read2}, reason={reason2}")
    
    # Test 3: Request lines 40-90
    # Lines 40-50 are in first range, 51-79 are in gap, 80-90 are in second range
    # Should return True (need to read lines 51-79)
    should_read3, reason3 = memory.should_read_file("/test/file.py", start=40, end=90)
    print(f"Test 3 - lines 40-90 (starts in first range, gap in middle): should_read={should_read3}, reason={reason3}")
    
    # Test 4: Request lines 30-40 (fully within first range)
    # Should return False (already read)
    should_read4, reason4 = memory.should_read_file("/test/file.py", start=30, end=40)
    print(f"Test 4 - lines 30-40 (fully within first range): should_read={should_read4}, reason={reason4}")
    
    # Test 5: Request lines 85-95 (partially within second range, partially beyond)
    # Lines 85-100 are in second range, 101-95 doesn't exist (end < start)
    # Actually end=95 < start=85? No, 95 > 85
    # Lines 85-95 are within 80-100
    # Should return False (already read)
    should_read5, reason5 = memory.should_read_file("/test/file.py", start=85, end=95)
    print(f"Test 5 - lines 85-95 (within second range): should_read={should_read5}, reason={reason5}")

if __name__ == "__main__":
    test_bug_gap_checking()