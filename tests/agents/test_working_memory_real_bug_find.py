"""Test to find a real bug in working_memory.py."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry, LineRange

def test_should_read_file_with_invalid_lines_read_format():
    """Test should_read_file when lines_read has invalid format like '10-20-30'.
    
    BUG: '10-20-30' has two dashes, which might not be handled correctly.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Create entry with invalid lines_read format '10-20-30' (two dashes)
    # With current implementation, WorkingMemoryEntry validates lines_read
    # and raises ValueError for invalid format
    with pytest.raises(ValueError, match="Invalid lines_read"):
        entry = WorkingMemoryEntry(
            path="/test/file.py",
            purpose="Test",
            lines_read="10-20-30",  # Invalid: two dashes
            key_insights=[],
        )
    
    # So we can't create entry with invalid format. Test with valid format instead.
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="10-20",  # Valid
        key_insights=[],
    )
    memory.add_recent_file(entry)
    
    # Request lines 15-25 (overlaps with 10-20)
    should_read, reason = memory.should_read_file("/test/file.py", 15, 25)
    
    # Lines 15-20 are already read, lines 21-25 are not
    # Should return True
    assert should_read is True
    assert "need to be read" in reason.lower() or "overlapping" in reason.lower()
    
    print(f"Test passes: should_read={should_read}, reason={reason}")

def test_parse_line_ranges_with_multiple_dashes():
    """Test _parse_line_ranges with '10-20-30' (two dashes)."""
    from henchman.agents.working_memory import WorkingMemory
    
    memory = WorkingMemory(current_task="Test")
    
    # '10-20-30' has two dashes - should be skipped
    ranges = memory._parse_line_ranges("10-20-30")
    # Should return empty list or handle gracefully
    # Current behavior: finds first dash at position 2, start_str="10", end_str="20-30"
    # end_str="20-30" is not decimal (contains dash), so .isdecimal() returns False
    # So it continues (skips)
    assert ranges == []
    
    print("Test passes: '10-20-30' correctly skipped")

def test_should_read_file_with_empty_string_lines_read():
    """Test should_read_file when lines_read is empty string ''.
    
    Empty string means "no lines have been read".
    """
    memory = WorkingMemory(current_task="Test")
    
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="",  # Empty string = no lines read
        key_insights=[],
    )
    memory.add_recent_file(entry)
    
    # Request lines 10-20
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)
    
    # Should return True (no lines have been read)
    assert should_read is True
    assert "no lines" in reason.lower() or "not read" in reason.lower()
    
    print(f"Test passes: should_read={should_read}, reason={reason}")

def test_line_range_from_str_with_unicode_digits():
    """Test LineRange.from_str with Unicode digits like '١٠-٢٠' (Arabic digits 10-20).
    
    BUG: .isdecimal() returns True for Arabic digits, but int() might fail?
    Actually int() works with Arabic digits in Python!
    """
    from henchman.agents.working_memory import LineRange
    
    # Arabic digits: ١ = 1, ٠ = 0, so ١٠ = 10, ٢٠ = 20
    result = LineRange.from_str("١٠-٢٠")
    # .isdecimal() returns True for Arabic digits
    # int() can parse Arabic digits in Python
    # So should create LineRange(10, 20)
    assert result is not None
    assert result.start == 10
    assert result.end == 20
    
    print(f"Test passes: LineRange.from_str('١٠-٢٠') = {result}")

def test_should_read_file_with_float_start():
    """Test should_read_file with start=10.5 (float).
    
    BUG: type(start) is not int returns True for float, so should return error.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with start=10.5 (float)
    should_read, reason = memory.should_read_file("/test/file.py", start=10.5, end=20)
    
    # Should return error about invalid line number
    assert should_read is True
    assert "integer" in reason.lower() or "invalid" in reason.lower()
    assert "float" in reason.lower()  # Error message should mention float
    
    print(f"Test passes: start=10.5 (float) correctly rejected: {reason}")

if __name__ == "__main__":
    test_should_read_file_with_invalid_lines_read_format()
    test_parse_line_ranges_with_multiple_dashes()
    test_should_read_file_with_empty_string_lines_read()
    test_line_range_from_str_with_unicode_digits()
    test_should_read_file_with_float_start()
    print("\nAll tests pass (no bug found)")