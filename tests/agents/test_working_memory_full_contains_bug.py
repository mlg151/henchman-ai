"""Test for bug where lines_read containing 'full' but not exactly 'full' is not recognized."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_lines_read_contains_full_but_not_exact():
    """Test bug: lines_read='full,10-20' should still mean file was read fully."""
    memory = WorkingMemory(current_task="Test")
    
    # Add entry with lines_read containing 'full' but not exactly 'full'
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="full,10-20",  # Contains 'full' but not exactly 'full'
        key_insights=[],
    )
    memory.add_recent_file(entry)
    
    # Request lines 1-100
    should_read, reason = memory.should_read_file("/test/file.py", 1, 100)
    
    print(f"Test - lines_read='full,10-20':")
    print(f"  should_read={should_read}, reason={reason}")
    
    # BUG: Returns True (should read) because "full,10-20" != "full"
    # Should return False (file was read fully)
    assert should_read is False, (
        f"lines_read='full,10-20' contains 'full', so file should be considered fully read. "
        f"Got: should_read={should_read}, reason={reason}"
    )
    assert "already read" in reason.lower()


def test_lines_read_full_with_extra_spaces():
    """Test: lines_read='  full  ' should work (already works)."""
    memory = WorkingMemory(current_task="Test")
    
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="  full  ",  # Extra spaces
        key_insights=[],
    )
    memory.add_recent_file(entry)
    
    should_read, reason = memory.should_read_file("/test/file.py", 1, 100)
    
    print(f"\nTest - lines_read='  full  ' (extra spaces):")
    print(f"  should_read={should_read}, reason={reason}")
    
    # This should work (normalization removes spaces)
    assert should_read is False
    assert "already read" in reason.lower()


def test_lines_read_full_with_other_text():
    """Test: lines_read='full file was read' should be rejected as invalid.
    
    With the fix, WorkingMemoryEntry validates lines_read and rejects invalid formats.
    'full file was read' is not a valid format (not parseable as line ranges).
    """
    # Should raise ValueError because 'full file was read' is not a valid lines_read format
    with pytest.raises(ValueError, match="Invalid lines_read"):
        entry = WorkingMemoryEntry(
            path="/test/file.py",
            purpose="Test",
            lines_read="full file was read",  # Contains 'full' but with other text
            key_insights=[],
        )
    
    print(f"\nTest - lines_read='full file was read':")
    print(f"  ✓ Correctly rejected as invalid format")


def test_lines_read_multiple_parts_with_full():
    """Test: lines_read='full,additional info' should be ACCEPTED (after fix).
    
    Even though 'full' is present, 'additional info' is not a valid line range.
    But _parse_line_ranges returns [] for any string containing "full" (regardless of other parts).
    So validation should accept it to be consistent.
    """
    # Should be ACCEPTED (after fix) because 'full' is present
    # _parse_line_ranges returns [] for "full,additional info"
    # Validation should match parsing
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="full,additional info",  # 'full' with invalid 'additional info'
        key_insights=[],
    )
    assert entry.lines_read == "full,additional info"
    
    # parse_line_ranges returns [] for this
    from henchman.agents.line_range_utils import parse_line_ranges
    ranges = parse_line_ranges("full,additional info")
    assert ranges == []
    
    print(f"\nTest - lines_read='full,additional info':")
    print(f"  ✓ Correctly accepted (contains 'full', invalid parts ignored)")


def test_parse_line_ranges_with_full_and_ranges():
    """Test _parse_line_ranges with 'full,10-20'."""
    from henchman.agents.line_range_utils import parse_line_ranges
    
    # Test parse_line_ranges directly
    ranges = parse_line_ranges("full,10-20")
    print(f"\nTest _parse_line_ranges('full,10-20'):")
    print(f"  ranges={ranges}")
    
    # Returns [LineRange(10, 20)] - ignores 'full'
    # This is wrong! 'full' should take precedence.


if __name__ == "__main__":
    print("Testing bug: lines_read containing 'full' not recognized...")
    print("=" * 60)
    
    try:
        test_lines_read_contains_full_but_not_exact()
        print("  ✗ FAIL: Test should have failed (bug exists)")
    except AssertionError as e:
        print(f"  ✓ PASS: Bug confirmed: {e}")
    
    test_lines_read_full_with_extra_spaces()
    print("  ✓ PASS: Extra spaces handled correctly")
    
    test_parse_line_ranges_with_full_and_ranges()
    
    print("\n" + "=" * 60)
    print("Bug confirmed: lines_read='full,10-20' is not recognized as 'full'")