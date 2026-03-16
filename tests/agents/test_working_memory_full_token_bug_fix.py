"""Test for bug in _parse_line_ranges where 'full,10-20' doesn't return empty list."""

import pytest
from henchman.agents.working_memory import WorkingMemory, LineRange


def test_parse_line_ranges_full_with_ranges():
    """Test _parse_line_ranges with 'full,10-20'.
    
    BUG: Should return [] (file read fully) but returns [LineRange(10, 20)]
    """
    memory = WorkingMemory(current_task="Test")
    
    # Test _parse_line_ranges directly
    ranges = memory._parse_line_ranges("full,10-20")
    
    # BUG: Returns [LineRange(10, 20)] instead of []
    # 'full' token should take precedence
    print(f"_parse_line_ranges('full,10-20') = {ranges}")
    
    # This test FAILS with current code (bug exists)
    # Should pass after fix (returns [])
    assert ranges == [], (
        f"'full,10-20' contains 'full' token, so file was read fully. "
        f"Expected empty list [], got {ranges}"
    )


def test_parse_line_ranges_ranges_with_full():
    """Test _parse_line_ranges with '10-20,full'."""
    memory = WorkingMemory(current_task="Test")
    
    ranges = memory._parse_line_ranges("10-20,full")
    
    # Should also return [] because 'full' is present
    print(f"_parse_line_ranges('10-20,full') = {ranges}")
    
    assert ranges == [], (
        f"'10-20,full' contains 'full' token, so file was read fully. "
        f"Expected empty list [], got {ranges}"
    )


def test_parse_line_ranges_full_alone():
    """Test _parse_line_ranges with just 'full'."""
    memory = WorkingMemory(current_task="Test")
    
    ranges = memory._parse_line_ranges("full")
    
    # Already works correctly
    print(f"_parse_line_ranges('full') = {ranges}")
    
    assert ranges == [], f"'full' should return empty list [], got {ranges}"


def test_parse_line_ranges_multiple_full():
    """Test _parse_line_ranges with 'full,full,10-20'."""
    memory = WorkingMemory(current_task="Test")
    
    ranges = memory._parse_line_ranges("full,full,10-20")
    
    # Should return [] because 'full' is present
    print(f"_parse_line_ranges('full,full,10-20') = {ranges}")
    
    assert ranges == [], (
        f"'full,full,10-20' contains 'full' token, so file was read fully. "
        f"Expected empty list [], got {ranges}"
    )


def test_parse_line_ranges_no_full():
    """Test _parse_line_ranges without 'full' (should work as before)."""
    memory = WorkingMemory(current_task="Test")
    
    ranges = memory._parse_line_ranges("10-20,30-40")
    
    # Should return [LineRange(10, 20), LineRange(30, 40)]
    print(f"_parse_line_ranges('10-20,30-40') = {ranges}")
    
    assert ranges == [LineRange(10, 20), LineRange(30, 40)], (
        f"Expected [LineRange(10, 20), LineRange(30, 40)], got {ranges}"
    )


if __name__ == "__main__":
    print("Testing bug: 'full,10-20' doesn't return empty list")
    print("=" * 60)
    
    try:
        test_parse_line_ranges_full_with_ranges()
        print("✓ test_parse_line_ranges_full_with_ranges: PASS")
    except AssertionError as e:
        print(f"✗ test_parse_line_ranges_full_with_ranges: FAIL - {e}")
    
    try:
        test_parse_line_ranges_ranges_with_full()
        print("✓ test_parse_line_ranges_ranges_with_full: PASS")
    except AssertionError as e:
        print(f"✗ test_parse_line_ranges_ranges_with_full: FAIL - {e}")
    
    test_parse_line_ranges_full_alone()
    print("✓ test_parse_line_ranges_full_alone: PASS")
    
    try:
        test_parse_line_ranges_multiple_full()
        print("✓ test_parse_line_ranges_multiple_full: PASS")
    except AssertionError as e:
        print(f"✗ test_parse_line_ranges_multiple_full: FAIL - {e}")
    
    test_parse_line_ranges_no_full()
    print("✓ test_parse_line_ranges_no_full: PASS")