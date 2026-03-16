"""Test for a real bug in working_memory.py."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

def test_memory_should_read_file_with_whitespace_only_lines_read():
    """Test should_read_file when lines_read contains only whitespace.
    
    After fix: whitespace-only strings should raise ValueError when creating WorkingMemoryEntry.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Creating entry with whitespace-only lines_read should raise ValueError
    with pytest.raises(ValueError, match="whitespace-only"):
        WorkingMemoryEntry(
            path="/test/file.py",
            purpose="Test",
            lines_read="   ",  # Only spaces
            key_insights=[],
        )
    
    # Test with empty string (should still work)
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="",  # Empty string
        key_insights=[],
    )
    memory.add_recent_file(entry)
    
    # Request lines 10-20
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)
    
    # Should return True (invalid lines_read format for empty string)
    assert should_read is True
    assert "invalid lines_read format" in reason or "Cannot determine" in reason
    
    print(f"Test passes: should_read={should_read}, reason={reason}")

def test_memory_parse_line_ranges_whitespace_only():
    """Test _parse_line_ranges with whitespace-only input."""
    from henchman.agents.working_memory import WorkingMemory
    
    memory = WorkingMemory(current_task="Test")
    
    # Test with only spaces
    ranges = memory._parse_line_ranges("   ")
    assert ranges == []
    
    # Test with only tabs
    ranges = memory._parse_line_ranges("\t\t")
    assert ranges == []
    
    # Test with only newlines
    ranges = memory._parse_line_ranges("\n\n")
    assert ranges == []
    
    # Test with mixed whitespace
    ranges = memory._parse_line_ranges(" \t\n ")
    assert ranges == []
    
    print("All whitespace-only tests pass")

if __name__ == "__main__":
    test_memory_should_read_file_with_whitespace_only_lines_read()
    test_memory_parse_line_ranges_whitespace_only()
    print("\nAll tests pass (no bug found)")