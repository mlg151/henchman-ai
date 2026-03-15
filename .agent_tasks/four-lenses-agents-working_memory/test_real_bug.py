"""Test for a real bug in working_memory.py."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry, LineRange

def test_should_read_file_bug_with_multiple_entries_and_gaps():
    """Test a bug in should_read_file when multiple entries have gaps.
    
    Scenario:
    - Entry 1: Read lines 10-50
    - Entry 2: Read lines 60-100  
    - Request: Read lines 1-100
    
    There's a gap at lines 1-9 and 51-59.
    The method should return True (need to read).
    """
    memory = WorkingMemory(current_task="Test")
    
    # Add two entries with a gap between them
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "First read", "10-50"))
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Second read", "60-100"))
    
    # Request lines 1-100 (has gaps 1-9 and 51-59)
    should_read, reason = memory.should_read_file("/test/file.py", 1, 100)
    
    print(f"should_read: {should_read}, reason: {reason}")
    
    # Should return True because of gaps
    assert should_read is True, (
        f"Lines 1-100 have gaps (1-9, 51-59), should return True. "
        f"Got: {should_read}, reason: {reason}"
    )
    
    # Now test with merged ranges that should cover
    memory2 = WorkingMemory(current_task="Test")
    memory2.add_recent_file(WorkingMemoryEntry("/test/file2.py", "First read", "1-50"))
    memory2.add_recent_file(WorkingMemoryEntry("/test/file2.py", "Second read", "51-100"))
    
    # These are adjacent (50 and 51), so _merge_ranges should merge to 1-100
    should_read2, reason2 = memory2.should_read_file("/test/file2.py", 1, 100)
    
    print(f"should_read2: {should_read2}, reason2: {reason2}")
    
    # Should return False (covered by merged range 1-100)
    assert should_read2 is False, (
        f"Lines 1-100 should be covered by merged range 1-100. "
        f"Got: {should_read2}, reason: {reason2}"
    )

def test_parse_line_ranges_bug_with_negative_numbers():
    """Test _parse_line_ranges with negative numbers.
    
    BUG: What if lines_read contains negative numbers like "-10-20" or "10--20"?
    """
    from henchman.agents.working_memory import WorkingMemory
    
    memory = WorkingMemory(current_task="Test")
    
    # Test with negative start: "-10-20"
    ranges = memory._parse_line_ranges("-10-20")
    print(f"_parse_line_ranges('-10-20') = {ranges}")
    # Should return [] because start < 1
    
    # Test with negative end: "10--20"  
    ranges2 = memory._parse_line_ranges("10--20")
    print(f"_parse_line_ranges('10--20') = {ranges2}")
    # Regex finds first dash, splits: start_str="10", end_str="-20"
    # int("-20") raises ValueError, caught, continue, returns []
    
    # Test with valid range
    ranges3 = memory._parse_line_ranges("10-20")
    print(f"_parse_line_ranges('10-20') = {ranges3}")
    assert len(ranges3) == 1
    assert ranges3[0].start == 10
    assert ranges3[0].end == 20

if __name__ == "__main__":
    test_should_read_file_bug_with_multiple_entries_and_gaps()
    print("\n---")
    test_parse_line_ranges_bug_with_negative_numbers()
    print("\nTests complete.")