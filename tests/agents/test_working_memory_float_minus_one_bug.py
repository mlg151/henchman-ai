"""Test for the float -1.0 bug in working_memory.py."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_should_read_file_with_end_float_minus_one():
    """Test should_read_file bug when end=-1.0 (float).
    
    BUG: end=-1.0 should be treated as end=-1 (read to EOF) since -1.0 == -1 is True.
    Currently it's rejected as "Invalid line number: end must be an integer".
    
    FIXED: Now correctly rejects float -1.0 because method signature is end: int | None.
    Only integer -1 is accepted.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with end=-1.0 (float)
    should_read, reason = memory.should_read_file("/test/file.py", start=10, end=-1.0)
    
    # Should return error about invalid line number (not integer)
    print(f"should_read={should_read}, reason={reason}")
    
    # Now correctly rejects float -1.0
    assert should_read is True, f"Expected True (error), got False with reason: {reason}"
    assert "integer" in reason.lower() or "invalid" in reason.lower()


def test_should_read_file_with_end_float_minus_one_no_start():
    """Test should_read_file with end=-1.0 and no start specified."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with end=-1.0 (float), no start
    should_read, reason = memory.should_read_file("/test/file.py", end=-1.0)
    
    # Should return error about invalid line number (not integer)
    print(f"should_read={should_read}, reason={reason}")
    
    assert should_read is True
    assert "integer" in reason.lower() or "invalid" in reason.lower()


def test_should_read_file_with_end_float_minus_one_partial():
    """Test should_read_file with end=-1.0 when file was partially read."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-50"))
    
    # Request to read from line 60 to EOF (end=-1.0 float)
    should_read, reason = memory.should_read_file("/test/file.py", start=60, end=-1.0)
    
    # Should return error about invalid line number (not integer)
    print(f"should_read={should_read}, reason={reason}")
    
    assert should_read is True
    assert "integer" in reason.lower() or "invalid" in reason.lower()


def test_should_read_file_with_end_int_minus_one():
    """Test should_read_file with end=-1 (int) for comparison."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with end=-1 (int) - should work
    should_read, reason = memory.should_read_file("/test/file.py", start=10, end=-1)
    
    # Should return False (file read fully)
    print(f"should_read={should_read}, reason={reason}")
    
    assert should_read is False
    assert "already read" in reason.lower()


if __name__ == "__main__":
    # Run tests
    import sys
    
    tests = [
        test_should_read_file_with_end_float_minus_one,
        test_should_read_file_with_end_float_minus_one_no_start,
        test_should_read_file_with_end_float_minus_one_partial,
        test_should_read_file_with_end_int_minus_one,
    ]
    
    all_passed = True
    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__} passed")
        except AssertionError as e:
            print(f"✗ {test.__name__} failed: {e}")
            all_passed = False
        except Exception as e:
            print(f"✗ {test.__name__} error: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False
    
    if not all_passed:
        sys.exit(1)
    else:
        print("\nAll tests passed!")