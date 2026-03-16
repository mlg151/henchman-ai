"""Test for a REAL bug in working_memory.py that should FAIL."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_should_read_file_bug_with_negative_start():
    """Test should_read_file with negative start value.
    
    BUG: start must be positive (1-indexed). Negative start should be invalid.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with start=-5 (invalid, negative)
    should_read, reason = memory.should_read_file("/test/file.py", start=-5, end=50)
    
    # Should return True with error about invalid line number
    assert should_read is True
    assert "invalid" in reason.lower() or "positive" in reason.lower(), (
        f"Expected error about invalid line number for start=-5, got: {reason}"
    )


def test_should_read_file_bug_with_start_float():
    """Test should_read_file with start as float.
    
    BUG: start must be integer. Float should be rejected.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with start=10.5 (float, not int)
    should_read, reason = memory.should_read_file("/test/file.py", start=10.5, end=50)
    
    # Should return True with error about invalid line number
    assert should_read is True
    assert "integer" in reason.lower(), (
        f"Expected error about integer for start=10.5, got: {reason}"
    )


def test_should_read_file_bug_with_end_float():
    """Test should_read_file with end as float (not -1.0).
    
    BUG: end must be integer (or -1). Float should be rejected.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with end=50.5 (float, not int)
    should_read, reason = memory.should_read_file("/test/file.py", start=10, end=50.5)
    
    # Should return True with error about invalid line number
    assert should_read is True
    assert "integer" in reason.lower(), (
        f"Expected error about integer for end=50.5, got: {reason}"
    )


def test_should_read_file_bug_with_end_float_minus_one():
    """Test should_read_file with end=-1.0 (float).
    
    BUG: end=-1.0 (float) should be treated as -1 (read to EOF).
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with end=-1.0 (float)
    should_read, reason = memory.should_read_file("/test/file.py", start=10, end=-1.0)
    
    # Should work (end=-1.0 == -1)
    # File was read fully, so should return False
    assert should_read is False
    assert "already read" in reason.lower()


def test_should_read_file_bug_with_string_parameters():
    """Test should_read_file with string parameters (should be rejected).
    
    BUG: start and end must be integers, not strings.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with start="10" (string)
    should_read, reason = memory.should_read_file("/test/file.py", start="10", end=50)
    
    # Should return True with error about invalid line number
    assert should_read is True
    assert "integer" in reason.lower(), (
        f"Expected error about integer for start='10', got: {reason}"
    )
    
    # Test with end="50" (string)
    should_read, reason = memory.should_read_file("/test/file.py", start=10, end="50")
    
    # Should return True with error about invalid line number
    assert should_read is True
    assert "integer" in reason.lower(), (
        f"Expected error about integer for end='50', got: {reason}"
    )


def test_should_read_file_bug_with_none_parameters():
    """Test should_read_file with None parameters.
    
    BUG: None is allowed for start/end (means unspecified).
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with start=None, end=None (read entire file)
    should_read, reason = memory.should_read_file("/test/file.py", start=None, end=None)
    
    # File was read fully, so should return False
    assert should_read is False
    assert "already read" in reason.lower()


if __name__ == "__main__":
    # Run tests
    import sys
    
    tests = [
        test_should_read_file_bug_with_negative_start,
        test_should_read_file_bug_with_start_float,
        test_should_read_file_bug_with_end_float,
        test_should_read_file_bug_with_end_float_minus_one,
        test_should_read_file_bug_with_string_parameters,
        test_should_read_file_bug_with_none_parameters,
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
        print("\nAll tests passed! (No bug found)")