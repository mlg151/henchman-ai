"""Test to find an ACTUAL bug in working_memory.py."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry, LineRange


def test_memory_should_read_file_none_values():
    """Test should_read_file with None values.
    
    The signature is start: int | None = None, end: int | None = None.
    What if someone passes None explicitly?
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test: start=None, end=None (explicitly)
    should_read, reason = memory.should_read_file("/test/file.py", None, None)
    
    # File was read fully, so should return False
    assert should_read is False, f"File read fully, should return False. Got: {should_read}, reason: {reason}"
    assert "already read" in reason.lower()


def test_memory_should_read_file_negative_start():
    """Test should_read_file with negative start (invalid).
    
    BUG: start=-5 should be rejected as invalid.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test: start=-5, end=10 (negative start)
    should_read, reason = memory.should_read_file("/test/file.py", -5, 10)
    
    # Should return True with error about invalid start
    assert should_read is True, f"Negative start=-5 should return True with error. Got: {should_read}, reason: {reason}"
    assert "invalid" in reason.lower() or "positive" in reason.lower() or "1-indexed" in reason.lower()


def test_memory_should_read_file_negative_end_not_minus_one():
    """Test should_read_file with negative end (not -1).
    
    BUG: end=-2 should be rejected as invalid (only -1 is special).
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test: start=1, end=-2 (negative end, not -1)
    should_read, reason = memory.should_read_file("/test/file.py", 1, -2)
    
    # Should return True with error about invalid end
    assert should_read is True, f"Negative end=-2 (not -1) should return True with error. Got: {should_read}, reason: {reason}"
    assert "invalid" in reason.lower() or "positive" in reason.lower() or "1-indexed" in reason.lower()


def test_memory_should_read_file_end_minus_one_with_invalid_start():
    """Test should_read_file with end=-1 and invalid start.
    
    BUG: end=-1 is valid, but start=0 is invalid.
    Should report error about invalid start, not about file being read fully.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test: start=0, end=-1 (invalid start, valid end=-1)
    should_read, reason = memory.should_read_file("/test/file.py", 0, -1)
    
    # Should return True with error about invalid start
    assert should_read is True, f"Invalid start=0 with end=-1 should return True with error. Got: {should_read}, reason: {reason}"
    assert "invalid" in reason.lower() or "positive" in reason.lower() or "1-indexed" in reason.lower()
    assert "start" in reason.lower()  # Error should mention start


def test_memory_parse_line_ranges_empty_string_after_normalization():
    """Test _parse_line_ranges with string that becomes empty after normalization.
    
    BUG: What if lines_read is "   " (only whitespace)?
    After normalization: "".join("   ".split()) = "" (empty string).
    Then normalized == "full" is False, "full" in normalized.split(",") is "full" in [""] which is False.
    So it continues to parse, but there's nothing to parse.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Test with whitespace-only string
    ranges = memory._parse_line_ranges("   ")
    assert ranges == []  # Should return empty list
    
    # Test with empty string
    ranges = memory._parse_line_ranges("")
    assert ranges == []  # Should return empty list
    
    # Test with None (should handle gracefully)
    ranges = memory._parse_line_ranges(None)  # type: ignore
    assert ranges == []  # Should return empty list


def test_memory_line_range_overlaps_edge_cases():
    """Test LineRange.overlaps method with edge cases.
    
    BUG: Check if overlaps method works correctly.
    """
    # Test overlapping ranges
    r1 = LineRange(1, 10)
    r2 = LineRange(5, 15)
    assert r1.overlaps(r2) is True
    assert r2.overlaps(r1) is True
    
    # Test adjacent ranges (end+1 == start)
    r3 = LineRange(1, 10)
    r4 = LineRange(11, 20)
    assert r3.overlaps(r4) is False  # Not overlapping, just adjacent
    
    # Test contained range
    r5 = LineRange(1, 100)
    r6 = LineRange(10, 20)
    assert r5.overlaps(r6) is True
    assert r6.overlaps(r5) is True
    
    # Test non-overlapping
    r7 = LineRange(1, 10)
    r8 = LineRange(20, 30)
    assert r7.overlaps(r8) is False
    assert r8.overlaps(r7) is False


def test_memory_should_read_file_complex_overlap_logic():
    """Test should_read_file with complex overlap logic.
    
    BUG: The logic for checking if requested range is fully covered might have bugs.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Add multiple partial reads
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "First", "1-30"))
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Second", "40-70"))
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Third", "80-100"))
    
    # Request lines 1-100 (gaps at 31-39 and 71-79)
    should_read, reason = memory.should_read_file("/test/file.py", 1, 100)
    
    # Should return True (gaps exist)
    assert should_read is True, f"Lines 1-100 have gaps, should return True. Got: {should_read}, reason: {reason}"
    assert "need to be read" in reason.lower() or "gap" in reason.lower() or "new" in reason.lower()
    
    # Request lines 1-30 (fully covered by first read)
    should_read2, reason2 = memory.should_read_file("/test/file.py", 1, 30)
    assert should_read2 is False, f"Lines 1-30 are fully covered, should return False. Got: {should_read2}, reason: {reason2}"
    assert "already read" in reason2.lower() or "covered" in reason2.lower()
    
    # Request lines 25-45 (partially covered, crosses gap)
    should_read3, reason3 = memory.should_read_file("/test/file.py", 25, 45)
    assert should_read3 is True, f"Lines 25-45 cross gap at 31-39, should return True. Got: {should_read3}, reason: {reason3}"


if __name__ == "__main__":
    # Run tests
    import sys
    
    tests = [
        test_memory_should_read_file_none_values,
        test_memory_should_read_file_negative_start,
        test_memory_should_read_file_negative_end_not_minus_one,
        test_memory_should_read_file_end_minus_one_with_invalid_start,
        test_memory_parse_line_ranges_empty_string_after_normalization,
        test_memory_line_range_overlaps_edge_cases,
        test_memory_should_read_file_complex_overlap_logic,
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