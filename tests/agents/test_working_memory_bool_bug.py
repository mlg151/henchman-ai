"""Test for bool bug in working_memory.py."""

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_should_read_file_with_bool_start():
    """Test should_read_file with start=True (bool).

    BUG: The method uses `type(start) is int` to reject bool.
    This works because `type(True) is bool`, not `int`.
    But `isinstance(True, int)` is True (bool is subclass of int).
    The comment says "Use type() not isinstance() to reject bool".
    This is actually correct!
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))

    # Test with start=True (bool)
    should_read, reason = memory.should_read_file("/test/file.py", start=True, end=10)

    # Should return error about invalid line number
    assert should_read is True
    assert "integer" in reason.lower() or "invalid" in reason.lower()
    assert "bool" in reason.lower()  # Error message should mention bool

    print(f"Test passes: start=True (bool) correctly rejected: {reason}")


def test_should_read_file_with_bool_end():
    """Test should_read_file with end=True (bool)."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))

    # Test with end=True (bool)
    should_read, reason = memory.should_read_file("/test/file.py", start=10, end=True)

    # Should return error about invalid line number
    assert should_read is True
    assert "integer" in reason.lower() or "invalid" in reason.lower()
    assert "bool" in reason.lower()

    print(f"Test passes: end=True (bool) correctly rejected: {reason}")


def test_should_read_file_with_bool_false():
    """Test should_read_file with start=False (bool)."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))

    # Test with start=False (bool) - False == 0, which is invalid anyway
    should_read, reason = memory.should_read_file("/test/file.py", start=False, end=10)

    # Should return error about invalid line number
    assert should_read is True
    # Either "bool" or "positive" error
    assert "bool" in reason.lower() or "positive" in reason.lower()

    print(f"Test passes: start=False (bool) correctly rejected: {reason}")


if __name__ == "__main__":
    test_should_read_file_with_bool_start()
    test_should_read_file_with_bool_end()
    test_should_read_file_with_bool_false()
    print("\nNo bug found - bool values are correctly rejected.")
