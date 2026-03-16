"""Test to find a REAL bug in working_memory.py."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry, LineRange


def test_memory_should_read_file_start_zero_end_valid():
    """Test should_read_file with start=0 (invalid) and valid end.
    
    BUG: start=0 should be rejected as invalid (lines are 1-indexed).
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test: start=0, end=10 (invalid start)
    should_read, reason = memory.should_read_file("/test/file.py", 0, 10)
    
    # Should return True with error about invalid start
    assert should_read is True, f"Invalid start=0 should return True with error. Got: {should_read}, reason: {reason}"
    assert "invalid" in reason.lower() or "positive" in reason.lower() or "1-indexed" in reason.lower()
    assert "start" in reason.lower()


def test_memory_should_read_file_end_zero_start_valid():
    """Test should_read_file with valid start and end=0 (invalid).
    
    BUG: end=0 should be rejected as invalid (lines are 1-indexed).
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test: start=1, end=0 (invalid end)
    should_read, reason = memory.should_read_file("/test/file.py", 1, 0)
    
    # Should return True with error about invalid end
    assert should_read is True, f"Invalid end=0 should return True with error. Got: {should_read}, reason: {reason}"
    assert "invalid" in reason.lower() or "positive" in reason.lower() or "1-indexed" in reason.lower()
    assert "end" in reason.lower() or "0" in reason.lower()


def test_memory_should_read_file_start_gt_end():
    """Test should_read_file with start > end (invalid range).
    
    BUG: start=10, end=5 should be rejected as invalid range.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test: start=10, end=5 (invalid: start > end)
    should_read, reason = memory.should_read_file("/test/file.py", 10, 5)
    
    # Should return True with error about invalid range
    assert should_read is True, f"Invalid range start=10 > end=5 should return True with error. Got: {should_read}, reason: {reason}"
    assert "invalid" in reason.lower() or "start.*>.*end" in reason.lower() or "ascending" in reason.lower()


def test_memory_should_read_file_float_line_numbers():
    """Test should_read_file with float line numbers.
    
    BUG: Float values like 1.5 should be rejected as invalid type.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test: start=1.5, end=10 (float start)
    should_read, reason = memory.should_read_file("/test/file.py", 1.5, 10)
    
    # Should return True with error about invalid type
    assert should_read is True, f"Float start=1.5 should return True with error. Got: {should_read}, reason: {reason}"
    assert "invalid" in reason.lower() or "type" in reason.lower() or "integer" in reason.lower()
    assert "float" in reason.lower() or "1.5" in reason
    
    # Test: start=1, end=10.5 (float end)
    should_read2, reason2 = memory.should_read_file("/test/file.py", 1, 10.5)
    
    assert should_read2 is True, f"Float end=10.5 should return True with error. Got: {should_read2}, reason: {reason2}"
    assert "invalid" in reason2.lower() or "type" in reason2.lower() or "integer" in reason2.lower()
    assert "float" in reason2.lower() or "10.5" in reason2


def test_memory_should_read_file_string_line_numbers():
    """Test should_read_file with string line numbers.
    
    BUG: String values like "10" should be rejected as invalid type.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test: start="10", end=20 (string start)
    should_read, reason = memory.should_read_file("/test/file.py", "10", 20)  # type: ignore
    
    # Should return True with error about invalid type
    assert should_read is True, f"String start='10' should return True with error. Got: {should_read}, reason: {reason}"
    assert "invalid" in reason.lower() or "type" in reason.lower() or "integer" in reason.lower()
    assert "str" in reason.lower() or "'10'" in reason or '"10"' in reason
    
    # Test: start=1, end="20" (string end)
    should_read2, reason2 = memory.should_read_file("/test/file.py", 1, "20")  # type: ignore
    
    assert should_read2 is True, f"String end='20' should return True with error. Got: {should_read2}, reason: {reason2}"
    assert "invalid" in reason2.lower() or "type" in reason2.lower() or "integer" in reason2.lower()
    assert "str" in reason2.lower() or "'20'" in reason2 or '"20"' in reason2


def test_memory_line_range_from_str_invalid():
    """Test LineRange.from_str with invalid input.
    
    BUG: LineRange.from_str should return None for invalid input.
    """
    # Test with invalid format
    assert LineRange.from_str("") is None
    assert LineRange.from_str("invalid") is None
    assert LineRange.from_str("10-") is None
    assert LineRange.from_str("-20") is None
    assert LineRange.from_str("10-20-30") is None  # Multiple dashes
    
    # Test with invalid numbers
    assert LineRange.from_str("0-10") is None  # start=0 invalid
    assert LineRange.from_str("10-0") is None  # end=0 invalid
    assert LineRange.from_str("-5-10") is None  # negative start
    assert LineRange.from_str("10--5") is None  # negative end
    
    # Test with start > end
    assert LineRange.from_str("20-10") is None  # start > end
    
    # Valid cases
    assert LineRange.from_str("10-20") is not None
    assert LineRange.from_str("1-1") is not None  # single line
    assert LineRange.from_str("100-200") is not None


if __name__ == "__main__":
    # Run tests
    import sys
    
    tests = [
        test_memory_should_read_file_start_zero_end_valid,
        test_memory_should_read_file_end_zero_start_valid,
        test_memory_should_read_file_start_gt_end,
        test_memory_should_read_file_float_line_numbers,
        test_memory_should_read_file_string_line_numbers,
        test_memory_line_range_from_str_invalid,
    ]
    
    failures = 0
    for test in tests:
        print(f"\nRunning {test.__name__}...")
        try:
            test()
            print("  ✓ PASS")
        except AssertionError as e:
            print(f"  ✗ FAIL: {e}")
            failures += 1
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            failures += 1
    
    print(f"\nTotal: {len(tests)} tests, {failures} failures")
    
    if failures > 0:
        print("\nBUGS FOUND!")
    else:
        print("\nAll tests pass (no bugs found).")
    
    sys.exit(1 if failures > 0 else 0)