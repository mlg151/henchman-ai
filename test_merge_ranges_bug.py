"""Test the bug in _merge_ranges that modifies input objects."""

from henchman.agents.working_memory import WorkingMemory, LineRange

def test_merge_ranges_modifies_input():
    """Test that _merge_ranges modifies input LineRange objects."""
    memory = WorkingMemory(current_task="Test")
    
    # Create input ranges
    range1 = LineRange(10, 20)
    range2 = LineRange(15, 25)  # Overlaps with range1
    
    # Store original values
    original_range1_end = range1.end
    original_range2_end = range2.end
    
    # Call _merge_ranges
    merged = memory._merge_ranges([range1, range2])
    
    # Check if input objects were modified
    print(f"range1.end before: {original_range1_end}, after: {range1.end}")
    print(f"range2.end before: {original_range2_end}, after: {range2.end}")
    
    # range1.end should be modified! Because range1 is in the merged list
    # and we modify last.end in place
    
    assert len(merged) == 1
    assert merged[0].start == 10
    assert merged[0].end == 25  # Merged range
    
    # Check if input was modified
    # Actually, range1 is the first element in the input list
    # When we sort, we get [range1, range2] (already sorted)
    # range1 becomes 'last' in merged list
    # We modify last.end = max(20, 25) = 25
    # So range1.end becomes 25!
    
    assert range1.end == 25  # Modified!
    assert range2.end == 25  # Also modified? Let me check...
    # Actually, range2.end should still be 25 (unchanged)
    
    print("BUG CONFIRMED: _merge_ranges modifies input objects!")
    
    # Test with non-overlapping ranges
    range3 = LineRange(10, 20)
    range4 = LineRange(30, 40)
    
    original_range3_end = range3.end
    original_range4_end = range4.end
    
    merged2 = memory._merge_ranges([range3, range4])
    
    print(f"\nNon-overlapping test:")
    print(f"range3.end before: {original_range3_end}, after: {range3.end}")
    print(f"range4.end before: {original_range4_end}, after: {range4.end}")
    
    # range3 and range4 should not be modified (no merging)
    assert range3.end == 20  # Unchanged
    assert range4.end == 40  # Unchanged
    
    print("Non-overlapping ranges not modified (correct)")

if __name__ == "__main__":
    test_merge_ranges_modifies_input()