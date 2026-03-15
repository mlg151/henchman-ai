"""Test for the Four Lenses bug in working_memory.py."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_memory_should_read_file_older_full_read_ignored():
    """Test that should_read_file ignores older full reads.
    
    BUG: When a file was read fully in an older entry, but partially read
    more recently, should_read_file only checks the most recent (partial) read
    and ignores the older full read.
    
    This causes unnecessary re-reading of lines that were previously read in full.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Add older full read
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Full read (older)",
        lines_read="full",
        key_insights=["Full file read"]
    ))
    
    # Add more recent partial read
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py", 
        purpose="Partial read (newer)",
        lines_read="10-50",
        key_insights=["Only read middle section"]
    ))
    
    # Request lines 60-100 (were in older full read, not in recent partial read)
    should_read, reason = memory.should_read_file("/test/file.py", 60, 100)
    
    # BUG: Returns True (should read) even though lines 60-100 were read in the full read
    # Should return False (already read) because file was fully read in older entry
    assert should_read is False, (
        f"Lines 60-100 were read in older full read. "
        f"Should return False (already read). Got: {should_read}, reason: {reason}"
    )
    assert "already read" in reason.lower()


def test_memory_should_read_file_multiple_partials_cover_range():
    """Test that should_read_file doesn't merge ranges from multiple entries.
    
    BUG: When multiple partial reads collectively cover a requested range,
    should_read_file doesn't recognize this and returns True (should read).
    """
    memory = WorkingMemory(current_task="Test")
    
    # Add two partial reads that together cover lines 1-100
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="First half",
        lines_read="1-50"
    ))
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Second half", 
        lines_read="51-100"
    ))
    
    # Request lines 1-100 (covered by both entries together)
    should_read, reason = memory.should_read_file("/test/file.py", 1, 100)
    
    # BUG: Returns True (should read) even though entries 1-50 and 51-100 cover 1-100
    # Should return False (already read)
    assert should_read is False, (
        f"Lines 1-100 should be already read (covered by entries 1-50 and 51-100). "
        f"Got: {should_read}, reason: {reason}"
    )
    assert "already read" in reason.lower()


def test_memory_should_read_file_full_anywhere_in_history():
    """Test that should_read_file should check ALL entries for 'full', not just most recent.
    
    BUG: Only checks most recent entry for 'full'. If ANY entry has 'full',
    the file should be considered fully read.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Add partial read (most recent)
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Partial read",
        lines_read="10-50"
    ))
    
    # Add older full read (not most recent)
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Full read (older)",
        lines_read="full"
    ))
    
    # Request lines 60-100 (were in older full read)
    should_read, reason = memory.should_read_file("/test/file.py", 60, 100)
    
    # BUG: Returns True (should read) even though file was fully read in older entry
    # Should return False (already read)
    assert should_read is False, (
        f"File was fully read in older entry. "
        f"Should return False (already read). Got: {should_read}, reason: {reason}"
    )
    assert "already read" in reason.lower()


def test_memory_should_read_file_case_insensitive_full():
    """Test that should_read_file should handle case-insensitive 'full'.
    
    BUG: Only checks for lowercase 'full', not 'FULL', 'Full', etc.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Add entry with uppercase FULL
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="FULL"
    ))
    
    # Request any lines
    should_read, reason = memory.should_read_file("/test/file.py", 10, 50)
    
    # BUG: Returns True (should read) because "FULL" != "full"
    # Should return False (already read)
    assert should_read is False, (
        f"File marked as 'FULL' should be considered fully read. "
        f"Got: {should_read}, reason: {reason}"
    )
    assert "already read" in reason.lower()


if __name__ == "__main__":
    # Run tests to demonstrate bugs
    import sys
    
    print("Running Four Lenses bug tests...")
    print("=" * 60)
    
    tests = [
        test_memory_should_read_file_older_full_read_ignored,
        test_memory_should_read_file_multiple_partials_cover_range,
        test_memory_should_read_file_full_anywhere_in_history,
        test_memory_should_read_file_case_insensitive_full,
    ]
    
    failures = 0
    for test in tests:
        print(f"\nRunning {test.__name__}...")
        try:
            test()
            print("  ✓ PASS")
        except AssertionError as e:
            print(f"  ✗ FAIL: {e}")
            failures += 1
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            failures += 1
    
    print(f"\n" + "=" * 60)
    print(f"Total: {len(tests)} tests, {failures} failures")
    sys.exit(1 if failures > 0 else 0)