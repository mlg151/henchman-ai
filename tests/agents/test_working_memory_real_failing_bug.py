"""Test for a real failing bug in working_memory.py."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_memory_should_read_file_whitespace_only_bug():
    """Test bug with whitespace-only lines_read.
    
    After fix: _validate_lines_read should reject whitespace-only strings.
    """
    # This should raise ValueError (whitespace-only is invalid)
    with pytest.raises(ValueError, match="whitespace-only"):
        WorkingMemoryEntry(
            path="/test/file.py",
            purpose="Test",
            lines_read="   ",  # Only spaces
            key_insights=[]
        )
    
    # Test with empty string (should still work)
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="",  # Empty string
        key_insights=[]
    )
    
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(entry)
    
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)
    
    print(f"lines_read='', request 10-20: {should_read}, {reason}")
    
    # Empty string is valid "no lines read"
    assert should_read is True
    assert "no lines" in reason.lower() or "not read" in reason.lower()


def test_memory_validate_lines_read_whitespace():
    """Test _validate_lines_read with whitespace."""
    from henchman.agents.working_memory import WorkingMemoryEntry
    
    # Test empty string (should pass)
    try:
        WorkingMemoryEntry._validate_lines_read("")
        print("Empty string: VALID")
    except ValueError as e:
        print(f"Empty string: INVALID - {e}")
    
    # Test whitespace-only (should fail after fix)
    try:
        WorkingMemoryEntry._validate_lines_read("   ")
        print("Whitespace-only: VALID (BUG - should fail)")
    except ValueError as e:
        print(f"Whitespace-only: INVALID - {e} (CORRECT)")
    
    # Test "full" (should pass)
    try:
        WorkingMemoryEntry._validate_lines_read("full")
        print("'full': VALID")
    except ValueError as e:
        print(f"'full': INVALID - {e}")
    
    # Test "invalid" (should fail)
    try:
        WorkingMemoryEntry._validate_lines_read("invalid")
        print("'invalid': VALID (BUG!)")
    except ValueError as e:
        print(f"'invalid': INVALID - {e}")
    
    # Test "10-20" (should pass)
    try:
        WorkingMemoryEntry._validate_lines_read("10-20")
        print("'10-20': VALID")
    except ValueError as e:
        print(f"'10-20': INVALID - {e}")


def test_memory_parse_line_ranges_whitespace():
    """Test _parse_line_ranges with whitespace."""
    from henchman.agents.working_memory import WorkingMemory
    
    memory = WorkingMemory(current_task="Test")
    
    # Test empty string
    ranges = memory._parse_line_ranges("")
    print(f"_parse_line_ranges('') = {ranges}")
    assert ranges == []
    
    # Test whitespace-only
    ranges2 = memory._parse_line_ranges("   ")
    print(f"_parse_line_ranges('   ') = {ranges2}")
    assert ranges2 == []
    
    # Test "full"
    ranges3 = memory._parse_line_ranges("full")
    print(f"_parse_line_ranges('full') = {ranges3}")
    assert ranges3 == []
    
    # Test "10-20"
    ranges4 = memory._parse_line_ranges("10-20")
    print(f"_parse_line_ranges('10-20') = {ranges4}")
    assert len(ranges4) == 1
    assert ranges4[0].start == 10
    assert ranges4[0].end == 20


def test_memory_inconsistent_validation_bug():
    """Demonstrate the inconsistency bug (now fixed).
    
    After fix: _validate_lines_read rejects whitespace-only strings,
    so there's no inconsistency.
    """
    from henchman.agents.working_memory import WorkingMemoryEntry
    
    # Create entry with whitespace-only lines_read should raise ValueError
    with pytest.raises(ValueError, match="whitespace-only"):
        WorkingMemoryEntry(
            path="/test/file.py",
            purpose="Test",
            lines_read="   ",
            key_insights=[]
        )
    
    print("Whitespace-only strings are now rejected (bug fixed)")
    
    # Create entry with empty string (still valid)
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="",
        key_insights=[]
    )
    
    print(f"Created entry with lines_read='': {entry}")
    
    # Empty string is valid, but should_read_file still says "invalid lines_read format"
    # This is less severe than the whitespace-only inconsistency.


if __name__ == "__main__":
    print("Testing real failing bug...")
    print("=" * 60)
    
    tests = [
        test_memory_should_read_file_whitespace_only_bug,
        test_memory_validate_lines_read_whitespace,
        test_memory_parse_line_ranges_whitespace,
        test_memory_inconsistent_validation_bug,
    ]
    
    for test in tests:
        print(f"\n{test.__name__}...")
        try:
            test()
            print("  ✓ Test ran")
        except AssertionError as e:
            print(f"  ✗ FAIL: {e}")
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
    
    print("\n" + "=" * 60)
    print("Tests completed.")
    
    print("\nSUMMARY:")
    print("The bug is: _validate_lines_read accepts whitespace-only strings as valid,")
    print("but should_read_file treats them as 'invalid lines_read format'.")
    print("This is inconsistent. Either _validate_lines_read should reject")
    print("whitespace-only strings, or should_read_file should have a better")
    print("error message (not 'invalid format' for valid input).")