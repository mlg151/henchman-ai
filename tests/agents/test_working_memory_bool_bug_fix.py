"""Test for the boolean line number bug in working_memory.py."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_validate_and_normalize_line_numbers_bool_true():
    """Test that True is accepted as line number 1."""
    memory = WorkingMemory(current_task="Test")
    
    # Add a file entry first
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-50"))
    
    # Test with True (should be treated as 1)
    # This should NOT raise an error
    should_read, reason, norm_start, norm_end = memory._validate_and_normalize_line_numbers(True, 10)
    
    print(f"Testing with start=True, end=10")
    print(f"Result: should_read={should_read}, reason={reason}, norm_start={norm_start}, norm_end={norm_end}")
    
    # Should NOT indicate an error (should_read should be False)
    assert should_read is False, f"True should be valid (equals 1). Got error: {reason}"
    assert norm_start == 1, f"True should normalize to 1, got {norm_start}"
    assert norm_end == 10, f"end should remain 10, got {norm_end}"


def test_validate_and_normalize_line_numbers_bool_false():
    """Test that False is accepted as line number 0 (which should then fail validation)."""
    memory = WorkingMemory(current_task="Test")
    
    # Add a file entry first
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-50"))
    
    # Test with False (should be treated as 0, which is invalid for line numbers)
    should_read, reason, norm_start, norm_end = memory._validate_and_normalize_line_numbers(False, 10)
    
    print(f"Testing with start=False, end=10")
    print(f"Result: should_read={should_read}, reason={reason}, norm_start={norm_start}, norm_end={norm_end}")
    
    # Should indicate an error because line 0 is invalid
    assert should_read is True, f"False (0) should be invalid for line numbers"
    assert "invalid" in reason.lower() or "positive" in reason.lower(), f"Should report invalid line number. Got: {reason}"
    assert "0" in reason or "False" in reason, f"Error message should mention the invalid value"


def test_validate_and_normalize_line_numbers_bool_end():
    """Test that boolean values as end parameter are handled correctly."""
    memory = WorkingMemory(current_task="Test")
    
    # Add a file entry first
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-50"))
    
    # Test with True as end (should be treated as 1)
    should_read, reason, norm_start, norm_end = memory._validate_and_normalize_line_numbers(10, True)
    
    print(f"Testing with start=10, end=True")
    print(f"Result: should_read={should_read}, reason={reason}, norm_start={norm_start}, norm_end={norm_end}")
    
    # Should NOT indicate an error (should_read should be False)
    assert should_read is False, f"True as end should be valid (equals 1). Got error: {reason}"
    assert norm_start == 10, f"start should remain 10, got {norm_start}"
    assert norm_end == 1, f"True should normalize to 1, got {norm_end}"
    
    # Check that start > end validation still works
    should_read2, reason2, norm_start2, norm_end2 = memory._validate_and_normalize_line_numbers(10, False)
    
    print(f"Testing with start=10, end=False (0)")
    print(f"Result: should_read={should_read2}, reason={reason2}, norm_start={norm_start2}, norm_end={norm_end2}")
    
    # Should indicate an error because end=False (0) is invalid
    assert should_read2 is True, f"False (0) as end should be invalid"
    assert "invalid" in reason2.lower() or "positive" in reason2.lower(), f"Should report invalid line number. Got: {reason2}"


def test_should_read_file_with_bool_values():
    """Test should_read_file with boolean line numbers."""
    memory = WorkingMemory(current_task="Test")
    
    # Add a file entry
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-50"))
    
    # Test with True as start (should be treated as 1)
    should_read, reason = memory.should_read_file("/test/file.py", True, 10)
    
    print(f"should_read_file with start=True, end=10: should_read={should_read}, reason={reason}")
    
    # Line 1-10 should be contained in 1-50, so should return False
    assert should_read is False, f"Lines 1-10 are contained in 1-50. Got: {should_read}"
    assert "already read" in reason.lower() or "covered" in reason.lower()
    
    # Test with False as start (should be treated as 0, which is invalid)
    should_read2, reason2 = memory.should_read_file("/test/file.py", False, 10)
    
    print(f"should_read_file with start=False, end=10: should_read={should_read2}, reason={reason2}")
    
    # Should return True with error about invalid line number
    assert should_read2 is True, f"False (0) is invalid line number, should return True"
    assert "invalid" in reason2.lower() or "positive" in reason2.lower(), f"Should report invalid line number. Got: {reason2}"


def test_bool_from_conditional_expression():
    """Test realistic scenario where boolean might come from conditional expression."""
    memory = WorkingMemory(current_task="Test")
    
    # Add a file entry
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-50"))
    
    # Simulate a conditional expression that returns boolean
    use_line_one = True
    start_line = 1 if use_line_one else 10
    
    # This should work fine since it's an int
    should_read, reason = memory.should_read_file("/test/file.py", start_line, 20)
    assert should_read is False  # 1-20 is contained in 1-50
    
    # Now test with boolean directly (might happen in edge cases)
    start_bool = True  # Could come from some API that returns bool
    
    # This currently fails with the bug
    should_read2, reason2 = memory.should_read_file("/test/file.py", start_bool, 20)
    
    print(f"Testing with start_bool=True directly: should_read={should_read2}, reason={reason2}")
    
    # Should work after fix
    assert should_read2 is False, f"True should be treated as 1. Got: {should_read2}"
    assert "already read" in reason2.lower() or "covered" in reason2.lower()


if __name__ == "__main__":
    print("Testing boolean line number bug...")
    print("=" * 60)
    
    tests = [
        test_validate_and_normalize_line_numbers_bool_true,
        test_validate_and_normalize_line_numbers_bool_false,
        test_validate_and_normalize_line_numbers_bool_end,
        test_should_read_file_with_bool_values,
        test_bool_from_conditional_expression,
    ]
    
    for test in tests:
        print(f"\nRunning {test.__name__}...")
        try:
            test()
            print("  ✓ PASS")
        except AssertionError as e:
            print(f"  ✗ FAIL: {e}")
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
    
    print("\n" + "=" * 60)
    print("Note: These tests will FAIL with the current implementation.")
    print("They should PASS after fixing type(start) is not int to not isinstance(start, int)")