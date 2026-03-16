"""Test to find a real bug in working_memory.py."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry, LineRange


def test_memory_should_read_file_float_end_minus_one():
    """Test should_read_file with float -1.0 (should be treated as -1).
    
    BUG: The comment says "Accept both int -1 and float -1.0" but
    the code uses `end == -1` which works for float -1.0 because
    -1.0 == -1 is True in Python. However, what about -1.1? That's
    also < 1 and != -1, so it would fail validation.
    
    Actually, that's correct - only -1 should be accepted.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="full"
    ))
    
    # Test with float -1.0
    should_read, reason = memory.should_read_file("/test/file.py", 1, -1.0)
    print(f"float -1.0: should_read={should_read}, reason={reason}")
    # Should return False (file read fully)
    assert should_read is False, f"float -1.0 should be treated as -1. Got: {should_read}"
    assert "already read" in reason.lower()
    
    # Test with float -1.1 (invalid)
    should_read2, reason2 = memory.should_read_file("/test/file.py", 1, -1.1)
    print(f"float -1.1: should_read={should_read2}, reason={reason2}")
    # Should return True with error
    assert should_read2 is True, f"float -1.1 should be invalid. Got: {should_read2}"
    assert "invalid" in reason2.lower() or "positive" in reason2.lower()


def test_memory_should_read_file_none_validation_order():
    """Test that validation happens in correct order.
    
    BUG POTENTIAL: What if start=None, end=None? The validation
    at line 510 checks `if end is not None:` but end is None,
    so it skips validation. That's correct.
    
    But what about the check `if end < 1 and end != -1:` when
    end is None? It doesn't execute because of the `if end is not None:` guard.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="10-50"
    ))
    
    # Test with start=None, end=None
    should_read, reason = memory.should_read_file("/test/file.py")
    print(f"None, None: should_read={should_read}, reason={reason}")
    # Should return True (file not fully read)
    assert should_read is True
    assert "not fully read" in reason.lower() or "partial" in reason.lower()


def test_memory_parse_line_ranges_unicode_digits():
    """Test _parse_line_ranges with Unicode digits.
    
    BUG: The code uses .isdecimal() which accepts Arabic digits (٠١٢٣...).
    But int() might not parse them correctly? Actually, int() does parse
    Arabic digits in Python!
    """
    memory = WorkingMemory(current_task="Test")
    
    # Test with Arabic digits (٠ = 0, ١ = 1, ٢ = 2, etc.)
    # Arabic digit ١ is 1, ١٠ is 10
    ranges = memory._parse_line_ranges("١-١٠")  # "1-10" in Arabic digits
    print(f"Arabic digits ١-١٠: {ranges}")
    # Should parse as LineRange(1, 10)
    assert len(ranges) == 1
    assert ranges[0].start == 1
    assert ranges[0].end == 10
    
    # Test with mixed (should fail)
    ranges2 = memory._parse_line_ranges("1-١٠")  # Mixed Arabic and Latin
    print(f"Mixed 1-١٠: {ranges2}")
    # .isdecimal() returns True for Arabic ١٠, so it might parse?
    # Actually, int("١٠") = 10 in Python!
    if ranges2:
        print(f"  Parsed as: {ranges2[0]}")


def test_memory_should_read_file_negative_start():
    """Test should_read_file with negative start line.
    
    BUG: start=-5 should be invalid (lines are 1-indexed).
    The code checks `if start < 1:` which catches this.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="10-50"
    ))
    
    should_read, reason = memory.should_read_file("/test/file.py", -5, 10)
    print(f"start=-5: should_read={should_read}, reason={reason}")
    assert should_read is True
    assert "invalid" in reason.lower() or "positive" in reason.lower()


def test_memory_working_memory_entry_validation():
    """Test WorkingMemoryEntry validation.
    
    BUG POTENTIAL: What if lines_read is None? The __post_init__
    checks `if self.lines_read is not None and not isinstance(self.lines_read, str):`
    So if lines_read is None, it skips validation. That might be okay?
    """
    # Test with lines_read=None
    try:
        entry = WorkingMemoryEntry(
            path="/test/file.py",
            purpose="Test",
            lines_read=None,  # type: ignore
            key_insights=[]
        )
        print(f"lines_read=None created successfully: {entry}")
        # Should this be allowed?
    except Exception as e:
        print(f"lines_read=None raised: {e}")
    
    # Test with lines_read as empty string
    entry2 = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="",
        key_insights=[]
    )
    print(f"lines_read='' created successfully: {entry2}")


if __name__ == "__main__":
    print("Running bug finding tests...")
    print("=" * 60)
    
    tests = [
        test_memory_should_read_file_float_end_minus_one,
        test_memory_should_read_file_none_validation_order,
        test_memory_parse_line_ranges_unicode_digits,
        test_memory_should_read_file_negative_start,
        test_memory_working_memory_entry_validation,
    ]
    
    for test in tests:
        print(f"\n{test.__name__}...")
        try:
            test()
            print("  ✓ PASS")
        except AssertionError as e:
            print(f"  ✗ FAIL: {e}")
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
    
    print("\n" + "=" * 60)
    print("Tests completed.")