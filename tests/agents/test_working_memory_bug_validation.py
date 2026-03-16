"""Test for validation bug in working_memory.py."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_working_memory_entry_accepts_invalid_lines_read():
    """Test that WorkingMemoryEntry accepts invalid lines_read values.
    
    BUG: WorkingMemoryEntry has type hint `lines_read: str` but accepts `None`
    without validation. This violates type safety and causes downstream issues.
    """
    # This should fail but doesn't
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read=None,  # Violates type hint str
        key_insights=[],
    )
    
    # The entry is created without error
    assert entry is not None
    assert entry.lines_read is None  # BUG: Should be string
    
    # This causes issues downstream
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(entry)
    
    # should_read_file will have issues with lines_read=None
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)
    
    # lines_read=None is valid (means "no lines read"), same as lines_read=""
    # Should return True with reason indicating no lines have been read
    assert should_read is True
    assert "no lines have been read" in reason.lower()
    
    print(f"BUG: WorkingMemoryEntry accepts lines_read=None (violates type hint str)")
    print(f"  should_read_file returns: should_read={should_read}, reason={reason}")


def test_working_memory_entry_accepts_empty_string():
    """Test that WorkingMemoryEntry accepts empty string for lines_read.
    
    Empty string might be valid (means no lines read) or invalid.
    Current behavior: treated as invalid in should_read_file.
    """
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="",  # Empty string
        key_insights=[],
    )
    
    assert entry.lines_read == ""
    
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(entry)
    
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)
    
    # Empty string is valid "no lines read" (not invalid)
    assert should_read is True
    assert "no lines" in reason.lower() or "not read" in reason.lower()
    
    print(f"Empty lines_read='' is valid 'no lines read': {reason}")


if __name__ == "__main__":
    test_working_memory_entry_accepts_invalid_lines_read()
    test_working_memory_entry_accepts_empty_string()
    print("\nBUG: WorkingMemoryEntry doesn't validate fields (type safety violation)")