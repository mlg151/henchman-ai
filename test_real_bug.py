"""Test to find a real bug in working_memory.py."""

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry, LineRange

def test_line_range_from_string():
    """Test LineRange.from_string edge cases."""
    # Test valid range
    r = LineRange.from_str("10-20")
    assert r is not None
    assert r.start == 10
    assert r.end == 20
    
    # Test single line
    r = LineRange.from_str("10-10")
    assert r is not None
    assert r.start == 10
    assert r.end == 10
    
    # Test invalid: start > end
    r = LineRange.from_str("20-10")
    assert r is None  # Should return None
    
    # Test invalid: negative numbers
    r = LineRange.from_str("-5-10")
    assert r is None  # Should return None
    
    # Test invalid: not a string
    r = LineRange.from_str(None)  # type: ignore
    assert r is None
    
    # Test invalid: wrong format
    r = LineRange.from_str("10")
    assert r is None  # Missing dash
    
    r = LineRange.from_str("10-20-30")
    assert r is None  # Too many dashes
    
    print("LineRange.from_string tests passed")

def test_parse_line_ranges():
    """Test _parse_line_ranges edge cases."""
    from henchman.agents.working_memory import WorkingMemory
    
    # Test "full"
    memory = WorkingMemory(current_task="Test")
    ranges = memory._parse_line_ranges("full")
    assert ranges == []  # "full" returns empty list
    
    # Test single range
    ranges = memory._parse_line_ranges("10-20")
    assert len(ranges) == 1
    assert ranges[0].start == 10
    assert ranges[0].end == 20
    
    # Test multiple ranges
    ranges = memory._parse_line_ranges("10-20,30-40")
    assert len(ranges) == 2
    assert ranges[0].start == 10
    assert ranges[0].end == 20
    assert ranges[1].start == 30
    assert ranges[1].end == 40
    
    # Test single line
    ranges = memory._parse_line_ranges("10")
    assert len(ranges) == 1
    assert ranges[0].start == 10
    assert ranges[0].end == 10
    
    # Test with whitespace
    ranges = memory._parse_line_ranges(" 10 - 20 , 30 - 40 ")
    assert len(ranges) == 2
    assert ranges[0].start == 10
    assert ranges[0].end == 20
    assert ranges[1].start == 30
    assert ranges[1].end == 40
    
    # Test invalid: negative numbers
    ranges = memory._parse_line_ranges("-5-10")
    assert ranges == []  # Should skip invalid
    
    # Test invalid: start > end
    ranges = memory._parse_line_ranges("20-10")
    assert ranges == []  # Should skip invalid
    
    # Test invalid: non-numeric
    ranges = memory._parse_line_ranges("abc-def")
    assert ranges == []  # Should skip invalid
    
    print("_parse_line_ranges tests passed")

def test_should_read_file_edge_cases():
    """Test edge cases for should_read_file."""
    memory = WorkingMemory(current_task="Test")
    
    # Test 1: File not in memory
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)
    assert should_read is True
    assert "not in recent files" in reason
    
    # Test 2: File marked as "full"
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Full read", "full"))
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)
    assert should_read is False
    assert "already read (full)" in reason
    
    # Test 3: Invalid line numbers (start < 1)
    should_read, reason = memory.should_read_file("/test/file.py", 0, 20)
    assert should_read is True
    assert "Invalid line number" in reason
    
    # Test 4: Invalid line numbers (end < 1)
    should_read, reason = memory.should_read_file("/test/file.py", 10, 0)
    assert should_read is True
    assert "Invalid line number" in reason
    
    # Test 5: start > end
    should_read, reason = memory.should_read_file("/test/file.py", 20, 10)
    assert should_read is True
    assert "start (20) > end (10)" in reason
    
    # Test 6: Request entire file (start=None, end=None) when file was read fully
    should_read, reason = memory.should_read_file("/test/file.py")
    assert should_read is False
    assert "already read (full)" in reason
    
    # Test 7: Request entire file when file was partially read
    memory2 = WorkingMemory(current_task="Test")
    memory2.add_recent_file(WorkingMemoryEntry("/test/file2.py", "Partial read", "10-50"))
    should_read, reason = memory2.should_read_file("/test/file2.py")
    assert should_read is True
    assert "File not fully read" in reason
    
    print("should_read_file edge case tests passed")

def test_merge_ranges():
    """Test _merge_ranges edge cases."""
    from henchman.agents.working_memory import WorkingMemory, LineRange
    
    memory = WorkingMemory(current_task="Test")
    
    # Test empty list
    merged = memory._merge_ranges([])
    assert merged == []
    
    # Test single range
    merged = memory._merge_ranges([LineRange(10, 20)])
    assert len(merged) == 1
    assert merged[0].start == 10
    assert merged[0].end == 20
    
    # Test overlapping ranges
    merged = memory._merge_ranges([LineRange(10, 20), LineRange(15, 25)])
    assert len(merged) == 1
    assert merged[0].start == 10
    assert merged[0].end == 25
    
    # Test adjacent ranges (should merge)
    merged = memory._merge_ranges([LineRange(10, 20), LineRange(21, 30)])
    assert len(merged) == 1
    assert merged[0].start == 10
    assert merged[0].end == 30
    
    # Test non-overlapping, non-adjacent ranges
    merged = memory._merge_ranges([LineRange(10, 20), LineRange(30, 40)])
    assert len(merged) == 2
    assert merged[0].start == 10
    assert merged[0].end == 20
    assert merged[1].start == 30
    assert merged[1].end == 40
    
    # Test unsorted ranges (should sort first)
    merged = memory._merge_ranges([LineRange(30, 40), LineRange(10, 20)])
    assert len(merged) == 2
    assert merged[0].start == 10
    assert merged[0].end == 20
    assert merged[1].start == 30
    assert merged[1].end == 40
    
    print("_merge_ranges tests passed")

if __name__ == "__main__":
    test_line_range_from_string()
    test_parse_line_ranges()
    test_should_read_file_edge_cases()
    test_merge_ranges()
    print("\nAll tests passed!")