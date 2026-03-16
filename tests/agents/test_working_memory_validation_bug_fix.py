"""Test for the validation bug fix in WorkingMemoryEntry._validate_lines_read."""

import pytest
from henchman.agents.working_memory import WorkingMemoryEntry


def test_validate_lines_read_with_full_and_invalid_parts():
    """Test that _validate_lines_read validates ALL parts even when 'full' is present.
    
    BUG: Previously, when 'full' appears in a comma-separated list, _validate_lines_read
    returned early without validating other parts. This allowed invalid formats like
    'full,invalid-format' to pass validation.
    
    FIX: _validate_lines_read now validates ALL parts and rejects strings containing
    invalid content, even when 'full' is present.
    """
    # Test 1: 'full,invalid-format' should be REJECTED (has invalid content)
    with pytest.raises(ValueError, match="Invalid lines_read"):
        WorkingMemoryEntry._validate_lines_read("full,invalid-format")
    
    # Test 2: 'invalid-format,full' should be REJECTED (has invalid content)
    with pytest.raises(ValueError, match="Invalid lines_read"):
        WorkingMemoryEntry._validate_lines_read("invalid-format,full")
    
    # Test 3: 'full,10-20' should pass (10-20 is valid)
    WorkingMemoryEntry._validate_lines_read("full,10-20")
    
    # Test 4: '10-20,full' should pass (10-20 is valid)
    WorkingMemoryEntry._validate_lines_read("10-20,full")
    
    # Test 5: 'full' alone should pass
    WorkingMemoryEntry._validate_lines_read("full")
    
    # Test 6: 'full, ,10-20' (with empty part) should pass (empty parts are skipped)
    WorkingMemoryEntry._validate_lines_read("full, ,10-20")
    
    # Test 7: 'full,invalid-format,10-20' should be REJECTED (has invalid content)
    with pytest.raises(ValueError, match="Invalid lines_read"):
        WorkingMemoryEntry._validate_lines_read("full,invalid-format,10-20")


def test_working_memory_entry_creation_with_invalid_lines_read():
    """Test that WorkingMemoryEntry creation raises ValueError for invalid lines_read."""
    # Test 1: 'full,invalid-format' should be REJECTED (has invalid content)
    with pytest.raises(ValueError, match="Invalid lines_read"):
        WorkingMemoryEntry(
            path="/test/file.py",
            purpose="Test",
            lines_read="full,invalid-format",
            key_insights=[]
        )
    
    # Test 2: 'invalid-format,full' should be REJECTED (has invalid content)
    with pytest.raises(ValueError, match="Invalid lines_read"):
        WorkingMemoryEntry(
            path="/test/file.py",
            purpose="Test",
            lines_read="invalid-format,full",
            key_insights=[]
        )
    
    # Test 3: Valid formats should work
    entry1 = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="full,10-20",
        key_insights=[]
    )
    assert entry1.lines_read == "full,10-20"
    
    entry2 = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="10-20,full",
        key_insights=[]
    )
    assert entry2.lines_read == "10-20,full"
    
    entry3 = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="full",
        key_insights=[]
    )
    assert entry3.lines_read == "full"


def test_parse_line_ranges_behavior_with_full():
    """Test that _parse_line_ranges returns empty list when 'full' is present.
    
    This tests the existing behavior that should remain unchanged.
    """
    from henchman.agents.working_memory import WorkingMemory
    
    memory = WorkingMemory(current_task="Test")
    
    # 'full' returns empty list
    assert memory._parse_line_ranges("full") == []
    # 'full,10-20' returns empty list (10-20 ignored)
    assert memory._parse_line_ranges("full,10-20") == []
    # '10-20,full' returns empty list (10-20 ignored)
    assert memory._parse_line_ranges("10-20,full") == []
    # '10-20' returns LineRange(10, 20)
    ranges = memory._parse_line_ranges("10-20")
    assert len(ranges) == 1
    assert ranges[0].start == 10
    assert ranges[0].end == 20


if __name__ == "__main__":
    # Run tests to demonstrate the bug
    import sys
    
    print("Running Validation Bug Fix tests...")
    print("=" * 60)
    
    tests = [
        test_validate_lines_read_with_full_and_invalid_parts,
        test_working_memory_entry_creation_with_invalid_lines_read,
        test_parse_line_ranges_behavior_with_full,
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
            print(f"  ✗ ERROR: {type(e).__name__}: {e}")
            failures += 1
    
    print(f"\n" + "=" * 60)
    print(f"Total: {len(tests)} tests, {failures} failures")
    
    if failures > 0:
        print("\nBUG CONFIRMED: Tests fail with current implementation.")
        print("The bug is: _validate_lines_read doesn't validate all parts when 'full' is present.")
    else:
        print("\nAll tests pass (bug may have been fixed).")
    
    sys.exit(1 if failures > 0 else 0)