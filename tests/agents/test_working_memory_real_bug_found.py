"""Test for the real bug found in working_memory.py."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

def test_should_read_file_invalid_range_before_file_check():
    """Test that invalid line range validation happens BEFORE file check.
    
    BUG: When start > end (invalid range), method should report invalid range
    even if file is not in recent files. Currently returns "File not in recent files".
    """
    memory = WorkingMemory(current_task="Test")
    
    # File is NOT in recent files
    # Request invalid range: start=10, end=5 (start > end)
    should_read, reason = memory.should_read_file("/test/file.py", 10, 5)
    print(f"File not in recent files, start=10, end=5: should_read={should_read}, reason={reason}")
    
    # Should return True with error about invalid range, NOT "File not in recent files"
    assert should_read is True, "Invalid range should return True (need to read)"
    assert "invalid" in reason.lower() or "ascending" in reason.lower() or "start" in reason.lower() and "end" in reason.lower(), (
        f"Should report invalid range error, not 'File not in recent files'. Got: {reason}"
    )
    
def test_should_read_file_invalid_range_with_file_in_recent_files():
    """Test invalid line range when file IS in recent files."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-100"))
    
    # File IS in recent files
    # Request invalid range: start=10, end=5 (start > end)
    should_read, reason = memory.should_read_file("/test/file.py", 10, 5)
    print(f"File in recent files, start=10, end=5: should_read={should_read}, reason={reason}")
    
    # Should return True with error about invalid range
    assert should_read is True, "Invalid range should return True (need to read)"
    assert "invalid" in reason.lower() or "ascending" in reason.lower() or "start" in reason.lower() and "end" in reason.lower(), (
        f"Should report invalid range error. Got: {reason}"
    )

def test_should_read_file_valid_range_file_not_in_recent_files():
    """Test valid line range when file is not in recent files."""
    memory = WorkingMemory(current_task="Test")
    
    # File is NOT in recent files
    # Request valid range: start=1, end=10
    should_read, reason = memory.should_read_file("/test/file.py", 1, 10)
    print(f"File not in recent files, start=1, end=10: should_read={should_read}, reason={reason}")
    
    # Should return True with "File not in recent files"
    assert should_read is True, "File not in recent files should return True"
    assert "not in recent" in reason.lower(), (
        f"Should report 'File not in recent files'. Got: {reason}"
    )

if __name__ == "__main__":
    test_should_read_file_invalid_range_before_file_check()
    test_should_read_file_invalid_range_with_file_in_recent_files()
    test_should_read_file_valid_range_file_not_in_recent_files()
    print("\nAll tests run")