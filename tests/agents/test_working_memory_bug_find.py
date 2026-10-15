"""Test to find a bug in working_memory.py."""

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_memory_should_read_file_start_equals_end():
    """Test when start == end (single line request).

    BUG POTENTIAL: What if we request a single line (start=10, end=10)
    and that line has been read?
    """
    memory = WorkingMemory(current_task="Test")

    # File read lines 5-15
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "5-15"))

    # Request single line 10 (within 5-15)
    should_read, reason = memory.should_read_file("/test/file.py", 10, 10)

    print(f"Read: 5-15, Request: 10-10, Result: {should_read}, {reason}")

    # Line 10 is within 5-15, so should return False
    assert should_read is False, f"Line 10 is within 5-15. Got: {should_read}"
    assert "already read" in reason.lower() or "covered" in reason.lower()

    # Request single line 20 (not in 5-15)
    should_read2, reason2 = memory.should_read_file("/test/file.py", 20, 20)
    print(f"Read: 5-15, Request: 20-20, Result: {should_read2}, {reason2}")
    assert should_read2 is True, f"Line 20 is not in 5-15. Got: {should_read2}"


def test_memory_should_read_file_start_gt_end_validation():
    """Test validation when start > end.

    BUG: The validation at line 525 checks `if start is not None and end is not None and start > end:`.
    But what if start=10, end=5? That's invalid.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-100"))

    # Invalid: start > end
    should_read, reason = memory.should_read_file("/test/file.py", 10, 5)

    print(f"Invalid: start=10 > end=5, Result: {should_read}, {reason}")

    assert should_read is True, f"Invalid range start=10 > end=5 should return True. Got: {should_read}"
    assert "invalid" in reason.lower() or "start.*>.*end" in reason.lower()


def test_memory_should_read_file_float_validation():
    """Test float validation.

    BUG: What about start=1.5 (float)? Should be rejected.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-100"))

    # Float start
    should_read, reason = memory.should_read_file("/test/file.py", 1.5, 10)

    print(f"Float start=1.5, Result: {should_read}, {reason}")

    assert should_read is True, f"Float start=1.5 should be rejected. Got: {should_read}"
    assert "invalid" in reason.lower() or "integer" in reason.lower() or "type" in reason.lower()

    # Float end (not -1.0)
    should_read2, reason2 = memory.should_read_file("/test/file.py", 1, 10.5)

    print(f"Float end=10.5, Result: {should_read2}, {reason2}")

    assert should_read2 is True, f"Float end=10.5 should be rejected. Got: {should_read2}"
    assert "invalid" in reason.lower() or "integer" in reason.lower() or "type" in reason.lower()


def test_memory_should_read_file_string_validation():
    """Test string validation (should fail).

    BUG: What if someone passes a string? type("10") is not int.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-100"))

    # String start (should fail)
    should_read, reason = memory.should_read_file("/test/file.py", "10", 20)  # type: ignore

    print(f"String start='10', Result: {should_read}, {reason}")

    assert should_read is True, f"String start='10' should be rejected. Got: {should_read}"
    assert "invalid" in reason.lower() or "integer" in reason.lower() or "type" in reason.lower()


def test_memory_should_read_file_none_start_valid_end():
    """Test when start=None, end=valid.

    BUG POTENTIAL: The validation at line 510 checks `if end is not None:`.
    If end=10, it validates. Good.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "20-30"))

    # start=None, end=10 (read lines 1-10)
    should_read, reason = memory.should_read_file("/test/file.py", end=10)

    print(f"Read: 20-30, Request: 1-10 (end=10), Result: {should_read}, {reason}")

    # We've read 20-30, but need 1-10 (before what we read)
    assert should_read is True, f"Need lines 1-10. Got: {should_read}"
    assert "before" in reason.lower() or "gap" in reason.lower() or "need to read" in reason.lower()


if __name__ == "__main__":
    print("Running bug find tests...")
    print("=" * 60)

    tests = [
        test_memory_should_read_file_start_equals_end,
        test_memory_should_read_file_start_gt_end_validation,
        test_memory_should_read_file_float_validation,
        test_memory_should_read_file_string_validation,
        test_memory_should_read_file_none_start_valid_end,
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
