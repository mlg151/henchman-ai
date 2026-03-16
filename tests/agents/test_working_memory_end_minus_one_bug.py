"""Test for the end=-1 bug in working_memory.py."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_should_read_file_with_end_minus_one_bug():
    """Test should_read_file bug when end=-1 (read to EOF) with start provided.
    
    BUG: When end=-1 is provided (meaning "read to end of file"), the method
    converts end=-1 to None BEFORE validating line numbers. This causes a
    TypeError when comparing start > end (where end is now None).
    
    Example: should_read_file("/test/file.py", start=10, end=-1)
    Expected: Should validate start=10 is valid (positive integer)
    Actual: Raises TypeError: '>' not supported between instances of 'int' and 'NoneType'
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test case 1: start=10, end=-1 (read from line 10 to EOF)
    # This should NOT raise TypeError
    should_read, reason = memory.should_read_file("/test/file.py", start=10, end=-1)
    
    # The file was read fully, so should return False
    # But more importantly, it should NOT crash with TypeError
    assert should_read is False
    assert "already read" in reason.lower()


def test_should_read_file_with_end_minus_one_and_invalid_start():
    """Test should_read_file with end=-1 and invalid start value.
    
    When end=-1 and start is invalid (e.g., start=0), the method should
    report the invalid start error, not crash with TypeError.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with invalid start=0, end=-1
    should_read, reason = memory.should_read_file("/test/file.py", start=0, end=-1)
    
    # Should report invalid line number error, not crash
    assert should_read is True
    assert "invalid" in reason.lower() or "positive" in reason.lower()


def test_should_read_file_with_end_minus_one_and_start_gt_end():
    """Test should_read_file with end=-1 and start > end scenario.
    
    When end=-1 and start > -1 (which is always true for positive start),
    the validation should handle this special case properly.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with start=10, end=-1
    # Since end=-1 means "read to EOF", start=10 > -1 is actually valid
    # (we want to read from line 10 to end of file)
    should_read, reason = memory.should_read_file("/test/file.py", start=10, end=-1)
    
    # File was read fully, so should return False
    assert should_read is False
    assert "already read" in reason.lower()


def test_should_read_file_end_minus_one_partial_read():
    """Test should_read_file with end=-1 when file was partially read."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-50"))
    
    # Request to read from line 60 to EOF (end=-1)
    should_read, reason = memory.should_read_file("/test/file.py", start=60, end=-1)
    
    # Should return True (need to read lines 60-EOF)
    assert should_read is True
    assert "beyond" in reason.lower() or "need to read" in reason.lower()


if __name__ == "__main__":
    # Run the tests
    import sys
    try:
        test_should_read_file_with_end_minus_one_bug()
        print("✓ test_should_read_file_with_end_minus_one_bug passed")
    except Exception as e:
        print(f"✗ test_should_read_file_with_end_minus_one_bug failed: {e}")
        sys.exit(1)
    
    try:
        test_should_read_file_with_end_minus_one_and_invalid_start()
        print("✓ test_should_read_file_with_end_minus_one_and_invalid_start passed")
    except Exception as e:
        print(f"✗ test_should_read_file_with_end_minus_one_and_invalid_start failed: {e}")
        sys.exit(1)
    
    try:
        test_should_read_file_with_end_minus_one_and_start_gt_end()
        print("✓ test_should_read_file_with_end_minus_one_and_start_gt_end passed")
    except Exception as e:
        print(f"✗ test_should_read_file_with_end_minus_one_and_start_gt_end failed: {e}")
        sys.exit(1)
    
    try:
        test_should_read_file_end_minus_one_partial_read()
        print("✓ test_should_read_file_end_minus_one_partial_read passed")
    except Exception as e:
        print(f"✗ test_should_read_file_end_minus_one_partial_read failed: {e}")
        sys.exit(1)
    
    print("\nAll tests passed!")