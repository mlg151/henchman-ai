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
    
    # Test with en dash U+2013 (should work in _parse_line_ranges but NOT in LineRange.from_str)
    result2 = LineRange.from_str("10–20")  # en dash
    # BUG: This returns None because LineRange.from_str uses s.split("-") which doesn't split on en dash
    assert result2 is None, "LineRange.from_str should return None for en dash, but might not"
    
    # Test with em dash U+2014 (should work in _parse_line_ranges but NOT in LineRange.from_str)
    result3 = LineRange.from_str("10—20")  # em dash
    assert result3 is None, "LineRange.from_str should return None for em dash"
    
    # Test with minus sign U+2212 (should work in _parse_line_ranges but NOT in LineRange.from_str)
    result4 = LineRange.from_str("10−20")  # minus sign
    assert result4 is None, "LineRange.from_str should return None for minus sign"
    
    print("LineRange.from_str inconsistency confirmed")
    
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
    
    # The bug: inconsistency between the two parsing methods
    print("\nBUG CONFIRMED: LineRange.from_str and _parse_line_ranges handle different dash characters!")
    print("This can cause inconsistent behavior in the codebase.")

if __name__ == "__main__":
    test_line_range_from_str_vs_parse_line_ranges_inconsistency()
    print("\nTest complete - bug exists!")