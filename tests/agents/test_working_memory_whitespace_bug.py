"""Test for the whitespace-only lines_read bug in working_memory.py.

Demonstrates the inconsistency between _parse_line_ranges and _validate_lines_read.
"""

import pytest
from henchman.agents.working_memory import (
    WorkingMemory,
    WorkingMemoryEntry,
    WorkingMemory as WMClass,
)


def test_parse_line_ranges_whitespace_only():
    """Test _parse_line_ranges with whitespace-only string."""
    memory = WorkingMemory(current_task="Test")
    
    # _parse_line_ranges should return [] for whitespace-only string
    ranges = memory._parse_line_ranges("   ")
    assert ranges == [], f"_parse_line_ranges('   ') returned {ranges}, expected []"
    
    ranges = memory._parse_line_ranges("\t\t")
    assert ranges == [], f"_parse_line_ranges('\\t\\t') returned {ranges}, expected []"
    
    ranges = memory._parse_line_ranges("\n\n")
    assert ranges == [], f"_parse_line_ranges('\\n\\n') returned {ranges}, expected []"
    
    ranges = memory._parse_line_ranges(" \t\n ")
    assert ranges == [], f"_parse_line_ranges(' \\t\\n ') returned {ranges}, expected []"
    
    print("✓ _parse_line_ranges returns [] for whitespace-only strings")


def test_validate_lines_read_whitespace_only():
    """Test _validate_lines_read with whitespace-only string.
    
    After fix: whitespace-only strings should be valid (treated as empty string).
    """
    # _validate_lines_read should NOT raise ValueError for whitespace-only string
    # (after fix, whitespace-only is treated as valid "no lines read")
    WorkingMemoryEntry._validate_lines_read("   ")  # Should not raise
    WorkingMemoryEntry._validate_lines_read("\t\t")  # Should not raise
    WorkingMemoryEntry._validate_lines_read("\n\n")  # Should not raise
    WorkingMemoryEntry._validate_lines_read(" \t\n ")  # Should not raise
    
    print("✓ _validate_lines_read accepts whitespace-only strings (after fix)")


def test_working_memory_entry_creation_whitespace_only():
    """Test creating WorkingMemoryEntry with whitespace-only lines_read.
    
    After fix: whitespace-only strings should be valid (treated as empty string).
    """
    # Should succeed (whitespace-only is valid "no lines read")
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="   ",  # Whitespace-only
        key_insights=[],
    )
    
    assert entry.lines_read == "   ", f"lines_read should be '   ', got: {entry.lines_read}"
    
    print("✓ WorkingMemoryEntry creation succeeds for whitespace-only lines_read (after fix)")


def test_inconsistency_impact():
    """Test the impact of the inconsistency.
    
    If a WorkingMemoryEntry is created with whitespace-only lines_read
    (e.g., via deserialization bypassing validation), _parse_line_ranges
    will treat it as "no lines read" (returns []), while _validate_lines_read
    would reject it.
    """
    # Simulate what happens if validation is bypassed
    memory = WorkingMemory(current_task="Test")
    
    # Create entry with empty string (valid)
    entry1 = WorkingMemoryEntry("/test/file1.py", "Test", "", [])
    memory.add_recent_file(entry1)
    
    # _parse_line_ranges("") returns []
    ranges1 = memory._parse_line_ranges("")
    assert ranges1 == [], "Empty string should return []"
    
    # Now test with a hypothetical whitespace-only string
    # (Can't create WorkingMemoryEntry with it, but if we could...)
    # _parse_line_ranges("   ") also returns []
    ranges2 = memory._parse_line_ranges("   ")
    assert ranges2 == [], "Whitespace-only string should return []"
    
    # Both empty string and whitespace-only string result in []
    # But _validate_lines_read treats them differently!
    
    print("✓ Inconsistency: Both '' and '   ' result in [] from _parse_line_ranges")
    print("  But _validate_lines_read rejects '   ' and accepts ''")


def test_should_read_file_with_empty_lines_read():
    """Test should_read_file behavior with empty lines_read.
    
    Empty lines_read means "no lines have been read".
    """
    memory = WorkingMemory(current_task="Test")
    
    # Add entry with empty lines_read (valid)
    entry = WorkingMemoryEntry("/test/file.py", "Test", "", [])
    memory.add_recent_file(entry)
    
    # Request lines 10-20
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)
    
    # Should return True (need to read)
    assert should_read is True, f"Empty lines_read means no lines read. Should return True. Got: {should_read}"
    assert "no lines" in reason.lower() or "not read" in reason.lower(), (
        f"Reason should indicate no lines read. Got: {reason}"
    )
    
    print(f"✓ should_read_file with empty lines_read: should_read={should_read}, reason={reason}")


def test_fix_whitespace_consistency():
    """Test the fix: whitespace-only strings should be treated like empty strings.
    
    After fix: _validate_lines_read should NOT raise ValueError for whitespace-only strings.
    They should be treated as valid "no lines read", same as empty string.
    """
    # This test will FAIL with current implementation
    # After fix, it should PASS
    
    # Currently raises ValueError - this is the bug!
    try:
        WorkingMemoryEntry._validate_lines_read("   ")
        print("✓ After fix: _validate_lines_read accepts whitespace-only string")
    except ValueError as e:
        print(f"✗ Before fix: _validate_lines_read rejects whitespace-only string: {e}")
        # Re-raise to make test fail (demonstrating bug)
        raise AssertionError(
            "Bug: _validate_lines_read raises ValueError for whitespace-only string, "
            "but _parse_line_ranges returns [] for same input. Inconsistent!"
        )


if __name__ == "__main__":
    test_parse_line_ranges_whitespace_only()
    test_validate_lines_read_whitespace_only()
    test_working_memory_entry_creation_whitespace_only()
    test_inconsistency_impact()
    test_should_read_file_with_empty_lines_read()
    
    print("\n" + "="*60)
    print("Demonstrating the bug (test should fail):")
    print("="*60)
    try:
        test_fix_whitespace_consistency()
        print("\n✓ All tests pass (bug is fixed)")
    except AssertionError as e:
        print(f"\n✗ Test failed (demonstrating bug): {e}")
        print("\nThis is the bug: inconsistent handling of whitespace-only strings!")