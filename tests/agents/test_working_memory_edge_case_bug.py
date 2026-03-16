"""Test for edge case bug in working_memory.py."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

def test_should_read_file_end_minus_one_with_start_none():
    """Test should_read_file with end=-1 and start=None.
    
    BUG: When end=-1 (read to EOF) and start=None (read from beginning),
    the validation at line 565 checks end != -1, but end gets converted
    to None at line 562, so end != -1 is True (None != -1).
    But end is not None is False, so validation doesn't happen.
    This is correct behavior.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-50"))
    
    # Test with start=None, end=-1 (read from beginning to EOF)
    should_read, reason = memory.should_read_file("/test/file.py", None, -1)
    print(f"start=None, end=-1: should_read={should_read}, reason={reason}")
    # Should say we need to read lines before 10
    
def test_should_read_file_end_minus_one_with_start_gt_end():
    """Test should_read_file with end=-1 and start > end.
    
    BUG: When end=-1 and start=10, the validation at line 565:
    if start is not None and end is not None and end != -1 and start > end:
    - start=10 (not None)
    - end=-1 (not None) 
    - end != -1 is False (because end = -1)
    - So validation doesn't happen, even though start > -1 is True!
    But start > -1 is always True for positive start, and that's valid
    (reading from line 10 to EOF).
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with start=10, end=-1 (read from line 10 to EOF)
    should_read, reason = memory.should_read_file("/test/file.py", 10, -1)
    print(f"start=10, end=-1: should_read={should_read}, reason={reason}")
    # File was read fully, so should return False
    
def test_should_read_file_end_minus_one_converted_to_none():
    """Test that end=-1 gets converted to None internally.
    
    This is correct behavior - end=-1 means "read to EOF", which
    is represented as None in the line range logic.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Add a file read with lines 10-50
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-50"))
    
    # Request to read from line 60 to EOF (end=-1)
    should_read, reason = memory.should_read_file("/test/file.py", 60, -1)
    print(f"start=60, end=-1: should_read={should_read}, reason={reason}")
    # Should return True (need to read lines 60+)
    
    # Request to read from line 5 to EOF (end=-1)
    should_read, reason = memory.should_read_file("/test/file.py", 5, -1)
    print(f"start=5, end=-1: should_read={should_read}, reason={reason}")
    # Should return True (need to read lines 5-9)

def test_should_read_file_validation_order_bug():
    """Test validation order bug.
    
    BUG: The validation for start > end happens AFTER end=-1 conversion.
    What if start=10, end=5 (start > end)? Validation should catch this.
    What if start=10, end=-1? end gets converted to None, then validation
    doesn't happen because end is None.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Test with start=10, end=5 (start > end) - should be invalid
    should_read, reason = memory.should_read_file("/test/file.py", 10, 5)
    print(f"start=10, end=5: should_read={should_read}, reason={reason}")
    assert should_read is True, "start > end should be invalid"
    assert "invalid" in reason.lower() or "ascending" in reason.lower(), (
        f"Should report invalid range. Got: {reason}"
    )
    
    # Test with start=10, end=-1 (valid - read from line 10 to EOF)
    should_read, reason = memory.should_read_file("/test/file.py", 10, -1)
    print(f"start=10, end=-1: should_read={should_read}, reason={reason}")
    # This is valid, so should_read could be True or False depending on file history

if __name__ == "__main__":
    test_should_read_file_end_minus_one_with_start_none()
    test_should_read_file_end_minus_one_with_start_gt_end()
    test_should_read_file_end_minus_one_converted_to_none()
    test_should_read_file_validation_order_bug()
    print("\nAll tests run")