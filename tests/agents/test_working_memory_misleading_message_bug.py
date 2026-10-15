"""Test for misleading error message bug in working_memory.py."""

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_memory_should_read_file_misleading_message_bug():
    """Test should_read_file returns misleading error message.

    BUG: When start=None, end=None (read entire file) and valid_ranges is not empty,
    the method returns True with reason "File not fully read - partial read recorded".
    This message is incorrect because:
    1. We don't know if file was "not fully read" (we don't know file size)
    2. "partial read recorded" implies we know it was partial, but we only know
       some lines were read, not whether all lines were read.

    The message should be more accurate, e.g., "Cannot determine if file fully read"
    or "File may not be fully read - cannot verify without file size".
    """
    memory = WorkingMemory(current_task="Test")

    # Record that we read some lines (could be all lines, we don't know)
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-50"))

    # Try to read entire file (start=None, end=None)
    should_read, reason = memory.should_read_file("/test/file.py")

    print("File read: 1-50 (some lines)")
    print("Request: read entire file (start=None, end=None)")
    print(f"Result: should_read={should_read}, reason={reason}")

    # Should return True (conservative: read if unsure)
    assert should_read is True, (
        f"Should return True when unsure if file was fully read. "
        f"Got: {should_read}"
    )

    # BUG: The reason is misleading!
    # Current: "File not fully read - partial read recorded"
    # Problem: We don't know if file was "not fully read"!
    # We only know some lines were read.
    # The message should reflect uncertainty.

    # Check that reason doesn't contain incorrect assumptions
    # (This test will FAIL with current code, demonstrating the bug)
    incorrect_phrases = [
        "not fully read",  # Assumes we know it wasn't fully read
        "partial read",    # Assumes we know it was partial (not full)
    ]

    for phrase in incorrect_phrases:
        assert phrase not in reason.lower(), (
            f"Error message contains incorrect assumption '{phrase}'. "
            f"Message: '{reason}'. "
            f"We don't know if file was fully read or partial (no file size)."
        )

    # The message should indicate uncertainty
    acceptable_phrases = [
        "partially read",
        "whole file not read",
        "cannot determine",
        "may not be",
        "uncertain",
        "cannot verify",
        "without file size",
        "unknown",
    ]

    # At least one acceptable phrase should be in the message
    has_acceptable_phrase = any(phrase in reason.lower() for phrase in acceptable_phrases)
    assert has_acceptable_phrase, (
        f"Error message should indicate file was partially read. "
        f"Message: '{reason}'. "
        f"Expected phrases like: {acceptable_phrases}"
    )


def test_memory_should_read_file_empty_no_ranges():
    """Test should_read_file when no lines recorded."""
    memory = WorkingMemory(current_task="Test")

    # No lines recorded for this file (file not in recent_files at all)
    should_read, reason = memory.should_read_file("/test/file.py")

    print("File: no lines recorded")
    print("Request: read entire file")
    print(f"Result: should_read={should_read}, reason={reason}")

    # Should return True (file not read at all)
    assert should_read is True
    # When file is not in recent_files at all, returns "File not in recent files"
    assert "not in recent" in reason.lower() or "no lines" in reason.lower() or "not read" in reason.lower()


def test_memory_should_read_file_marked_full():
    """Test should_read_file when file marked as 'full'."""
    memory = WorkingMemory(current_task="Test")

    # File marked as fully read
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))

    should_read, reason = memory.should_read_file("/test/file.py")

    print("File: marked as 'full'")
    print("Request: read entire file")
    print(f"Result: should_read={should_read}, reason={reason}")

    # Should return False (file already read fully)
    assert should_read is False
    assert "already read" in reason.lower() or "full" in reason.lower()


if __name__ == "__main__":
    print("Testing misleading error message bug...")
    print("=" * 60)

    tests = [
        test_memory_should_read_file_misleading_message_bug,
        test_memory_should_read_file_empty_no_ranges,
        test_memory_should_read_file_marked_full,
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
    print("Tests complete.")
