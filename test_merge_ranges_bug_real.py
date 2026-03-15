"""Test for a real bug in _merge_ranges."""

from henchman.agents.working_memory import WorkingMemory, LineRange

def test_merge_ranges_adjacent_bug():
    """Test that _merge_ranges correctly merges adjacent ranges.
    
    BUG: When ranges are adjacent (e.g., 10-20 and 21-30), they should be merged.
    But what if the ranges are 10-20 and 20-30? They overlap at line 20!
    Actually, 10-20 ends at 20, 20-30 starts at 20. They're adjacent, not overlapping.
    Line 20 is in both ranges? 10-20 includes line 20, 20-30 includes line 20.
    So they overlap at line 20!
    """
    memory = WorkingMemory(current_task="Test")
    
    # Test overlapping ranges (10-20 and 20-30)
    range1 = LineRange(10, 20)
    range2 = LineRange(20, 30)
    
    merged = memory._merge_ranges([range1, range2])
    
    print(f"range1: {range1}")
    print(f"range2: {range2}")
    print(f"merged: {merged}")
    
    # Should merge into 10-30
    assert len(merged) == 1
    assert merged[0].start == 10
    assert merged[0].end == 30
    
    print("Test passes - ranges are merged correctly")
    
    # Test adjacent ranges (10-20 and 21-30)
    range3 = LineRange(10, 20)
    range4 = LineRange(21, 30)
    
    merged2 = memory._merge_ranges([range3, range4])
    
    print(f"\nrange3: {range3}")
    print(f"range4: {range4}")
    print(f"merged2: {merged2}")
    
    # Should merge into 10-30 (adjacent: 20 and 21)
    assert len(merged2) == 1
    assert merged2[0].start == 10
    assert merged2[0].end == 30
    
    print("Test passes - adjacent ranges are merged correctly")
    
    # Test non-adjacent ranges (10-20 and 22-30)
    range5 = LineRange(10, 20)
    range6 = LineRange(22, 30)
    
    merged3 = memory._merge_ranges([range5, range6])
    
    print(f"\nrange5: {range5}")
    print(f"range6: {range6}")
    print(f"merged3: {merged3}")
    
    # Should NOT merge (gap at line 21)
    assert len(merged3) == 2
    assert merged3[0].start == 10
    assert merged3[0].end == 20
    assert merged3[1].start == 22
    assert merged3[1].end == 30
    
    print("Test passes - non-adjacent ranges are not merged")

if __name__ == "__main__":
    test_merge_ranges_adjacent_bug()