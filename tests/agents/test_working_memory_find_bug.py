"""Test to find a bug in working_memory.py."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry, LineRange


def test_parse_line_ranges_empty_string():
    """Test _parse_line_ranges with empty string."""
    result = WorkingMemory._parse_line_ranges("")
    assert result == []  # Empty string means no lines read


def test_parse_line_ranges_whitespace_only():
    """Test _parse_line_ranges with whitespace-only string."""
    result = WorkingMemory._parse_line_ranges("   ")
    assert result == []  # Whitespace-only becomes empty after normalization


def test_parse_line_ranges_invalid_characters():
    """Test _parse_line_ranges with invalid characters."""
    # Test with letters
    result = WorkingMemory._parse_line_ranges("abc")
    assert result == []
    
    # Test with decimal point
    result = WorkingMemory._parse_line_ranges("10.5")
    assert result == []  # .isdecimal() returns False for "10.5"
    
    # Test with negative sign (not dash between numbers)
    result = WorkingMemory._parse_line_ranges("-10")
    assert result == []  # .isdecimal() returns False for "-10"


def test_parse_line_ranges_leading_zeros():
    """Test _parse_line_ranges with leading zeros."""
    # Single line with leading zero
    result = WorkingMemory._parse_line_ranges("01")
    assert len(result) == 1
    assert result[0].start == 1
    assert result[0].end == 1
    
    # Range with leading zeros
    result = WorkingMemory._parse_line_ranges("01-05")
    assert len(result) == 1
    assert result[0].start == 1
    assert result[0].end == 5
    
    # "00" should be rejected (line 0 is invalid)
    result = WorkingMemory._parse_line_ranges("00")
    assert result == []


def test_parse_line_ranges_unicode_digits():
    """Test _parse_line_ranges with Unicode digits."""
    # Arabic digits (٠١٢٣) - .isdecimal() returns True for these!
    # int() CAN parse Arabic digits in Python
    result = WorkingMemory._parse_line_ranges("١-١٠")  # 1-10 in Arabic digits
    # .isdecimal() returns True, and int() can parse them
    # So they should be accepted
    assert len(result) == 1
    assert result[0].start == 1
    assert result[0].end == 10


def test_validate_lines_read_empty_string():
    """Test _validate_lines_read with empty string."""
    # Should not raise
    WorkingMemoryEntry._validate_lines_read("")


def test_validate_lines_read_whitespace_only():
    """Test _validate_lines_read with whitespace-only string."""
    # Should NOT raise ValueError (after fix)
    WorkingMemoryEntry._validate_lines_read("   ")  # Should not raise
    WorkingMemoryEntry._validate_lines_read("\t\t")  # Should not raise
    WorkingMemoryEntry._validate_lines_read("\n\n")  # Should not raise


def test_validate_lines_read_inconsistent_with_parse():
    """Test if _validate_lines_read and _parse_line_ranges are consistent."""
    # Cases where they might disagree
    test_cases = [
        ("", True, []),  # Empty: valid, parses to []
        ("   ", True, []),  # Whitespace-only: valid (after fix), parses to []
        ("full", True, []),  # "full": valid, parses to []
        ("full,10-20", True, []),  # "full" with range: valid, parses to []
        ("10-20,full", True, []),  # Range with "full": valid, parses to []
        ("invalid", False, []),  # Invalid: invalid, parses to []
        ("10-20,invalid", True, [LineRange(10, 20)]),  # Mixed: NOW VALID (after fix), _parse_line_ranges skips invalid part
        ("10-20,30-40", True, [LineRange(10, 20), LineRange(30, 40)]),  # Valid ranges
    ]
    
    for lines_read, should_be_valid, expected_ranges in test_cases:
        # Test _validate_lines_read
        try:
            WorkingMemoryEntry._validate_lines_read(lines_read)
            is_valid = True
        except ValueError:
            is_valid = False
        
        # Test _parse_line_ranges
        parsed = WorkingMemory._parse_line_ranges(lines_read)
        
        print(f"'{lines_read}': valid={is_valid}, parsed={parsed}, expected_valid={should_be_valid}, expected_ranges={expected_ranges}")
        
        # Check consistency
        if should_be_valid:
            assert is_valid, f"'{lines_read}' should be valid but _validate_lines_read raised"
        else:
            assert not is_valid, f"'{lines_read}' should be invalid but _validate_lines_read didn't raise"
        
        # Check parsing
        assert parsed == expected_ranges, f"'{lines_read}' parsed to {parsed}, expected {expected_ranges}"


def test_should_read_file_with_zero_line():
    """Test should_read_file with line 0 (invalid)."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-50"))
    
    # Test with start=0 (invalid)
    should_read, reason = memory.should_read_file("/test/file.py", 0, 10)
    print(f"start=0, end=10: should_read={should_read}, reason={reason}")
    assert should_read is True
    assert "positive" in reason.lower() or "invalid" in reason.lower()
    
    # Test with end=0 (invalid, different from end=-1)
    should_read, reason = memory.should_read_file("/test/file.py", 10, 0)
    print(f"start=10, end=0: should_read={should_read}, reason={reason}")
    assert should_read is True
    assert "positive" in reason.lower() or "invalid" in reason.lower()


def test_should_read_file_validation_order():
    """Test validation order in should_read_file.
    
    BUG POTENTIAL: What if start is invalid (e.g., string) and end is also invalid?
    Which error is reported?
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-50"))
    
    # Test with start as string, end as string
    should_read, reason = memory.should_read_file("/test/file.py", "abc", "xyz")
    print(f"start='abc', end='xyz': should_read={should_read}, reason={reason}")
    assert should_read is True
    # Should report error about start (first validation)
    assert "start" in reason.lower()
    
    # Test with start valid, end as string
    should_read, reason = memory.should_read_file("/test/file.py", 10, "xyz")
    print(f"start=10, end='xyz': should_read={should_read}, reason={reason}")
    assert should_read is True
    # Should report error about end
    assert "end" in reason.lower()
    
    # Test with start as string, end valid
    should_read, reason = memory.should_read_file("/test/file.py", "abc", 10)
    print(f"start='abc', end=10: should_read={should_read}, reason={reason}")
    assert should_read is True
    # Should report error about start
    assert "start" in reason.lower()


if __name__ == "__main__":
    print("Running bug-finding tests...")
    print("=" * 60)
    
    tests = [
        test_parse_line_ranges_empty_string,
        test_parse_line_ranges_whitespace_only,
        test_parse_line_ranges_invalid_characters,
        test_parse_line_ranges_leading_zeros,
        test_parse_line_ranges_unicode_digits,
        test_validate_lines_read_empty_string,
        test_validate_lines_read_whitespace_only,
        test_validate_lines_read_inconsistent_with_parse,
        test_should_read_file_with_zero_line,
        test_should_read_file_validation_order,
    ]
    
    for test in tests:
        print(f"\nRunning {test.__name__}...")
        try:
            test()
            print("  ✓ PASS")
        except AssertionError as e:
            print(f"  ✗ FAIL: {e}")
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
    
    print("\n" + "=" * 60)
    print("Tests complete.")