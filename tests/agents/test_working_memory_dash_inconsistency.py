"""Test for dash character inconsistency bug in working_memory.py."""

import pytest
from henchman.agents.working_memory import LineRange, WorkingMemory


def test_line_range_from_str_vs_parse_line_ranges_inconsistency():
    """Test that LineRange.from_str and _parse_line_ranges handle different dash characters.
    
    BUG: LineRange.from_str only handles hyphen '-', but _parse_line_ranges
    handles multiple dash characters (hyphen, en dash, em dash, etc.).
    This inconsistency can cause bugs.
    """
    # Test with hyphen (should work in both)
    result1 = LineRange.from_str("10-20")
    assert result1 is not None
    assert result1.start == 10
    assert result1.end == 20
    
    # Test with en dash U+2013 (should work in both after fix)
    result2 = LineRange.from_str("10–20")  # en dash
    # FIXED: Now returns LineRange(10, 20) because we handle Unicode dashes
    assert result2 is not None, "LineRange.from_str should handle en dash after fix"
    assert result2.start == 10 and result2.end == 20
    
    # Test with em dash U+2014 (should work in both after fix)
    result3 = LineRange.from_str("10—20")  # em dash
    assert result3 is not None, "LineRange.from_str should handle em dash after fix"
    assert result3.start == 10 and result3.end == 20
    
    # Test with minus sign U+2212 (should work in both after fix)
    result4 = LineRange.from_str("10−20")  # minus sign
    assert result4 is not None, "LineRange.from_str should handle minus sign after fix"
    assert result4.start == 10 and result4.end == 20
    
    print("LineRange.from_str now handles Unicode dashes correctly")
    
    # Now test _parse_line_ranges
    memory = WorkingMemory(current_task="Test")
    
    # All these should parse correctly in _parse_line_ranges
    test_cases = [
        "10-20",    # hyphen
        "10–20",    # en dash U+2013
        "10—20",    # em dash U+2014  
        "10−20",    # minus sign U+2212
    ]
    
    for test_str in test_cases:
        ranges = memory._parse_line_ranges(test_str)
        assert len(ranges) == 1, f"_parse_line_ranges should parse '{test_str}'"
        assert ranges[0].start == 10
        assert ranges[0].end == 20
    
    print("_parse_line_ranges handles all dash characters correctly")
    
    # The bug is now fixed: both methods handle the same dash characters
    print("\nBUG FIXED: LineRange.from_str and _parse_line_ranges now handle the same dash characters!")
    print("Consistent behavior achieved.")


if __name__ == "__main__":
    test_line_range_from_str_vs_parse_line_ranges_inconsistency()
    print("\nTest complete - bug exists!")