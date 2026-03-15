"""Test edge case that might reveal a bug."""

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry, LineRange

def test_merge_ranges_edge_case():
    """Test _merge_ranges with edge cases."""
    memory = WorkingMemory(current_task="Test")
    
    # Test 1: Empty list
    assert memory._merge_ranges([]) == []
    
    # Test 2: Single range
    ranges1 = [LineRange(1, 10)]
    assert memory._merge_ranges(ranges1) == [LineRange(1, 10)]
    
    # Test 3: Overlapping ranges
    ranges2 = [LineRange(1, 10), LineRange(5, 15)]
    merged2 = memory._merge_ranges(ranges2)
    assert merged2 == [LineRange(1, 15)], f"Expected [1-15], got {merged2}"
    
    # Test 4: Adjacent ranges (should merge)
    ranges3 = [LineRange(1, 10), LineRange(11, 20)]
    merged3 = memory._merge_ranges(ranges3)
    assert merged3 == [LineRange(1, 20)], f"Expected [1-20], got {merged3}"
    
    # Test 5: Non-overlapping, non-adjacent (should not merge)
    ranges4 = [LineRange(1, 10), LineRange(15, 20)]
    merged4 = memory._merge_ranges(ranges4)
    assert merged4 == [LineRange(1, 10), LineRange(15, 20)], f"Expected [1-10, 15-20], got {merged4}"
    
    # Test 6: Unsorted ranges (should sort first)
    ranges5 = [LineRange(15, 20), LineRange(1, 10)]
    merged5 = memory._merge_ranges(ranges5)
    assert merged5 == [LineRange(1, 10), LineRange(15, 20)], f"Expected [1-10, 15-20], got {merged5}"
    
    # Test 7: Three ranges where middle connects both
    ranges6 = [LineRange(1, 5), LineRange(6, 10), LineRange(8, 15)]
    merged6 = memory._merge_ranges(ranges6)
    # 1-5 and 6-10 are adjacent (6 <= 5+1) -> merge to 1-10
    # 1-10 and 8-15 overlap (8 <= 10+1) -> merge to 1-15
    assert merged6 == [LineRange(1, 15)], f"Expected [1-15], got {merged6}"
    
    print("✓ All _merge_ranges tests pass")

def test_should_read_file_edge_case():
    """Test should_read_file with edge cases."""
    memory = WorkingMemory(current_task="Test")
    
    # File read with gaps: 1-10 and 20-30
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "First", "1-10"))
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Second", "20-30"))
    
    # Request 5-25: covers 5-10 (covered), 11-19 (gap), 20-25 (covered)
    # Should return True (gap 11-19)
    should_read, reason = memory.should_read_file("/test/file.py", 5, 25)
    assert should_read is True, f"Expected True (gap), got {should_read}"
    assert "gap" in reason.lower() or "new" in reason.lower() or "partially" in reason.lower()
    
    # Request 1-30: covers entire range (with gap 11-19)
    # Should return True (gap)
    should_read2, reason2 = memory.should_read_file("/test/file.py", 1, 30)
    assert should_read2 is True, f"Expected True (gap), got {should_read2}"
    
    # Request 1-10: fully covered
    should_read3, reason3 = memory.should_read_file("/test/file.py", 1, 10)
    assert should_read3 is False, f"Expected False (covered), got {should_read3}"
    
    # Request 20-30: fully covered
    should_read4, reason4 = memory.should_read_file("/test/file.py", 20, 30)
    assert should_read4 is False, f"Expected False (covered), got {should_read4}"
    
    # Request 15-25: covers gap 15-19 and part of 20-25
    # Should return True (gap at beginning)
    should_read5, reason5 = memory.should_read_file("/test/file.py", 15, 25)
    assert should_read5 is True, f"Expected True (gap), got {should_read5}"
    
    print("✓ All should_read_file edge case tests pass")

def test_parse_line_ranges_edge_case():
    """Test _parse_line_ranges with edge cases."""
    memory = WorkingMemory(current_task="Test")
    
    # Test empty/whitespace
    assert memory._parse_line_ranges("") == []
    assert memory._parse_line_ranges("   ") == []
    assert memory._parse_line_ranges("\t\n") == []
    
    # Test "full" with various whitespace
    assert memory._parse_line_ranges("full") == []
    assert memory._parse_line_ranges("FULL") == []
    assert memory._parse_line_ranges("Full") == []
    assert memory._parse_line_ranges(" full ") == []
    assert memory._parse_line_ranges("full,10-20") == []  # "full" present means fully read
    
    # Test invalid formats
    assert memory._parse_line_ranges("invalid") == []
    assert memory._parse_line_ranges("10--20") == []  # double dash
    assert memory._parse_line_ranges("20-10") == []  # start > end
    assert memory._parse_line_ranges("0-10") == []  # line 0
    assert memory._parse_line_ranges("-5-10") == []  # negative start
    
    # Test mixed valid and invalid
    result = memory._parse_line_ranges("10-20,invalid,30-40")
    assert len(result) == 2
    assert result[0] == LineRange(10, 20)
    assert result[1] == LineRange(30, 40)
    
    # Test with different dash characters
    # Note: The regex matches various dash characters
    # We can't easily test Unicode dashes here
    
    print("✓ All _parse_line_ranges edge case tests pass")

if __name__ == "__main__":
    print("Testing edge cases for bugs...")
    print("=" * 60)
    
    test_merge_ranges_edge_case()
    test_should_read_file_edge_case()
    test_parse_line_ranges_edge_case()
    
    print("=" * 60)
    print("All edge case tests pass - no bugs found!")
    print("Note: The boolean bug has been fixed.")
    print("Note: The invalid line number bug has been fixed.")