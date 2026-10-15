"""Test for type safety bug in WorkingMemoryEntry.

This test demonstrates that WorkingMemoryEntry accepts invalid types for
lines_read field, violating type hints and causing downstream issues.
"""

import pytest

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_working_memory_entry_lines_read_type_safety():
    """Test that WorkingMemoryEntry validates lines_read is a string.

    FIXED: WorkingMemoryEntry now validates lines_read is a string or None.
    """
    # Test 1: lines_read=None (should be allowed for deserialization)
    entry1 = WorkingMemoryEntry(
        path="/test/file1.py",
        purpose="Test",
        lines_read=None,  # Allowed for deserialization
        key_insights=[],
    )
    assert entry1.lines_read is None  # OK

    # Test 2: lines_read=123 (int, should raise TypeError)
    with pytest.raises(TypeError, match="lines_read must be a string or None"):
        WorkingMemoryEntry(
            path="/test/file2.py",
            purpose="Test",
            lines_read=123,  # Should raise TypeError
            key_insights=[],
        )

    # Test 3: lines_read=["10-20", "30-40"] (list, should raise TypeError)
    with pytest.raises(TypeError, match="lines_read must be a string or None"):
        WorkingMemoryEntry(
            path="/test/file3.py",
            purpose="Test",
            lines_read=["10-20", "30-40"],  # Should raise TypeError
            key_insights=[],
        )

    # Test 4: lines_read should be string (valid)
    entry4 = WorkingMemoryEntry(
        path="/test/file4.py",
        purpose="Test",
        lines_read="10-20",  # Correct
        key_insights=[],
    )
    assert entry4.lines_read == "10-20"  # OK

    print("FIXED: WorkingMemoryEntry now validates lines_read type")
    print("  lines_read=None: allowed (for deserialization)")
    print("  lines_read=123: raises TypeError")
    print("  lines_read=list: raises TypeError")
    print("  lines_read=str: accepted (correct)")


def test_should_read_file_with_invalid_lines_read_type():
    """Test should_read_file behavior - now invalid entries can't be created."""
    memory = WorkingMemory(current_task="Test")

    # With the fix, we can't create entries with invalid lines_read
    # So this test is no longer relevant for the bug
    # But we can test that valid entries work correctly

    # Add valid entry
    entry = WorkingMemoryEntry("/test/file.py", "Test", "10-20", [])
    memory.add_recent_file(entry)

    result = memory.should_read_file("/test/file.py", 10, 20)
    print(f"Valid entry with lines_read='10-20': {result}")
    # Should return (False, "File already read (covered)")

    # Test with empty string (valid string, but might be treated as invalid format)
    entry2 = WorkingMemoryEntry("/test/file2.py", "Test", "", [])
    memory.add_recent_file(entry2)

    result2 = memory.should_read_file("/test/file2.py", 10, 20)
    print(f"Empty string lines_read='': {result2}")
    # _parse_line_ranges("") returns [] (empty string)
    # should_read_file returns (True, "Cannot determine - invalid lines_read format")


if __name__ == "__main__":
    test_working_memory_entry_lines_read_type_safety()
    test_should_read_file_with_invalid_lines_read_type()
    print("\n" + "="*60)
    print("BUG: WorkingMemoryEntry doesn't enforce type hints")
    print("FIX: Add __post_init__ validation to WorkingMemoryEntry")
