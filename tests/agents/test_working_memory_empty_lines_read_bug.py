"""Test bug with empty lines_read."""

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_memory_empty_lines_read():
    """Test that empty lines_read is handled correctly.

    BUG: Empty lines_read string is considered valid by _validate_lines_read,
    but _parse_line_ranges returns empty list, and should_read_file treats
    empty valid_ranges as "invalid lines_read format".
    """
    # Create entry with empty lines_read
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="",  # Empty string
        key_insights=[]
    )
    print(f"Created entry with lines_read='': {entry}")

    # This should not raise ValueError (empty string is valid)
    # Actually, it does validate in __post_init__

    # Now test should_read_file
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(entry)

    # Request lines 10-20
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)

    print(f"lines_read='', request 10-20: should_read={should_read}, reason={reason}")

    # What SHOULD happen?
    # Option 1: Empty lines_read means "no lines read", so should_read=True
    # Option 2: Current behavior: "Cannot determine - invalid lines_read format"

    # Actually, looking at the code:
    # - _parse_line_ranges("") returns []
    # - valid_ranges is empty
    # - File wasn't read "full" (lines_read is "", not "full")
    # - At line ~545: if not valid_ranges: return True, "Cannot determine - invalid lines_read format"

    # After fix: Empty lines_read means "no lines read", not "invalid format"
    assert should_read is True
    assert "no lines" in reason.lower() or "not read" in reason.lower()

    # This is correct! Empty lines_read means "no lines read",
    # so we should read the file!
    # Actually, "Cannot determine - invalid lines_read format" returns True (should read).
    # So the outcome is correct (should read), but the reason is misleading.


def test_memory_whitespace_lines_read():
    """Test whitespace-only lines_read.

    After fix: whitespace-only strings should be valid (treated as empty string).
    """
    # Create entry with whitespace lines_read should NOT raise ValueError (after fix)
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="   ",  # Only spaces
        key_insights=[]
    )

    assert entry.lines_read == "   ", f"lines_read should be '   ', got: {entry.lines_read}"

    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(entry)

    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)

    print(f"lines_read='   ', request 10-20: should_read={should_read}, reason={reason}")

    # Whitespace-only string is valid "no lines read" (same as empty string)
    assert should_read is True
    # Reason can be "Cannot determine - no valid line ranges" or similar
    assert "no valid" in reason.lower() or "cannot determine" in reason.lower() or "no lines" in reason.lower() or "not read" in reason.lower()

    # Test with empty string (should still work)
    entry2 = WorkingMemoryEntry(
        path="/test/file2.py",
        purpose="Test",
        lines_read="",  # Empty string
        key_insights=[]
    )

    memory.add_recent_file(entry2)

    should_read2, reason2 = memory.should_read_file("/test/file2.py", 10, 20)

    print(f"lines_read='', request 10-20: should_read={should_read2}, reason={reason2}")

    # Empty string is valid "no lines read"
    assert should_read2 is True
    # Reason can be "Cannot determine - no valid line ranges" or similar
    assert "no valid" in reason2.lower() or "cannot determine" in reason2.lower() or "no lines" in reason2.lower() or "not read" in reason2.lower()


def test_memory_none_lines_read():
    """Test lines_read=None (from deserialization)."""
    # Can't create with lines_read=None due to type annotation (str, not Optional[str])
    # But __post_init__ handles None: "lines_read may be None during deserialization"

    # Test _parse_line_ranges directly: it should handle None
    from henchman.agents.line_range_utils import parse_line_ranges
    ranges = parse_line_ranges(None)  # type: ignore
    print(f"parse_line_ranges(None) = {ranges}")
    assert ranges == []

    # What about in should_read_file? We can't add entry with lines_read=None
    # But if it comes from deserialization, lines_read could be None
    # Actually, WorkingMemoryEntry.__post_init__ says "lines_read may be None during deserialization"
    # So we need to handle it.


if __name__ == "__main__":
    print("Testing empty lines_read bug...")
    print("=" * 60)

    tests = [
        test_memory_empty_lines_read,
        test_memory_whitespace_lines_read,
        test_memory_none_lines_read,
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
