"""Test for the bug in should_read_file when file was read fully but invalid line numbers are provided."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

def test_should_read_file_full_with_invalid_line_numbers():
    """Test that invalid line numbers are validated BEFORE checking if file was read fully.
    
    BUG: When file was read "full" and caller provides invalid line numbers (e.g., start=0),
    should_read_file returns False (don't read) instead of True with error about invalid line numbers.
    Invalid line number validation should happen first.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Add entry with file read fully
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with start=0 (invalid, lines are 1-indexed)
    should_read, reason = memory.should_read_file("/test/file.py", 0, 10)
    
    # BUG: Currently returns False, "File already read (full)"
    # Should return True with error about invalid line numbers
    print(f"should_read: {should_read}, reason: {reason}")
    
    assert should_read is True, (
        f"Invalid line number start=0 should return True with error, "
        f"not False (file was read fully). Got: {should_read}, reason: {reason}"
    )
    assert "invalid" in reason.lower() or "positive" in reason.lower(), (
        f"Should report invalid line number error, not 'File already read (full)'. "
        f"Got reason: {reason}"
    )
    
    # Test with start=-5 (invalid negative)
    should_read2, reason2 = memory.should_read_file("/test/file.py", -5, 10)
    assert should_read2 is True
    assert "invalid" in reason2.lower() or "positive" in reason2.lower()
    
    # Test with start=1, end=0 (invalid, start > end)
    should_read3, reason3 = memory.should_read_file("/test/file.py", 1, 0)
    assert should_read3 is True
    assert "invalid" in reason3.lower() or "start.*>.*end" in reason3.lower()
    
    # Valid line numbers should still return False (file read fully)
    should_read4, reason4 = memory.should_read_file("/test/file.py", 10, 50)
    assert should_read4 is False
    assert "already read" in reason4.lower()

if __name__ == "__main__":
    test_should_read_file_full_with_invalid_line_numbers()
    print("\nTest demonstrates the bug!")