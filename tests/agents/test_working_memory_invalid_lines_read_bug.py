"""Test for invalid lines_read bug in should_read_file."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_memory_should_read_file_invalid_lines_read_bug():
    """Test should_read_file bug: invalid lines_read silently ignored.
    
    BUG: When lines_read contains invalid line numbers (e.g., "0-10" with line 0),
    _parse_line_ranges raises ValueError, which is caught in should_read_file,
    and the entry is skipped (continue). This means the file is treated as NOT read,
    even though it's in recent_files!
    
    FIXED: WorkingMemoryEntry now validates lines_read when created, so invalid
    lines_read like "0-10" raises ValueError and can't be added.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Add entry with invalid lines_read (line 0) - should raise ValueError
    with pytest.raises(ValueError, match="Invalid lines_read"):
        memory.add_recent_file(WorkingMemoryEntry(
            path="/test/file.py",
            purpose="Test",
            lines_read="0-10",  # Invalid: line 0 (1-indexed)
            key_insights=["Invalid line numbers"]
        ))
    
    print(f"Test - lines_read='0-10': Correctly rejected with ValueError")
    
    # Test with valid lines_read for comparison
    memory2 = WorkingMemory(current_task="Test")
    memory2.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="1-10",  # Valid
        key_insights=["Valid"]
    ))
    
    should_read2, reason2 = memory2.should_read_file("/test/file.py", 1, 10)
    print(f"Test - lines_read='1-10', request 1-10: should_read={should_read2}, reason={reason2}")
    assert should_read2 is False, f"Should return False (already read), got {should_read2}"
    assert "already read" in reason2.lower()
    
    # Test with valid lines_read for comparison
    memory2 = WorkingMemory(current_task="Test")
    memory2.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="1-10",  # Valid
        key_insights=["Valid"]
    ))
    
    should_read2, reason2 = memory2.should_read_file("/test/file.py", 1, 10)
    print(f"Test - lines_read='1-10', request 1-10: should_read={should_read2}, reason={reason2}")
    assert should_read2 is False, f"Should return False (already read), got {should_read2}"
    assert "already read" in reason2.lower()


if __name__ == "__main__":
    test_memory_should_read_file_invalid_lines_read_bug()
    print("\nTest demonstrates invalid lines_read bug in should_read_file")