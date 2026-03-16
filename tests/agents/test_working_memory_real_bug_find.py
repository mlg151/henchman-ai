"""Test for a real bug in working_memory.py - finding the actual bug."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_should_read_file_bug_with_negative_end_other_than_minus_one():
    """Test should_read_file with end=-2 (invalid, not -1).
    
    BUG: The validation allows end=-1 (special case for EOF), but what about
    end=-2, -3, etc.? These should be invalid.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with end=-2 (invalid, not -1)
    should_read, reason = memory.should_read_file("/test/file.py", start=10, end=-2)
    
    # Should return True with error about invalid line number
    assert should_read is True
    assert "invalid" in reason.lower() or "positive" in reason.lower(), (
        f"Expected error about invalid line number for end=-2, got: {reason}"
    )


def test_should_read_file_bug_with_end_zero():
    """Test should_read_file with end=0 (invalid, 1-indexed)."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with end=0 (invalid, 1-indexed)
    should_read, reason = memory.should_read_file("/test/file.py", start=10, end=0)
    
    # Should return True with error about invalid line number
    assert should_read is True
    assert "invalid" in reason.lower() or "positive" in reason.lower(), (
        f"Expected error about invalid line number for end=0, got: {reason}"
    )


def test_should_read_file_bug_with_start_zero():
    """Test should_read_file with start=0 (invalid, 1-indexed)."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with start=0 (invalid, 1-indexed)
    should_read, reason = memory.should_read_file("/test/file.py", start=0, end=50)
    
    # Should return True with error about invalid line number
    assert should_read is True
    assert "invalid" in reason.lower() or "positive" in reason.lower(), (
        f"Expected error about invalid line number for start=0, got: {reason}"
    )


def test_should_read_file_bug_with_boolean_start():
    """Test should_read_file with start=True (bool, should be rejected).
    
    BUG: type(start) is not int will catch bool since bool is subclass of int,
    but isinstance(start, int) would return True for bool.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with start=True (bool, should be rejected)
    should_read, reason = memory.should_read_file("/test/file.py", start=True, end=50)
    
    # Should return True with error about invalid line number
    assert should_read is True
    assert "invalid" in reason.lower() or "integer" in reason.lower(), (
        f"Expected error about invalid line number for start=True, got: {reason}"
    )
    # Check that it specifically mentions bool
    assert "bool" in reason.lower() or "boolean" in reason.lower(), (
        f"Should mention bool/boolean in error, got: {reason}"
    )


def test_should_read_file_bug_with_boolean_end():
    """Test should_read_file with end=False (bool, should be rejected)."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with end=False (bool, should be rejected)
    should_read, reason = memory.should_read_file("/test/file.py", start=10, end=False)
    
    # Should return True with error about invalid line number
    assert should_read is True
    assert "invalid" in reason.lower() or "integer" in reason.lower(), (
        f"Expected error about invalid line number for end=False, got: {reason}"
    )
    # Check that it specifically mentions bool
    assert "bool" in reason.lower() or "boolean" in reason.lower(), (
        f"Should mention bool/boolean in error, got: {reason}"
    )


if __name__ == "__main__":
    # Run tests
    import sys
    
    tests = [
        test_should_read_file_bug_with_negative_end_other_than_minus_one,
        test_should_read_file_bug_with_end_zero,
        test_should_read_file_bug_with_start_zero,
        test_should_read_file_bug_with_boolean_start,
        test_should_read_file_bug_with_boolean_end,
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