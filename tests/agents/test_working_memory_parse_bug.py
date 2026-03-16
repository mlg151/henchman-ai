"""Test for the _parse_line_ranges bug in working_memory.py.

This test demonstrates the bug where _parse_line_ranges returns empty list
if ANY part of the lines_read string is invalid, instead of skipping invalid parts.
"""

import pytest
from henchman.agents.working_memory import WorkingMemory, LineRange


def test_parse_line_ranges_skips_invalid_parts():
    """Test that _parse_line_ranges skips invalid parts instead of returning empty list.
    
    BUG: Currently returns [] if any part is invalid.
    Should skip invalid parts and return valid ranges.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Test 1: Mixed valid and invalid (0-5 is invalid because 0 < 1)
    ranges = memory._parse_line_ranges("10-50,0-5,60-100")
    # BUG: Returns [] (empty list)
    # FIX: Should return [LineRange(10, 50), LineRange(60, 100)]
    assert ranges == [
        LineRange(10, 50),
        LineRange(60, 100),
    ], f"Expected [LineRange(10, 50), LineRange(60, 100)], got {ranges}"
    
    # Test 2: Mixed valid and non-integer
    ranges = memory._parse_line_ranges("10-50,abc,60-100")
    # BUG: Returns [] (empty list)
    # FIX: Should return [LineRange(10, 50), LineRange(60, 100)]
    assert ranges == [
        LineRange(10, 50),
        LineRange(60, 100),
    ], f"Expected [LineRange(10, 50), LineRange(60, 100)], got {ranges}"
    
    # Test 3: Mixed valid and invalid start > end
    ranges = memory._parse_line_ranges("10-50,60-55,70-100")  # 60-55 is invalid (start > end)
    # BUG: Returns [] (empty list)
    # FIX: Should return [LineRange(10, 50), LineRange(70, 100)]
    assert ranges == [
        LineRange(10, 50),
        LineRange(70, 100),
    ], f"Expected [LineRange(10, 50), LineRange(70, 100)], got {ranges}"
    
    # Test 4: All invalid should return empty list
    ranges = memory._parse_line_ranges("0-5,abc,10-5")
    # Should return [] (all parts invalid)
    assert ranges == [], f"Expected [] (all invalid), got {ranges}"
    
    # Test 5: Single invalid part
    ranges = memory._parse_line_ranges("0-5")
    # Should return [] (invalid)
    assert ranges == [], f"Expected [] (invalid), got {ranges}"
    
    # Test 6: Valid single range should work
    ranges = memory._parse_line_ranges("10-50")
    # Should return [LineRange(10, 50)]
    assert ranges == [LineRange(10, 50)], f"Expected [LineRange(10, 50)], got {ranges}"
    
    # Test 7: Valid multiple ranges should work
    ranges = memory._parse_line_ranges("10-50,60-100")
    # Should return [LineRange(10, 50), LineRange(60, 100)]
    assert ranges == [
        LineRange(10, 50),
        LineRange(60, 100),
    ], f"Expected [LineRange(10, 50), LineRange(60, 100)], got {ranges}"


def test_should_read_file_with_mixed_valid_invalid_lines_read():
    """Test that should_read_file works correctly when lines_read has mixed valid/invalid parts.
    
    When an entry has lines_read="10-50,0-5,60-100" (0-5 is invalid),
    the entry should be ACCEPTED (after fix) because it has valid parts.
    Invalid parts are skipped.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Add entry with mixed valid/invalid lines_read
    from henchman.agents.working_memory import WorkingMemoryEntry
    
    # Should be ACCEPTED (after fix) because it has valid parts (10-50, 60-100)
    # Invalid part (0-5) is skipped
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="10-50,0-5,60-100",  # 0-5 is invalid but will be skipped
    )
    memory.add_recent_file(entry)
    
    # Request lines that are in valid ranges
    should_read, reason = memory.should_read_file("/test/file.py", 20, 40)
    # Should return False (lines 20-40 are within 10-50)
    assert should_read is False
    assert "already read" in reason.lower()
    # FIX: Should return False (lines 20-40 are within 10-50)
    assert should_read is False, (
        f"Lines 20-40 are within valid range 10-50. "
        f"Should return False. Got: {should_read}, reason: {reason}"
    )
    assert "already read" in reason.lower()
    
    # Request lines that are NOT in valid ranges (in gap 51-59)
    should_read2, reason2 = memory.should_read_file("/test/file.py", 55, 58)
    # Should return True (gap 51-59 not read)
    assert should_read2 is True, (
        f"Lines 55-58 are in gap between 50 and 60. "
        f"Should return True. Got: {should_read2}, reason: {reason2}"
    )
    assert "need to be read" in reason2.lower() or "gap" in reason2.lower()


if __name__ == "__main__":
    # Run tests to demonstrate bug
    import sys
    
    print("Running _parse_line_ranges bug tests...")
    print("=" * 60)
    
    tests = [
        test_parse_line_ranges_skips_invalid_parts,
        test_should_read_file_with_mixed_valid_invalid_lines_read,
    ]
    
    failures = 0
    for test in tests:
        print(f"\nRunning {test.__name__}...")
        try:
            test()
            print("  ✓ PASS")
        except AssertionError as e:
            print(f"  ✗ FAIL: {e}")
            failures += 1
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            failures += 1
    
    print(f"\n" + "=" * 60)
    print(f"Total: {len(tests)} tests, {failures} failures")
    sys.exit(1 if failures > 0 else 0)