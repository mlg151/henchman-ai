"""Test for WorkingMemoryEntry validation bug."""

from henchman.agents.working_memory import WorkingMemoryEntry


def test_working_memory_entry_validation_bug():
    """Test WorkingMemoryEntry bug: doesn't validate lines_read content.

    BUG: WorkingMemoryEntry only validates that lines_read is a string or None,
    but doesn't validate the content. Invalid lines_read like "0-10" (line 0)
    is accepted, causing errors later in should_read_file.

    Expected: WorkingMemoryEntry should raise ValueError for invalid lines_read.
    """
    # Test 1: Valid lines_read should work
    entry1 = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="1-10",
        key_insights=["Valid"]
    )
    assert entry1.lines_read == "1-10"

    # Test 2: Invalid lines_read "0-10" (line 0) - BUG: should raise ValueError but doesn't
    # Currently accepted, causes error later in should_read_file
    try:
        entry2 = WorkingMemoryEntry(
            path="/test/file.py",
            purpose="Test",
            lines_read="0-10",  # Invalid: line 0
            key_insights=["Invalid"]
        )
        print("BUG: WorkingMemoryEntry accepted invalid lines_read='0-10' (no error)")
        print(f"Entry created: {entry2}")

        # The bug is that this doesn't raise ValueError
        # We expect it to raise ValueError
        # So this test should fail (demonstrating the bug)
        raise AssertionError("WorkingMemoryEntry should have raised ValueError for lines_read='0-10'")

    except ValueError as e:
        print(f"GOOD: WorkingMemoryEntry raised ValueError for lines_read='0-10': {e}")
        # This is what should happen

    # Test 3: lines_read="full" should work
    entry3 = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="full",
        key_insights=["Full read"]
    )
    assert entry3.lines_read == "full"

    # Test 4: lines_read=None should work
    entry4 = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read=None,
        key_insights=["No lines read"]
    )
    assert entry4.lines_read is None

    # Test 5: lines_read="10-5" (start > end) - should be invalid
    try:
        WorkingMemoryEntry(
            path="/test/file.py",
            purpose="Test",
            lines_read="10-5",  # Invalid: start > end
            key_insights=["Invalid"]
        )
        print("BUG: WorkingMemoryEntry accepted invalid lines_read='10-5' (start > end)")
        raise AssertionError("WorkingMemoryEntry should have raised ValueError for lines_read='10-5'")
    except ValueError as e:
        print(f"GOOD: WorkingMemoryEntry raised ValueError for lines_read='10-5': {e}")

    print("\nTest demonstrates WorkingMemoryEntry validation bug")


if __name__ == "__main__":
    test_working_memory_entry_validation_bug()
