"""Test for missing return bug in should_read_file."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_should_read_file_start_none_end_not_none():
    """Test should_read_file with start=None, end=100.
    
    This tests the bug mentioned in test_memory_should_read_file_missing_return_bug.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Add a file with no line ranges (empty string)
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", ""))
    
    # Test with start=None, end=100
    # This should return True because no lines have been read
    should_read, reason = memory.should_read_file("/test/file.py", None, 100)
    print(f"should_read={should_read}, reason={reason}")
    assert should_read is True
    assert "No lines have been read" in reason
    
    # Now add a file with some line ranges
    memory2 = WorkingMemory(current_task="Test")
    memory2.add_recent_file(WorkingMemoryEntry("/test/file2.py", "Test", "1-50"))
    
    # Test with start=None, end=100 (end is beyond read range)
    should_read, reason = memory2.should_read_file("/test/file2.py", None, 100)
    print(f"should_read={should_read}, reason={reason}")
    assert should_read is True
    # Current message: "May need to read lines before 1"
    assert "read lines before" in reason or "beyond last read line" in reason
    
    # Test with start=None, end=25 (end is within read range)
    should_read, reason = memory2.should_read_file("/test/file2.py", None, 25)
    print(f"should_read={should_read}, reason={reason}")
    assert should_read is True
    assert "May need to read lines before" in reason
    
    # Test with start=None, end=0 (invalid line number)
    should_read, reason = memory2.should_read_file("/test/file2.py", None, 0)
    print(f"should_read={should_read}, reason={reason}")
    assert should_read is True
    assert "must be positive" in reason or "must be -1 (for EOF) or positive" in reason
    
    # Test with start=None, end=-1 (EOF)
    should_read, reason = memory2.should_read_file("/test/file2.py", None, -1)
    print(f"should_read={should_read}, reason={reason}")
    # end=-1 gets converted to None, so we're reading entire file
    # File has only lines 1-50 read, not full, so should return True
    assert should_read is True
    # Accept various messages about file not being fully read
    assert ("File not fully read" in reason or 
            "May need to read lines before" in reason or
            "Cannot determine if file fully read" in reason or
            "file size unknown" in reason or
            "File has been partially read" in reason)


def test_should_read_file_edge_cases():
    """Test edge cases that might cause missing return."""
    memory = WorkingMemory(current_task="Test")
    
    # Add file with overlapping ranges
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-10,5-15"))
    # merged_ranges would be [LineRange(1, 15)]
    
    # Test with start=None, end=20 (beyond merged range)
    should_read, reason = memory.should_read_file("/test/file.py", None, 20)
    print(f"Case 1: should_read={should_read}, reason={reason}")
    assert should_read is True
    # Current message: "May need to read lines before 1"
    assert "read lines before" in reason or "beyond last read line" in reason
    
    # Test with start=None, end=0 (before first range)
    should_read, reason = memory.should_read_file("/test/file.py", None, 0)
    print(f"Case 2: should_read={should_read}, reason={reason}")
    assert should_read is True
    assert "must be positive" in reason or "must be -1 (for EOF) or positive" in reason
    
    # Test with start=None, end=8 (within merged range)
    should_read, reason = memory.should_read_file("/test/file.py", None, 8)
    print(f"Case 3: should_read={should_read}, reason={reason}")
    assert should_read is True
    assert "May need to read lines before" in reason


if __name__ == "__main__":
    test_should_read_file_start_none_end_not_none()
    print("\ntest_should_read_file_start_none_end_not_none passed")
    
    test_should_read_file_edge_cases()
    print("\ntest_should_read_file_edge_cases passed")
    
    print("\nAll tests passed - checking if bug exists...")