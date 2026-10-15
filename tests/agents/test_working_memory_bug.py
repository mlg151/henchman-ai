"""Test for a bug in working_memory.py."""

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_memory_should_read_file_empty_lines_read():
    """Test should_read_file when lines_read is empty string.

    BUG: _parse_line_ranges("") returns [], which means valid_ranges is empty.
    When valid_ranges is empty, the method returns "Cannot determine - invalid lines_read format".
    But actually, empty lines_read means no lines were read, so we should read the file.
    """
    memory = WorkingMemory(current_task="Test")

    # Add entry with empty lines_read
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="",  # Empty string
        key_insights=[],
    )
    memory.add_recent_file(entry)

    # Request lines 10-20
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)

    # Should return True (need to read)
    # Empty lines_read means "no lines were read", which is valid
    # After fix: returns "No lines have been read" instead of "invalid lines_read format"

    print(f"should_read: {should_read}, reason: {reason}")
    assert should_read is True
    # Empty lines_read is valid "no lines read", not invalid
    assert "no lines" in reason.lower() or "not read" in reason.lower()

    print("Test passes (no bug)")

if __name__ == "__main__":
    test_memory_should_read_file_empty_lines_read()
