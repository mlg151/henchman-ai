"""Test for a real bug in working_memory.py."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

def test_bug_key_insights_string():
    """BUG: key_insights as string creates list of characters."""
    # This should fail or handle gracefully
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="1-10",
        key_insights="Important finding"  # String instead of list!
    )
    
    memory = WorkingMemory(current_task="Test")
    # This will call list("Important finding") -> ['I', 'm', 'p', 'o', ...]
    memory.add_recent_file(entry)
    
    # Check what happened
    print(f"Entry added: {memory.recent_files[0]}")
    print(f"key_insights type: {type(memory.recent_files[0].key_insights)}")
    print(f"key_insights value: {memory.recent_files[0].key_insights}")
    
    # This is a bug! key_insights should be ["Important finding"], not list of chars
    # But is it a "core functionality" bug?

def test_bug_should_read_file_with_end_minus_one_and_full():
    """BUG: end=-1 with file read 'full' returns incorrect result."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="full"
    ))
    
    # File was read fully
    # User wants to check if lines 10-EOF need to be read
    # Since file was read fully, should return False
    should_read, reason = memory.should_read_file("/test/file.py", 10, -1)
    
    print(f"File read 'full', request lines 10-EOF (end=-1):")
    print(f"  Result: should_read={should_read}, reason={reason}")
    print(f"  Expected: False (file read fully)")
    
    # Actually, this works correctly! Returns False, "File already read (full)"
    assert should_read is False, f"Expected False, got {should_read}"
    assert "already read" in reason.lower()

def test_bug_parse_line_ranges_unicode_dash():
    """Test _parse_line_ranges with Unicode dash characters."""
    memory = WorkingMemory(current_task="Test")
    
    # Test with en dash U+2013
    # Note: Python string literal with Unicode
    ranges = memory._parse_line_ranges("10\u201320")  # en dash
    print(f"Parsing '10\\u201320' (en dash): {ranges}")
    # Should parse as 10-20
    
    # Test with em dash U+2014
    ranges2 = memory._parse_line_ranges("10\u201420")  # em dash
    print(f"Parsing '10\\u201420' (em dash): {ranges2}")
    # Should parse as 10-20
    
    # The regex r'[-\u2012\u2013\u2014\u2015\u2212]' should match these

def test_bug_should_read_file_with_invalid_lines_read():
    """BUG: Invalid lines_read format not handled correctly in coverage check."""
    memory = WorkingMemory(current_task="Test")
    
    # Add entry with invalid lines_read (empty string)
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read=""  # Empty string
    ))
    
    # Request to read lines 10-20
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)
    
    print(f"File with lines_read='', request 10-20:")
    print(f"  Result: should_read={should_read}, reason={reason}")
    print(f"  Expected: True with 'Cannot determine' or similar")
    
    # lines_read="" parses to [] (empty list)
    # valid_ranges is empty
    # Line 445: if not valid_ranges: return True, "Cannot determine - invalid lines_read format"
    # This seems correct!

if __name__ == "__main__":
    print("Testing for real bugs...")
    print("=" * 60)
    
    test_bug_key_insights_string()
    print()
    
    test_bug_should_read_file_with_end_minus_one_and_full()
    print()
    
    test_bug_parse_line_ranges_unicode_dash()
    print()
    
    test_bug_should_read_file_with_invalid_lines_read()
    
    print("=" * 60)
    print("Note: Most 'bugs' tested here are actually handled correctly.")
    print("The boolean bug and invalid line number bug have been fixed.")
    print("Need to find a different bug.")