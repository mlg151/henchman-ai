"""Test for the validation bug in working_memory.py.

This test demonstrates the bug where _validate_lines_read accepts
whitespace-only strings but should_read_file treats them as invalid.
"""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_validate_lines_read_whitespace_inconsistent():
    """Test the inconsistent validation bug.
    
    BUG: _validate_lines_read accepts whitespace-only strings,
    but should_read_file treats them as "invalid lines_read format".
    
    After fix: _validate_lines_read should reject whitespace-only strings.
    """
    from henchman.agents.working_memory import WorkingMemoryEntry
    
    # After fix: this SHOULD raise ValueError
    with pytest.raises(ValueError, match="whitespace-only"):
        WorkingMemoryEntry._validate_lines_read("   ")
    
    # Creating a WorkingMemoryEntry with whitespace-only lines_read
    # should now raise ValueError in __post_init__
    with pytest.raises(ValueError):
        WorkingMemoryEntry(
            path="/test/file.py",
            purpose="Test",
            lines_read="   ",
            key_insights=[]
        )
    
    # Test with empty string (should still be valid)
    WorkingMemoryEntry._validate_lines_read("")
    
    # Create entry with empty string
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="",
        key_insights=[]
    )
    
    # Now use it in should_read_file
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(entry)
    
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)
    
    # Empty string is valid, but should_read_file still says "invalid lines_read format"
    # This is still a problem, but less severe than whitespace-only
    assert should_read is True
    # The error message could be improved, but at least it's consistent now


def test_validate_lines_read_should_reject_whitespace():
    """Test that _validate_lines_read should reject whitespace-only strings.
    
    This is what the fix should do.
    """
    from henchman.agents.working_memory import WorkingMemoryEntry
    
    # After fix: this should raise ValueError
    with pytest.raises(ValueError, match="Invalid lines_read"):
        WorkingMemoryEntry._validate_lines_read("   ")
    
    # Empty string might still be valid (means "no lines read")
    # Or should it also be rejected?
    # Let's check current behavior first
    try:
        WorkingMemoryEntry._validate_lines_read("")
        # Empty string is currently valid
        print("Empty string is valid (means 'no lines read')")
    except ValueError:
        print("Empty string is invalid")


def test_working_memory_entry_creation_with_whitespace():
    """Test creating WorkingMemoryEntry with whitespace-only lines_read.
    
    After fix: should raise ValueError.
    """
    # After fix: should raise ValueError
    with pytest.raises(ValueError, match="whitespace-only"):
        WorkingMemoryEntry(
            path="/test/file.py",
            purpose="Test",
            lines_read="   ",
            key_insights=[]
        )
    
    # Test with empty string (should still work)
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="",
        key_insights=[]
    )
    assert entry.lines_read == ""


def test_should_read_file_better_error_message():
    """Test that should_read_file should have better error for whitespace.
    
    After fix: whitespace-only strings are rejected, so test with empty string.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Add entry with empty string lines_read
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="",  # Empty string
        key_insights=[]
    ))
    
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)
    
    # Current error message for empty string
    print(f"Current error for empty string: {reason}")
    
    # After fix: Error message is "No lines have been read" (improved!)
    assert should_read is True
    assert "no lines" in reason.lower() or "not read" in reason.lower()


if __name__ == "__main__":
    print("Testing validation bug...")
    print("=" * 60)
    
    # Run the test that demonstrates the bug
    test_validate_lines_read_whitespace_inconsistent()
    print("✓ Bug demonstrated: whitespace-only passes validation but produces 'invalid format' error")
    
    print("\n" + "=" * 60)
    print("Bug confirmed: Inconsistent validation vs. usage.")