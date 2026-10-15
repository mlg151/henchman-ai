"""Test for .isdigit() bug fix in working_memory.py.

This test demonstrates the bug and will fail before the fix,
then pass after the fix.
"""

import pytest

from henchman.agents.working_memory import LineRange, WorkingMemory, WorkingMemoryEntry


def test_line_range_from_str_superscript_digits():
    """Test LineRange.from_str with superscript digits.

    BUG: .isdigit() returns True for superscript digits,
    but int() raises ValueError.
    """
    # Superscript digits: ¹ (superscript 1), ² (superscript 2)
    result = LineRange.from_str("¹-²")

    # BEFORE FIX: Returns None (invalid, but only after ValueError is raised and caught)
    # AFTER FIX: Should return None (invalid, caught by .isdecimal() check)
    assert result is None, f"Expected None for superscript digits, got {result}"

    # Also test that ASCII digits still work
    result2 = LineRange.from_str("10-20")
    assert result2 is not None
    assert result2.start == 10
    assert result2.end == 20


def test_line_range_from_str_circled_digits():
    """Test LineRange.from_str with circled digits."""
    # Circled digits: ① (circled 1), ② (circled 2)
    result = LineRange.from_str("①-②")

    assert result is None, f"Expected None for circled digits, got {result}"


def test_line_range_from_str_arabic_digits():
    """Test LineRange.from_str with Arabic digits.

    Arabic digits should work - int() can parse them.
    """
    # Arabic digits: ١ (Arabic 1), ٢ (Arabic 2)
    result = LineRange.from_str("١-٢")

    # Arabic digits are valid decimal digits
    assert result is not None
    assert result.start == 1
    assert result.end == 2


def test_working_memory_with_superscript_in_lines_read():
    """Test WorkingMemory with superscript digits in lines_read.

    This tests the integration through should_read_file.

    With the fix, WorkingMemoryEntry validates lines_read and rejects
    superscript digits (not .isdecimal()).
    """
    # Should raise ValueError because superscript digits are not valid
    with pytest.raises(ValueError, match="Invalid lines_read"):
        entry = WorkingMemoryEntry(
            path="/test/file.py",
            purpose="Test",
            lines_read="¹-²",  # Superscript digits
            key_insights=[],
            timestamp="2025-01-01T00:00:00Z"
        )

    print("✓ WorkingMemoryEntry correctly rejects superscript digits in lines_read")

    # Test with valid Arabic digits (should work)
    memory = WorkingMemory(current_task="Test")
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="١-٢",  # Arabic digits
        key_insights=[],
        timestamp="2025-01-01T00:00:00Z"
    )
    memory.add_recent_file(entry)

    should_read, reason = memory.should_read_file("/test/file.py", start=1, end=2)
    # Should be already read (lines 1-2)
    assert should_read is False
    assert "already read" in reason.lower()

    print(f"✓ Arabic digits work correctly: {reason}")


def test_isdecimal_vs_isdigit_demonstration():
    """Demonstrate the difference between .isdecimal() and .isdigit()."""
    test_cases = [
        ("123", True, True, True),      # ASCII digits
        ("١٢٣", True, True, True),      # Arabic digits (valid for int())
        ("¹²³", True, False, False),    # Superscript digits (invalid for int())
        ("①②③", True, False, False),    # Circled digits (invalid for int())
    ]

    print("\nDemonstrating .isdigit() vs .isdecimal() bug:")
    for s, isdigit_result, isdecimal_result, int_works in test_cases:
        assert s.isdigit() is isdigit_result
        assert s.isdecimal() is isdecimal_result
        print(f"\n'{s}' (U+{ord(s[0]):04X}...):")
        print(f"  .isdigit() = {s.isdigit()} (expect {isdigit_result})")
        print(f"  .isdecimal() = {s.isdecimal()} (expect {isdecimal_result})")
        int_succeeded = False
        if s.isdigit():
            try:
                i = int(s)
                int_succeeded = True
                print(f"  int('{s}') = {i} ✓")
            except ValueError:
                print(f"  int('{s}') raises ValueError ✗")
        assert int_succeeded is int_works

    print("\nCONCLUSION: .isdecimal() correctly identifies strings that int() can parse.")
    print("           .isdigit() is too permissive.")


if __name__ == "__main__":
    # Run tests
    test_line_range_from_str_superscript_digits()
    test_line_range_from_str_circled_digits()
    test_line_range_from_str_arabic_digits()
    test_working_memory_with_superscript_in_lines_read()
    test_isdecimal_vs_isdigit_demonstration()

    print("\n" + "="*60)
    print("All tests pass (or would pass after fix).")
    print("The bug is that .isdigit() accepts invalid characters.")
    print("="*60)
