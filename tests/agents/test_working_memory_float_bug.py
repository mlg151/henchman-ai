"""Test for float -1.0 bug in working_memory.py."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_should_read_file_with_float_minus_one():
    """Test should_read_file with end=-1.0 (float).
    
    BUG: The method converts end=-1 to None using `if end == -1:`.
    This works for end=-1.0 (float) because -1.0 == -1 is True.
    But the method signature says end: int | None, not float.
    This is a type violation.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with end=-1.0 (float) - should work but is type violation
    should_read, reason = memory.should_read_file("/test/file.py", start=10, end=-1.0)
    
    # File was read fully, so should return False
    assert should_read is False
    assert "already read" in reason.lower()
    
    print(f"Test passes: end=-1.0 (float) works: should_read={should_read}, reason={reason}")


def test_should_read_file_with_float_minus_one_point_five():
    """Test should_read_file with end=-1.5 (float).
    
    BUG: end=-1.5 doesn't equal -1, so doesn't get converted to None.
    Then type(end) is not int is True (float), returns error.
    This is inconsistent: -1.0 works but -1.5 doesn't.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with end=-1.5 (float) - should fail
    should_read, reason = memory.should_read_file("/test/file.py", start=10, end=-1.5)
    
    # Should return error about invalid line number
    assert should_read is True
    assert "integer" in reason.lower() or "invalid" in reason.lower()
    
    print(f"Test passes: end=-1.5 (float) fails: should_read={should_read}, reason={reason}")


def test_should_read_file_type_safety_bug():
    """Test type safety bug: method accepts float but signature says int."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # The bug is that the method signature is wrong!
    # It should be: end: int | float | None = None
    # Or it should reject float explicitly.
    
    # Currently accepts float -1.0
    should_read1, _ = memory.should_read_file("/test/file.py", start=10, end=-1.0)
    assert should_read1 is False  # File read fully
    
    # Currently rejects float -1.5
    should_read2, reason2 = memory.should_read_file("/test/file.py", start=10, end=-1.5)
    assert should_read2 is True  # Error
    
    print("Type safety bug: method inconsistently handles float values")


if __name__ == "__main__":
    test_should_read_file_with_float_minus_one()
    test_should_read_file_with_float_minus_one_point_five()
    test_should_read_file_type_safety_bug()
    print("\nTests show type inconsistency bug with float values")