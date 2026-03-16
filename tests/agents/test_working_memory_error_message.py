"""Test for error message bug in working_memory.py."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_should_read_file_invalid_range_error_message():
    """Test that error message for invalid line range (start > end) is clear.
    
    BUG: Current message says "treating as new read" which is misleading.
    Should just report the error without suggesting a file reading decision.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with start > end
    should_read, reason = memory.should_read_file("/test/file.py", 10, 5)
    
    # Should return True (invalid input)
    assert should_read is True
    
    # BUG: Message contains misleading "treating as new read"
    # Should NOT contain this phrase
    assert "treating as new read" not in reason, (
        f"Error message should not contain 'treating as new read' as it's misleading. "
        f"Got: {reason}"
    )
    
    # Should clearly indicate the error
    assert "Invalid line range" in reason
    assert "start (10) > end (5)" in reason
    
    # Alternative: Could say "line numbers must be in ascending order" or similar
    print(f"Test passes with clear error message: {reason}")


def test_should_read_file_invalid_line_numbers_error_messages():
    """Test error messages for various invalid line numbers."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-50"))
    
    # Test with start=0 (invalid)
    should_read, reason = memory.should_read_file("/test/file.py", 0, 10)
    assert should_read is True
    assert "Invalid line number" in reason
    assert "start must be positive" in reason
    assert "got start=0" in reason
    
    # Test with end=0 (invalid)
    should_read, reason = memory.should_read_file("/test/file.py", 1, 0)
    assert should_read is True
    assert "Invalid line number" in reason
    # Error message: end must be positive (1-indexed)
    assert "end must be positive" in reason
    assert "got end=0" in reason
    
    # Test with start=-5 (invalid)
    should_read, reason = memory.should_read_file("/test/file.py", -5, 10)
    assert should_read is True
    assert "Invalid line number" in reason
    assert "start must be positive" in reason
    assert "got start=-5" in reason
    
    print("All error message tests pass")


if __name__ == "__main__":
    test_should_read_file_invalid_range_error_message()
    test_should_read_file_invalid_line_numbers_error_messages()
    print("\nAll tests pass (or fail, showing the bug)")