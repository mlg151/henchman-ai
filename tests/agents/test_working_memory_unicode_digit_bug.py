"""Test for Unicode digit bug in working_memory.py."""

import pytest
from henchman.agents.working_memory import WorkingMemory


def test_parse_line_ranges_unicode_superscript_digit():
    """Test _parse_line_ranges with Unicode superscript digits.
    
    BUG: str.isdigit() returns True for superscript digits like '²' (superscript 2),
    but int('²') raises ValueError. The code should handle this.
    """
    from henchman.agents.line_range_utils import parse_line_ranges
    
    # Test with superscript digit (² is superscript 2)
    # '²'.isdigit() returns True, but int('²') raises ValueError
    ranges = parse_line_ranges("¹⁰-²⁰")  # superscript 10-20
    
    # Should return empty list (invalid) or handle gracefully
    # Currently: '¹⁰'.isdigit() returns True, int('¹⁰') raises ValueError
    # So it will skip this part (continue in the loop)
    assert ranges == []  # Or maybe should handle differently


def test_parse_line_ranges_arabic_digits():
    """Test _parse_line_ranges with Arabic digits.
    
    Arabic digits like '٣' (Arabic digit 3) are valid for int().
    """
    from henchman.agents.line_range_utils import parse_line_ranges
    
    # Test with Arabic digits (٣ is Arabic 3, ٥ is Arabic 5)
    ranges = parse_line_ranges("٣-٥")  # Arabic 3-5
    
    # int('٣') works (returns 3), int('٥') works (returns 5)
    # So should parse successfully
    assert len(ranges) == 1
    assert ranges[0].start == 3
    assert ranges[0].end == 5


def test_parse_line_ranges_mixed_digits():
    """Test _parse_line_ranges with mixed regular and Unicode digits."""
    from henchman.agents.line_range_utils import parse_line_ranges
    
    # Test with regular digits (should work)
    ranges = parse_line_ranges("10-20")
    assert len(ranges) == 1
    assert ranges[0].start == 10
    assert ranges[0].end == 20
    
    # Test with string containing non-digit characters
    ranges = parse_line_ranges("10a-20")  # '10a' is not all digits
    assert ranges == []  # Should skip
    
    ranges = parse_line_ranges("10-20b")  # '20b' is not all digits
    assert ranges == []  # Should skip


def test_should_read_file_with_unicode_digits():
    """Test should_read_file when lines_read contains Unicode digits."""
    memory = WorkingMemory(current_task="Test")
    
    # Add entry with Arabic digits
    from henchman.agents.working_memory import WorkingMemoryEntry
    # Can't directly create with Arabic digits in lines_read because
    # it would be stored as string "٣-٥"
    # But let's test the parsing
    
    # Actually test the full flow
    entry = WorkingMemoryEntry("/test/file.py", "Test", "٣-٥")  # Arabic 3-5
    memory.add_recent_file(entry)
    
    # Request lines 3-5 (in regular digits)
    should_read, reason = memory.should_read_file("/test/file.py", 3, 5)
    
    # Should return False (already read lines 3-5)
    # But might fail because parsing Arabic digits might not work
    print(f"should_read={should_read}, reason={reason}")
    # This test might fail if the bug exists!


if __name__ == "__main__":
    # Run tests
    import sys
    
    tests = [
        test_parse_line_ranges_unicode_superscript_digit,
        test_parse_line_ranges_arabic_digits,
        test_parse_line_ranges_mixed_digits,
        test_should_read_file_with_unicode_digits,
    ]
    
    all_passed = True
    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__} passed")
        except AssertionError as e:
            print(f"✗ {test.__name__} failed: {e}")
            all_passed = False
        except Exception as e:
            print(f"✗ {test.__name__} error: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False
    
    if not all_passed:
        sys.exit(1)
    else:
        print("\nAll tests passed!")