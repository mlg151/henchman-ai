"""Test for the bug where line number validation happens after 'full' read check.

This test demonstrates the bug where should_read_file returns incorrect result
when a file was read "full" but invalid line numbers are provided.
"""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_should_read_file_full_with_invalid_line_numbers_bug():
    """Test should_read_file bug: invalid line numbers masked by "full" read.
    
    BUG: When a file was read "full" and invalid line numbers are provided
    (e.g., start=0, end=-1), the method returns False, "File already read (full)"
    instead of reporting the invalid line number error.
    
    This is incorrect because:
    1. Invalid inputs should be reported as errors
    2. The caller might think they provided valid parameters but got a misleading response
    3. This could hide bugs in calling code that passes invalid line numbers
    """
    memory = WorkingMemory(current_task="Test")
    
    # Add entry with file read fully
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="full",
        key_insights=["Full file read"]
    ))
    
    # Test 1: Invalid start=0 (lines are 1-indexed)
    should_read, reason = memory.should_read_file("/test/file.py", 0, 10)
    
    # BUG: Returns False, "File already read (full)"
    # Should return True with error about invalid line number
    assert should_read is True, (
        f"Invalid start=0 should return True with error, not False. "
        f"Got: should_read={should_read}, reason={reason}"
    )
    assert "invalid" in reason.lower() or "positive" in reason.lower() or "1-indexed" in reason.lower(), (
        f"Should report invalid line number error, not 'File already read (full)'. "
        f"Got reason: {reason}"
    )
    
    # Test 2: end=-1 is VALID (means "read to end of file")
    # This is not invalid - it's a special value used by the read_file tool
    should_read2, reason2 = memory.should_read_file("/test/file.py", 1, -1)
    assert should_read2 is False, (
        f"end=-1 is valid (means 'read to end of file'). "
        f"Since file was read fully, should return False. "
        f"Got: should_read={should_read2}, reason={reason2}"
    )
    assert "already read" in reason2.lower() or "full" in reason2.lower()
    
    # Test 3: start=0 is invalid, end=-1 is valid
    should_read3, reason3 = memory.should_read_file("/test/file.py", 0, -1)
    assert should_read3 is True, (
        f"start=0 is invalid (must be positive), end=-1 is valid. "
        f"Should return True with error about invalid start. "
        f"Got: should_read={should_read3}, reason={reason3}"
    )
    assert "invalid" in reason3.lower() or "positive" in reason3.lower() or "1-indexed" in reason3.lower()
    assert "start" in reason3.lower()  # Error should mention start, not end
    
    # Test 4: start > end (invalid range)
    should_read4, reason4 = memory.should_read_file("/test/file.py", 10, 5)
    assert should_read4 is True, (
        f"Invalid range start=10 > end=5 should return True with error. "
        f"Got: should_read={should_read4}, reason={reason4}"
    )
    assert "invalid" in reason4.lower() or "start.*>.*end" in reason4.lower()
    
    # Test 5: Valid line numbers should still return False (file read fully)
    should_read5, reason5 = memory.should_read_file("/test/file.py", 10, 50)
    assert should_read5 is False, (
        f"Valid line numbers 10-50 should return False (file read fully). "
        f"Got: should_read={should_read5}, reason={reason5}"
    )
    assert "already read" in reason5.lower()


def test_should_read_file_partial_range_invalid_line_numbers_bug():
    """Test should_read_file with partial range and invalid line numbers.
    
    Similar bug: When only start OR end is provided and invalid, 
    should report error about invalid line number.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="full"
    ))
    
    # Test: start=0, end=None (invalid start, partial range)
    should_read, reason = memory.should_read_file("/test/file.py", start=0)
    assert should_read is True, (
        f"Invalid start=0 with end=None should return True with error. "
        f"Got: should_read={should_read}, reason={reason}"
    )
    assert "invalid" in reason.lower() or "positive" in reason.lower() or "1-indexed" in reason.lower()
    
    # Test: start=None, end=0 (invalid end, partial range)
    should_read2, reason2 = memory.should_read_file("/test/file.py", end=0)
    assert should_read2 is True, (
        f"Invalid end=0 with start=None should return True with error. "
        f"Got: should_read={should_read2}, reason={reason2}"
    )
    assert "invalid" in reason2.lower() or "positive" in reason2.lower() or "1-indexed" in reason2.lower()
    
    # Test: start=-5, end=None (invalid negative start)
    should_read3, reason3 = memory.should_read_file("/test/file.py", start=-5)
    assert should_read3 is True, (
        f"Invalid start=-5 should return True with error. "
        f"Got: should_read={should_read3}, reason={reason3}"
    )
    assert "invalid" in reason3.lower() or "positive" in reason3.lower() or "1-indexed" in reason3.lower()
    
    # Test: start=None, end=-10 (invalid negative end, -10 is not -1)
    should_read4, reason4 = memory.should_read_file("/test/file.py", end=-10)
    assert should_read4 is True, (
        f"end=-10 is invalid (only -1 is valid as special value). "
        f"Should return True with error. "
        f"Got: should_read={should_read4}, reason={reason4}"
    )
    assert "invalid" in reason4.lower() or "positive" in reason4.lower() or "1-indexed" in reason4.lower()


if __name__ == "__main__":
    # Run tests to demonstrate the bug
    import sys
    
    print("Running bug validation order tests...")
    print("=" * 60)
    
    tests = [
        test_should_read_file_full_with_invalid_line_numbers_bug,
        test_should_read_file_partial_range_invalid_line_numbers_bug,
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
    
    print(f"\n" + "=" * 60)
    print(f"Total: {len(tests)} tests, {failures} failures")
    
    if failures > 0:
        print("\nBUG CONFIRMED: Tests fail with current implementation.")
        print("The bug is: should_read_file doesn't validate line numbers before checking 'full' read.")
    else:
        print("\nAll tests pass (bug may have been fixed).")
    
    sys.exit(1 if failures > 0 else 0)