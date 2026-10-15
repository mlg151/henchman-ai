"""Test for end=-1 validation bug in should_read_file."""


from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_should_read_file_end_minus_one_with_invalid_start_bug():
    """Test should_read_file bug: end=-1 with invalid start=0.

    BUG: When start=0 (invalid) and end=-1 (valid special case for "read to EOF"),
    the method converts end=-1 to None before validating that start=0 is invalid.
    This causes confusing behavior where the invalid start validation might not
    trigger properly or might give misleading error messages.

    Expected: Should immediately return error about invalid start=0.
    Actual: Converts end=-1 to None first, then may give different error.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))

    # Test case: start=0 (invalid), end=-1 (valid special case)
    should_read, reason = memory.should_read_file("/test/file.py", 0, -1)

    # Should return True (should read) with error about invalid start
    assert should_read is True, (
        f"Invalid start=0 should return True with error. Got: {should_read}, reason: {reason}"
    )

    # The error should be about invalid start line number
    # Current bug: might say "File already read (full)" or give confusing message
    assert "invalid" in reason.lower() or "positive" in reason.lower() or "must be positive" in reason.lower(), (
        f"Should report invalid line number error for start=0. Got: {reason}"
    )

    # Should NOT say "already read" when line numbers are invalid
    assert "already read" not in reason.lower(), (
        f"Should NOT say 'already read' when start=0 is invalid. Got: {reason}"
    )


def test_should_read_file_end_minus_one_with_start_greater_than_end_bug():
    """Test should_read_file bug: end=-1 with start > hypothetical end.

    When end=-1 (means "read to EOF"), the validation for start > end
    should not apply because we don't know the end line number.
    But if start is invalid (e.g., start=0), that should be caught first.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))

    # Test with valid start but end=-1
    should_read, reason = memory.should_read_file("/test/file.py", 10, -1)

    # This should be valid: start=10, end=-1 means "read from line 10 to EOF"
    # File was read fully, so should return False
    assert should_read is False, (
        f"File read fully, start=10, end=-1 should return False. Got: {should_read}, reason: {reason}"
    )
    assert "already read" in reason.lower()


def test_should_read_file_validation_order_bug():
    """Test validation order bug in should_read_file.

    The validation order should be:
    1. Validate start (if provided) - reject non-int, < 1
    2. Validate end (if provided) - reject non-int, < 1 except -1
    3. Only after both validations pass, handle end=-1 → None
    4. Validate start > end (if both not None)

    Current bug: end=-1 → None happens before checking if start is invalid.
    """
    memory = WorkingMemory(current_task="Test")

    # Test 1: start=0.5 (float) should be rejected
    should_read, reason = memory.should_read_file("/test/file.py", 0.5, 10)
    assert should_read is True
    assert "invalid" in reason.lower() or "must be an integer" in reason.lower()

    # Test 2: start=True (bool) should be rejected
    should_read, reason = memory.should_read_file("/test/file.py", True, 10)
    assert should_read is True
    assert "invalid" in reason.lower() or "must be an integer" in reason.lower()

    # Test 3: end=0.5 (float) should be rejected
    should_read, reason = memory.should_read_file("/test/file.py", 1, 0.5)
    assert should_read is True
    assert "invalid" in reason.lower() or "must be an integer" in reason.lower()

    # Test 4: end=-1.0 (float -1.0) should be rejected (only integer -1 allowed)
    should_read, reason = memory.should_read_file("/test/file.py", 1, -1.0)
    assert should_read is True
    assert "invalid" in reason.lower() or "must be an integer" in reason.lower()
