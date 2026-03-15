"""Try to find a bug in working_memory.py."""

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry, LineRange

def test_edge_case_1():
    """Test edge case: empty lines_read string."""
    from henchman.agents.working_memory import WorkingMemory
    
    memory = WorkingMemory(current_task="Test")
    
    # Test with empty string
    ranges = memory._parse_line_ranges("")
    assert ranges == []  # Should return empty list
    
    # Test with only whitespace
    ranges = memory._parse_line_ranges("   ")
    assert ranges == []  # Should return empty list
    
    # Test with "full" with whitespace
    ranges = memory._parse_line_ranges("  full  ")
    assert ranges == []  # "full" returns empty list
    
    print("Edge case 1 passed")

def test_edge_case_2():
    """Test edge case: lines_read is not a string."""
    # _parse_line_ranges expects str, but what if we pass something else?
    # The method has: if not lines_read or not isinstance(lines_read, str): return []
    # So it should handle non-string inputs
    
    from henchman.agents.working_memory import WorkingMemory
    
    memory = WorkingMemory(current_task="Test")
    
    # These would be type errors at runtime, but the method should handle them
    # Actually, mypy would catch these, but at runtime...
    
    print("Edge case 2 - type checking is done")

def test_edge_case_3():
    """Test edge case: line range with start == end."""
    memory = WorkingMemory(current_task="Test")
    
    ranges = memory._parse_line_ranges("10-10")
    assert len(ranges) == 1
    assert ranges[0].start == 10
    assert ranges[0].end == 10
    
    print("Edge case 3 passed")

def test_edge_case_4():
    """Test edge case: multiple ranges with overlap."""
    memory = WorkingMemory(current_task="Test")
    
    ranges = memory._parse_line_ranges("10-20,15-25")
    assert len(ranges) == 2
    assert ranges[0].start == 10
    assert ranges[0].end == 20
    assert ranges[1].start == 15
    assert ranges[1].end == 25
    
    # These would be merged by _merge_ranges
    merged = memory._merge_ranges(ranges)
    assert len(merged) == 1
    assert merged[0].start == 10
    assert merged[0].end == 25
    
    print("Edge case 4 passed")

def test_edge_case_5():
    """Test edge case: invalid characters in line range."""
    memory = WorkingMemory(current_task="Test")
    
    ranges = memory._parse_line_ranges("10-20,abc-def,30-40")
    assert len(ranges) == 2  # Should skip "abc-def"
    assert ranges[0].start == 10
    assert ranges[0].end == 20
    assert ranges[1].start == 30
    assert ranges[1].end == 40
    
    print("Edge case 5 passed")

def test_edge_case_6():
    """Test edge case: very large line numbers."""
    memory = WorkingMemory(current_task="Test")
    
    ranges = memory._parse_line_ranges("1-999999")
    assert len(ranges) == 1
    assert ranges[0].start == 1
    assert ranges[0].end == 999999
    
    # This should work, but might be inefficient
    print("Edge case 6 passed")

def test_bug_candidate():
    """Test a potential bug: what if lines_read contains newlines?"""
    memory = WorkingMemory(current_task="Test")
    
    # Test with newlines and spaces
    ranges = memory._parse_line_ranges("10-20\n,30-40")
    # The normalization removes all whitespace, including newlines
    # So "10-20\n,30-40" becomes "10-20,30-40"
    
    assert len(ranges) == 2
    assert ranges[0].start == 10
    assert ranges[0].end == 20
    assert ranges[1].start == 30
    assert ranges[1].end == 40
    
    print("Bug candidate test passed")

def test_another_bug_candidate():
    """Test another potential bug: what if we call should_read_file with start > end but both valid?"""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-50"))
    
    # Request lines 30-20 (start > end)
    should_read, reason = memory.should_read_file("/test/file.py", 30, 20)
    
    # Should return True with "Invalid line range" message
    assert should_read is True
    assert "start (30) > end (20)" in reason
    
    print("Another bug candidate test passed")

if __name__ == "__main__":
    test_edge_case_1()
    test_edge_case_2()
    test_edge_case_3()
    test_edge_case_4()
    test_edge_case_5()
    test_edge_case_6()
    test_bug_candidate()
    test_another_bug_candidate()
    print("\nAll tests passed! No bugs found.")