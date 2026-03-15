"""Test for the error message bug in working_memory.py.

This test demonstrates the bug where should_read_file returns
"File already read (covered by multiple entries)" even when
the range is covered by a single entry.
"""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_error_message_single_entry():
    """Test that error message is correct when range covered by single entry.
    
    BUG: Currently returns "File already read (covered by multiple entries)"
    even when covered by a single entry.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Add SINGLE entry
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="10-50"
    ))
    
    # Request lines 20-40 (fully within single entry's range)
    should_read, reason = memory.should_read_file("/test/file.py", 20, 40)
    
    # Should return False (already read)
    assert should_read is False, f"Should return False, got {should_read}"
    
    # BUG: Reason says "covered by multiple entries" but it's only ONE entry
    # Should say something like "File already read (covered)" or "File already read"
    assert "already read" in reason.lower()
    
    # This is the bug: message says "multiple entries" when it's a single entry
    # The test EXPECTS this to fail with current implementation
    if "multiple entries" in reason:
        print(f"BUG CONFIRMED: Reason says '{reason}' but range is covered by SINGLE entry")
        # This assertion will FAIL with current code, proving the bug
        # We expect it to fail - that's TDD!
        assert "multiple entries" not in reason, (
            f"Error message should not say 'multiple entries' when covered by single entry. "
            f"Got: '{reason}'"
        )
    else:
        print(f"BUG FIXED: Reason correctly says '{reason}' for single entry coverage")


def test_error_message_multiple_entries():
    """Test that error message is correct when range covered by multiple entries."""
    memory = WorkingMemory(current_task="Test")
    
    # Add MULTIPLE entries that together cover the range
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="First read",
        lines_read="10-30"
    ))
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Second read",
        lines_read="31-50"
    ))
    
    # Request lines 10-50 (covered by TWO entries together)
    should_read, reason = memory.should_read_file("/test/file.py", 10, 50)
    
    # Should return False (already read)
    assert should_read is False, f"Should return False, got {should_read}"
    
    # Should say "already read (covered)" (simplified message)
    assert "already read" in reason.lower()
    assert "covered" in reason.lower(), (
        f"Error message should indicate coverage. Got: '{reason}'"
    )


def test_error_message_full_read():
    """Test error message for full read."""
    memory = WorkingMemory(current_task="Test")
    
    # Add full read
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="full"
    ))
    
    # Request any lines
    should_read, reason = memory.should_read_file("/test/file.py", 10, 50)
    
    # Should return False (already read)
    assert should_read is False, f"Should return False, got {should_read}"
    
    # Should say "File already read (full)"
    assert "already read" in reason.lower()
    assert "full" in reason.lower(), (
        f"Error message should mention 'full' for full read. Got: '{reason}'"
    )


if __name__ == "__main__":
    print("Running error message bug tests...")
    print("=" * 60)
    
    # Run the test that should fail with current implementation
    try:
        test_error_message_single_entry()
        print("\n✓ test_error_message_single_entry PASSED (bug might be fixed?)")
    except AssertionError as e:
        print(f"\n✗ test_error_message_single_entry FAILED as expected: {e}")
        print("This confirms the bug exists!")
    
    print("\n" + "=" * 60)
    print("Running other tests...")
    
    tests = [
        test_error_message_multiple_entries,
        test_error_message_full_read,
    ]
    
    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__} PASSED")
        except AssertionError as e:
            print(f"✗ {test.__name__} FAILED: {e}")
        except Exception as e:
            print(f"✗ {test.__name__} ERROR: {e}")