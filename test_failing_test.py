"""Write a failing test to demonstrate a bug."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

def test_should_read_file_edge_case():
    """Test an edge case that should fail but doesn't."""
    memory = WorkingMemory(current_task="Test")
    
    # Add a file read with lines 10-20
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-20"))
    
    # Request lines 5-15 (overlaps with 10-20)
    # We've read lines 10-20, but we need lines 5-9
    should_read, reason = memory.should_read_file("/test/file.py", 5, 15)
    
    # Should return True (need to read lines 5-9)
    assert should_read is True
    assert "need to read" in reason.lower()
    
    # Actually, this should pass! Let me think of a real edge case...
    
    # What about requesting lines 10-10 (single line within range)?
    should_read2, reason2 = memory.should_read_file("/test/file.py", 10, 10)
    
    # Should return False (line 10 is within 10-20)
    assert should_read2 is False
    assert "already read" in reason2.lower()
    
    # This should also pass!
    
    print("Both tests pass (no bug found)")

def test_parse_line_ranges_edge_case():
    """Test edge case in _parse_line_ranges."""
    from henchman.agents.working_memory import WorkingMemory
    
    memory = WorkingMemory(current_task="Test")
    
    # Test with string "0" (invalid line number)
    ranges = memory._parse_line_ranges("0")
    assert ranges == []  # Should skip line 0
    
    # Test with string "0-10" (invalid start line)
    ranges = memory._parse_line_ranges("0-10")
    assert ranges == []  # Should skip
    
    # Test with string "10-0" (invalid end line)
    ranges = memory._parse_line_ranges("10-0")
    assert ranges == []  # Should skip
    
    # Test with string "10-10-20" (invalid format)
    ranges = memory._parse_line_ranges("10-10-20")
    # This splits into parts: ["10-10-20"]
    # "-" in part is True
    # part.split("-", 1) returns ["10", "10-20"]
    # start_str = "10", end_str = "10-20"
    # int("10-20") raises ValueError
    # caught by except ValueError: continue
    # So should skip
    assert ranges == []
    
    print("All edge case tests pass (no bug found)")

def test_line_range_from_str_edge_case():
    """Test edge case in LineRange.from_str."""
    from henchman.agents.working_memory import LineRange
    
    # Test with empty string
    r = LineRange.from_str("")
    assert r is None
    
    # Test with "10-10" (single line)
    r = LineRange.from_str("10-10")
    assert r is not None
    assert r.start == 10
    assert r.end == 10
    
    # Test with "10-5" (start > end)
    r = LineRange.from_str("10-5")
    assert r is None  # Should return None
    
    # Test with "0-10" (invalid line 0)
    r = LineRange.from_str("0-10")
    assert r is None  # Should return None (__post_init__ raises ValueError)
    
    print("All LineRange.from_str tests pass (no bug found)")

if __name__ == "__main__":
    test_should_read_file_edge_case()
    test_parse_line_ranges_edge_case()
    test_line_range_from_str_edge_case()
    print("\nNo bugs found!")