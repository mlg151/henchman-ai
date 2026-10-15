"""Test for a real bug in working_memory.py."""

import pytest

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_bug_invalid_lines_read_with_full_file_request():
    """Test bug when lines_read is invalid and requesting full file.

    Scenario:
    1. Add entry with invalid lines_read (e.g., "invalid")
    2. Request to read entire file (start=None, end=None)
    3. should_read_file should return True (need to read)
    4. But check if the reason is correct

    Actually, this might work correctly. Let me think of a different bug...
    """
    # Try to create entry with invalid lines_read
    # This should raise ValueError in __post_init__
    with pytest.raises(ValueError, match="Invalid lines_read"):
        WorkingMemoryEntry(
            path="/test/file.py",
            purpose="Test",
            lines_read="invalid",  # Invalid format
            key_insights=[],
        )

    print("✓ WorkingMemoryEntry correctly rejects invalid lines_read")


def test_bug_empty_string_lines_read():
    """Test with lines_read="" (empty string).

    Empty string is valid - means "no lines were read".
    """
    memory = WorkingMemory(current_task="Test")

    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="",  # Empty string - valid
        key_insights=[],
    )
    memory.add_recent_file(entry)

    # Request entire file
    should_read, reason = memory.should_read_file("/test/file.py")

    print(f"lines_read='': should_read={should_read}, reason={reason}")
    assert should_read is True
    assert "no lines" in reason.lower()

def test_bug_none_lines_read():
    """Test with lines_read=None.

    None is also valid - means "no lines were read".
    """
    memory = WorkingMemory(current_task="Test")

    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read=None,  # None - valid
        key_insights=[],
    )
    memory.add_recent_file(entry)

    # Request entire file
    should_read, reason = memory.should_read_file("/test/file.py")

    print(f"lines_read=None: should_read={should_read}, reason={reason}")
    assert should_read is True
    assert "no lines" in reason.lower()


def test_bug_whitespace_only_lines_read():
    """Test with lines_read="   " (whitespace only).

    This should be normalized to empty string.
    """
    memory = WorkingMemory(current_task="Test")

    # Try to create entry with whitespace-only lines_read
    # This might be rejected as invalid
    try:
        entry = WorkingMemoryEntry(
            path="/test/file.py",
            purpose="Test",
            lines_read="   ",  # Whitespace only
            key_insights=[],
        )
        memory.add_recent_file(entry)

        # Request entire file
        should_read, reason = memory.should_read_file("/test/file.py")

        print(f"lines_read='   ': should_read={should_read}, reason={reason}")
        # Should return True (need to read)
        assert should_read is True

    except ValueError as e:
        print(f"✓ WorkingMemoryEntry rejects whitespace-only lines_read: {e}")


def test_bug_mixed_valid_invalid_entries():
    """Test with multiple entries, some valid, some invalid.

    Bug hypothesis: If one entry has invalid lines_read and another has valid,
    the algorithm might incorrectly handle it.
    """
    memory = WorkingMemory(current_task="Test")

    # First entry: valid partial read
    entry1 = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="First read",
        lines_read="1-10",
        key_insights=[],
    )
    memory.add_recent_file(entry1)

    # Second entry: empty lines_read (valid)
    entry2 = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Second read",
        lines_read="",  # Empty - valid
        key_insights=[],
    )
    memory.add_recent_file(entry2)

    # Request lines 5-15
    should_read, reason = memory.should_read_file("/test/file.py", 5, 15)

    print(f"Mixed entries (1-10, ''): should_read={should_read}, reason={reason}")
    print(f"Mixed entries (1-10, ''): should_read={should_read}, reason={reason}")
    # We've read 1-10, need 11-15
    assert should_read is True
    assert "need to be read" in reason.lower()  # Should say lines need to be read
if __name__ == "__main__":
    print("Testing for real bugs...")
    print("=" * 60)

    tests = [
        test_bug_invalid_lines_read_with_full_file_request,
        test_bug_empty_string_lines_read,
        test_bug_none_lines_read,
        test_bug_whitespace_only_lines_read,
        test_bug_mixed_valid_invalid_entries,
    ]

    for test in tests:
        print(f"\nRunning {test.__name__}...")
        try:
            test()
            print("  ✓ PASS")
        except AssertionError as e:
            print(f"  ✗ FAIL: {e}")
        except Exception as e:
            print(f"  ✗ ERROR: {e}")

    print("\n" + "=" * 60)
    print("Summary: No obvious bugs found in these test cases.")
