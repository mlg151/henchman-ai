"""Test for .isdigit() bug in working_memory.py."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry, LineRange


def test_parse_line_ranges_superscript_digits():
    """Test _parse_line_ranges with superscript digits.
    
    BUG: .isdigit() returns True for superscript digits like ¹²³,
    but int() raises ValueError on them.
    The code catches ValueError and continues, so it's handled,
    but it's inefficient and the error is silent.
    """
    # Can't test _parse_line_ranges directly (private)
    # Instead test through WorkingMemory
    print("Note: Can't test _parse_line_ranges directly (private method)")
    print("Testing through WorkingMemory instead...")


def test_parse_line_ranges_circled_digits():
    """Test parse_line_ranges with circled digits."""
    from henchman.agents.line_range_utils import parse_line_ranges
    # Circled digits: ① (circled 1), ② (circled 2)
    result = parse_line_ranges("①-②")
    
    # Should return empty list (invalid)
    assert result == []
    
    print("✓ parse_line_ranges('①-②') returns [] (invalid)")


def test_parse_line_ranges_arabic_digits():
    """Test _parse_line_ranges with Arabic digits.
    
    Arabic digits are valid: int('١') = 1
    """
    from henchman.agents.line_range_utils import parse_line_ranges
    # Arabic digits: ١ (Arabic 1), ٢ (Arabic 2)
    result = parse_line_ranges("١-٢")
    
    # Should parse successfully
    assert len(result) == 1
    assert result[0].start == 1
    assert result[0].end == 2
    
    print("✓ _parse_line_ranges('١-٢') returns LineRange(1, 2)")


def test_line_range_from_str_superscript():
    """Test LineRange.from_str with superscript digits."""
    result = LineRange.from_str("¹-²")
    
    # Should return None (invalid)
    assert result is None
    
    print("✓ LineRange.from_str('¹-²') returns None (invalid)")


def test_should_read_file_with_superscript_in_lines_read():
    """Test should_read_file when lines_read contains superscript digits."""
    # With the fix, WorkingMemoryEntry validates lines_read and rejects
    # superscript digits (not .isdecimal())
    with pytest.raises(ValueError, match="Invalid lines_read"):
        entry = WorkingMemoryEntry("/test/file.py", "Test", "¹-²")
    
    print(f"✓ WorkingMemoryEntry correctly rejects superscript digits in lines_read")
    
    # Test with valid Arabic digits (should work)
    memory = WorkingMemory(current_task="Test")
    entry = WorkingMemoryEntry("/test/file.py", "Test", "١-٢")  # Arabic digits
    memory.add_recent_file(entry)
    
    should_read, reason = memory.should_read_file("/test/file.py", start=1, end=2)
    # Should be already read (lines 1-2)
    assert should_read is False
    assert "already read" in reason.lower()
    
    print(f"✓ Arabic digits work correctly: {reason}")


def test_isdecimal_vs_isdigit():
    """Demonstrate the difference between .isdecimal() and .isdigit()."""
    test_cases = [
        ("123", True, True),      # ASCII digits
        ("١٢٣", True, True),      # Arabic digits (valid for int())
        ("¹²³", True, False),     # Superscript digits (invalid for int())
        ("①②③", True, False),     # Circled digits (invalid for int())
    ]
    
    for s, isdigit_result, isdecimal_result in test_cases:
        print(f"'{s}': .isdigit()={s.isdigit()}, .isdecimal()={s.isdecimal()}")
        if s.isdigit():
            try:
                i = int(s)
                print(f"  int('{s}') = {i} (success)")
            except ValueError:
                print(f"  int('{s}') raises ValueError")
    
    print("\nBUG: .isdigit() is too permissive. Should use .isdecimal() or check ASCII digits only.")


if __name__ == "__main__":
    test_parse_line_ranges_superscript_digits()
    test_parse_line_ranges_circled_digits()
    test_parse_line_ranges_arabic_digits()
    test_line_range_from_str_superscript()
    test_should_read_file_with_superscript_in_lines_read()
    test_isdecimal_vs_isdigit()
    
    print("\n" + "="*60)
    print("BUG FOUND: .isdigit() accepts characters that int() cannot parse.")
    print("This causes ValueError exceptions to be raised and caught silently.")
    print("Fix: Use .isdecimal() instead of .isdigit().")
    print("="*60)