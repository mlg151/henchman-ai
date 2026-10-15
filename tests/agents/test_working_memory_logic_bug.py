"""Test for logic bug in should_read_file method."""

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_should_read_file_end_minus_one_bug():
    """Test the logic bug with end=-1.

    Bug: After converting end=-1 to None, the code checks end != -1
    which is None != -1 (always True). This is logically wrong.
    """
    memory = WorkingMemory(current_task="Test")

    # Add a file read entry
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-50"))

    # Test with end=-1 (read to EOF)
    # This should not raise any errors
    should_read, reason = memory.should_read_file("/test/file.py", start=10, end=-1)

    print(f"Test with end=-1: should_read={should_read}, reason={reason}")

    # The bug is in the logic, not in the output
    # We need to verify the logic path doesn't have the redundant check
    # Actually test passes because end=None after conversion,
    # so end is not None is False, short-circuiting the condition

    # But we can assert the behavior is correct
    assert should_read is True  # Lines 10-EOF, we've only read 1-50, need 51-EOF
    assert "may need to read lines beyond" in reason.lower() or "beyond" in reason.lower()


def test_should_read_file_invalid_range_with_end_none():
    """Test that invalid range check works correctly after end conversion.

    When end is converted from -1 to None, we shouldn't check start > end
    because end is None.
    """
    memory = WorkingMemory(current_task="Test")

    # Test case that would fail if the bug caused issues
    # With start=10, end=-1 (converted to None)
    # The condition on line 562: if start is not None and end is not None and end != -1 and start > end:
    # After conversion: if 10 is not None and None is not None and None != -1 and 10 > None:
    # This is False because None is not None is False, short-circuiting
    # So no TypeError from comparing int > None

    should_read, reason = memory.should_read_file("/test/file.py", start=10, end=-1)

    # Should return True (need to read) not crash
    assert should_read is True


def test_should_read_file_code_analysis():
    """Analyze the buggy code path."""
    print("\nAnalyzing the bug:")
    print("Line 556: if end == -1: end = None")
    print("Line 562: if start is not None and end is not None and end != -1 and start > end:")
    print("\nIf end was -1 and is now None:")
    print("  - end is not None: False")
    print("  - end != -1: None != -1 = True (but doesn't matter due to short-circuit)")
    print("  - start > end: Not evaluated (short-circuited)")
    print("\nThe bug: Checking end != -1 after converting end from -1 to None is logically wrong.")
    print("It should just be: if start is not None and end is not None and start > end:")


if __name__ == "__main__":
    print("Testing logic bug in should_read_file...")
    print("=" * 60)

    test_should_read_file_end_minus_one_bug()
    print("✓ Test 1 passed")

    test_should_read_file_invalid_range_with_end_none()
    print("✓ Test 2 passed")

    test_should_read_file_code_analysis()

    print("\n" + "=" * 60)
    print("Bug confirmed: Redundant end != -1 check after end conversion")
