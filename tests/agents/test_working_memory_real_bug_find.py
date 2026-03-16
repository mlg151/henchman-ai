"""Test to find a real bug in working_memory.py."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry, LineRange


def test_line_range_creation_with_none():
    """Test that LineRange cannot be created with None values.
    
    BUG: LineRange(start: int, end: int) has type hints for int, but
    should_read_file creates LineRange(start, end) where start and end
    could be None if not properly validated.
    """
    # This should raise TypeError because start and end must be int
    with pytest.raises(TypeError):
        LineRange(None, 10)
    
    with pytest.raises(TypeError):
        LineRange(10, None)
    
    with pytest.raises(TypeError):
        LineRange(None, None)


def test_should_read_file_with_none_values():
    """Test should_read_file with None values for start/end.
    
    BUG: The method signature says start: int | None, end: int | None,
    but the validation logic might not handle all cases correctly.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with start=None, end=None (read entire file)
    should_read, reason = memory.should_read_file("/test/file.py", None, None)
    # File was read fully, should return False
    assert should_read is False
    assert "already read" in reason
    
    # Test with start=10, end=None (read from line 10 to EOF)
    should_read, reason = memory.should_read_file("/test/file.py", 10, None)
    # File was read fully, should return False
    assert should_read is False
    assert "already read" in reason
    
    # Test with start=None, end=20 (read from beginning to line 20)
    should_read, reason = memory.should_read_file("/test/file.py", None, 20)
    # File was read fully, should return False
    assert should_read is False
    assert "already read" in reason


def test_should_read_file_with_invalid_string_line_numbers():
    """Test should_read_file with string line numbers (should fail).
    
    BUG: The validation uses type(start) is not int, which correctly
    rejects strings, but the error message might not be clear.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with start as string
    should_read, reason = memory.should_read_file("/test/file.py", "10", 20)
    assert should_read is True
    assert "must be an integer" in reason
    assert "str" in reason  # Should mention the type
    
    # Test with end as string
    should_read, reason = memory.should_read_file("/test/file.py", 10, "20")
    assert should_read is True
    assert "must be an integer" in reason
    assert "str" in reason


def test_should_read_file_with_float_line_numbers():
    """Test should_read_file with float line numbers (should fail).
    
    BUG: Floats like 10.0 should be rejected as invalid line numbers.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with start as float
    should_read, reason = memory.should_read_file("/test/file.py", 10.0, 20)
    assert should_read is True
    assert "must be an integer" in reason
    assert "float" in reason  # Should mention the type
    
    # Test with end as float
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20.0)
    assert should_read is True
    assert "must be an integer" in reason
    assert "float" in reason
    
    # Test with end=-1.0 (float -1.0, should be rejected)
    should_read, reason = memory.should_read_file("/test/file.py", 10, -1.0)
    assert should_read is True
    assert "must be an integer" in reason
    assert "float" in reason


if __name__ == "__main__":
    test_line_range_creation_with_none()
    print("test_line_range_creation_with_none passed")
    
    test_should_read_file_with_none_values()
    print("test_should_read_file_with_none_values passed")
    
    test_should_read_file_with_invalid_string_line_numbers()
    print("test_should_read_file_with_invalid_string_line_numbers passed")
    
    test_should_read_file_with_float_line_numbers()
    print("test_should_read_file_with_float_line_numbers passed")
    
    print("\nAll tests passed - no bug found!")