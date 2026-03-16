"""Test to find a real bug in working_memory.py."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry, LineRange


def test_memory_should_read_file_edge_case_negative_end_after_conversion():
    """Test edge case with end=-1 after it's converted to None.
    
    BUG POTENTIAL: When end=-1 is converted to None, and start is provided,
    the validation start > end doesn't happen because end is None.
    But actually, end=-1 means "read to end of file", so start=10, end=-1
    means "read from line 10 to EOF", which is valid.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-50"))
    
    # Test: start=10, end=-1 (read from line 10 to EOF)
    should_read, reason = memory.should_read_file("/test/file.py", 10, -1)
    
    # Lines 10-50 have been read, but we want 10-EOF (beyond 50)
    # Should return True because we might need lines beyond 50
    assert should_read is True, f"Expected True, got {should_read}, reason: {reason}"
    assert "may need to read lines beyond" in reason.lower() or "beyond" in reason.lower()


def test_memory_parse_line_ranges_unicode_dash():
    """Test _parse_line_ranges with Unicode dash characters.
    
    The code handles various dash characters, but does it handle them correctly?
    """
    memory = WorkingMemory(current_task="Test")
    
    # Test with en dash (U+2013)
    ranges = memory._parse_line_ranges("10–20")  # en dash
    assert len(ranges) == 1
    assert ranges[0].start == 10
    assert ranges[0].end == 20
    
    # Test with em dash (U+2014)
    ranges = memory._parse_line_ranges("30—40")  # em dash
    assert len(ranges) == 1
    assert ranges[0].start == 30
    assert ranges[0].end == 40
    
    # Test with minus sign (U+2212)
    ranges = memory._parse_line_ranges("50−60")  # minus sign
    assert len(ranges) == 1
    assert ranges[0].start == 50
    assert ranges[0].end == 60


def test_memory_should_read_file_empty_lines_read():
    """Test should_read_file when lines_read is empty string.
    
    BUG POTENTIAL: Empty lines_read string should be treated as invalid.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Add entry with empty lines_read
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="",  # Empty string
        key_insights=[],
    )
    memory.add_recent_file(entry)
    
    # Request lines 10-20
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)
    
    # Should return True (invalid lines_read format)
    assert should_read is True
    assert "invalid lines_read format" in reason.lower() or "Cannot determine" in reason.lower()


def test_memory_line_range_validation_zero():
    """Test LineRange validation with zero values.
    
    BUG: LineRange(0, 10) should raise ValueError because lines are 1-indexed.
    """
    # This should raise ValueError
    with pytest.raises(ValueError, match="Line numbers must be positive"):
        LineRange(0, 10)
    
    # This should also raise ValueError
    with pytest.raises(ValueError, match="Line numbers must be positive"):
        LineRange(1, 0)
    
    # This should work
    lr = LineRange(1, 10)
    assert lr.start == 1
    assert lr.end == 10


def test_memory_should_read_file_invalid_lines_read_none():
    """Test should_read_file when lines_read is None (after deserialization).
    
    BUG POTENTIAL: lines_read can be None after deserialization.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Create entry with lines_read=None (simulating deserialization)
    # This is tricky because WorkingMemoryEntry.__post_init__ validates lines_read
    # But let's test the _parse_line_ranges method directly
    ranges = memory._parse_line_ranges(None)  # type: ignore
    assert ranges == []
    
    # Test with empty string
    ranges = memory._parse_line_ranges("")
    assert ranges == []
    
    # Test with whitespace only
    ranges = memory._parse_line_ranges("   ")
    assert ranges == []


if __name__ == "__main__":
    # Run tests
    import sys
    
    tests = [
        test_memory_should_read_file_edge_case_negative_end_after_conversion,
        test_memory_parse_line_ranges_unicode_dash,
        test_memory_should_read_file_empty_lines_read,
        test_memory_line_range_validation_zero,
        test_memory_should_read_file_invalid_lines_read_none,
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
    sys.exit(1 if failures > 0 else 0)