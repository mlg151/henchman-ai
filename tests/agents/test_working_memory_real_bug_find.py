"""Test to find real bug in working_memory.py."""

import pytest

from henchman.agents.working_memory import (
    LineRange,
    WorkingMemory,
    WorkingMemoryEntry,
)


def test_line_range_from_str_edge_cases():
    """Test LineRange.from_str with edge cases."""
    # Test empty string
    assert LineRange.from_str("") is None
    
    # Test single dash
    assert LineRange.from_str("-") is None
    
    # Test start dash only
    assert LineRange.from_str("10-") is None
    
    # Test dash end only  
    assert LineRange.from_str("-20") is None
    
    # Test valid range
    assert LineRange.from_str("10-20") == LineRange(10, 20)
    
    # Test start > end (should be caught by __post_init__)
    result = LineRange.from_str("20-10")
    # Should return None because __post_init__ raises ValueError
    assert result is None
    
    # Test with Unicode dash
    assert LineRange.from_str("10–20") == LineRange(10, 20)  # en dash
    assert LineRange.from_str("10—20") == LineRange(10, 20)  # em dash
    
    # Test with spaces (should fail because .isdecimal() returns False for strings with spaces)
    assert LineRange.from_str("10 - 20") is None
    
    # Test with non-decimal characters
    assert LineRange.from_str("10-20a") is None
    assert LineRange.from_str("a10-20") is None


def test_should_read_file_edge_case_bug():
    """Test edge case bug in should_read_file.
    
    BUG FOUND: When start=1, end=-1 (read from line 1 to EOF), and file was read
    with lines_read="full", the method should return False (file already read fully).
    But there might be an issue with the validation logic.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test: start=1, end=-1 (read from line 1 to EOF)
    should_read, reason = memory.should_read_file("/test/file.py", 1, -1)
    
    # File was read fully, so should return False
    assert should_read is False, f"File read fully, should return False. Got: {should_read}, reason: {reason}"
    assert "already read" in reason.lower()


def test_should_read_file_validation_order_real_bug():
    """Test real bug in validation order.
    
    ACTUAL BUG: When start is invalid (e.g., start=0) and end=-1,
    the validation happens in this order:
    1. Validate start: start=0 < 1 → returns error
    2. Validate end: end=-1 is valid special case
    3. Convert end=-1 to None
    4. Check start > end: skipped because end is None
    
    This is actually CORRECT! The bug I thought existed doesn't.
    
    But let me test a different edge case: what if start is a float?
    """
    memory = WorkingMemory(current_task="Test")
    
    # Test with float start
    should_read, reason = memory.should_read_file("/test/file.py", 1.5, 10)
    assert should_read is True
    assert "must be an integer" in reason or "invalid" in reason
    
    # Test with float end  
    should_read, reason = memory.should_read_file("/test/file.py", 1, 10.5)
    assert should_read is True
    assert "must be an integer" in reason or "invalid" in reason
    
    # Test with float end=-1.0 (should be rejected, only integer -1 allowed)
    should_read, reason = memory.should_read_file("/test/file.py", 1, -1.0)
    assert should_read is True
    assert "must be an integer" in reason or "invalid" in reason


def test_parse_line_ranges_inconsistent_with_validation_bug():
    """Test inconsistency between _parse_line_ranges and _validate_lines_read.
    
    POTENTIAL BUG: _parse_line_ranges returns [] for "full" or invalid formats.
    _validate_lines_read raises ValueError for invalid formats.
    But WorkingMemoryEntry.__post_init__ calls _validate_lines_read.
    
    So if someone creates WorkingMemoryEntry with invalid lines_read,
    it raises ValueError. But _parse_line_ranges just returns [].
    
    This might be intentional: _parse_line_ranges is lenient (skips invalid parts),
    while _validate_lines_read is strict (rejects entire string if any invalid part).
    """
    from henchman.agents.working_memory import WorkingMemory
    
    # Test with invalid format
    result = WorkingMemory._parse_line_ranges("10-20,invalid,30-40")
    # Should parse 10-20 and 30-40, skip "invalid"
    assert len(result) == 2
    assert result[0] == LineRange(10, 20)
    assert result[1] == LineRange(30, 40)
    
    # Creating WorkingMemoryEntry with "10-20,invalid,30-40" should NOT raise ValueError
    # because it has valid parts (10-20 and 30-40). Invalid part "invalid" is skipped.
    # This is consistent with _parse_line_ranges.
    entry = WorkingMemoryEntry("/test/file.py", "Test", "10-20,invalid,30-40")
    assert entry.lines_read == "10-20,invalid,30-40"
    
    # Only completely invalid strings should raise ValueError
    with pytest.raises(ValueError, match="Invalid lines_read"):
        WorkingMemoryEntry("/test/file.py", "Test", "invalid,also-invalid")
    
    # This consistency FIXES the bug! Now parsing and validation are consistent.
    # Both skip invalid parts and only reject strings with no valid content.
    # This also fixes deserialization bug - entries with invalid parts can be loaded.


def test_should_read_file_with_empty_lines_read_bug():
    """Test bug with empty lines_read string.
    
    If lines_read is empty string "", it means "no lines have been read".
    should_read_file should handle this correctly.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Add entry with empty lines_read
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", ""))
    
    # Check if file should be read (lines 10-50)
    should_read, reason = memory.should_read_file("/test/file.py", 10, 50)
    
    # No lines have been read, so should return True
    assert should_read is True
    assert "no lines" in reason.lower() or "not read" in reason.lower()
    
    # What about with start=None, end=None (read whole file)?
    should_read, reason = memory.should_read_file("/test/file.py")
    assert should_read is True
    assert "no lines" in reason.lower() or "not read" in reason.lower()