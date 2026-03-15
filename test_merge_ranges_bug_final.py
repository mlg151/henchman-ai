"""Demonstrate the bug in _merge_ranges that modifies input objects."""

from henchman.agents.working_memory import WorkingMemory, LineRange

def test_merge_ranges_modifies_input():
    """Test that _merge_ranges modifies input LineRange objects (BUG)."""
    memory = WorkingMemory(current_task="Test")
    
    # Create input ranges that will be merged
    range1 = LineRange(10, 20)
    range2 = LineRange(15, 25)  # Overlaps with range1
    
    # Store original values
    original_range1_end = range1.end
    original_range2_end = range2.end
    
    # Call _merge_ranges
    merged = memory._merge_ranges([range1, range2])
    
    # Check results
    assert len(merged) == 1
    assert merged[0].start == 10
    assert merged[0].end == 25
    
    # Check if input objects were modified (THE BUG)
    # range1.end should still be 20, but it might be 25
    print(f"range1.end before: {original_range1_end}, after: {range1.end}")
    print(f"range2.end before: {original_range2_end}, after: {range2.end}")
    
    # This is the bug: range1.end might be modified
    if range1.end != original_range1_end:
        print("BUG CONFIRMED: range1.end was modified!")
        return True
    else:
        print("range1.end was NOT modified (unexpected)")
        return False

def test_merge_ranges_does_not_modify_non_overlapping():
    """Test that _merge_ranges does not modify non-overlapping input objects."""
    memory = WorkingMemory(current_task="Test")
    
    # Create non-overlapping ranges
    range1 = LineRange(10, 20)
    range2 = LineRange(30, 40)
    
    # Store original values
    original_range1_end = range1.end
    original_range2_end = range2.end
    
    # Call _merge_ranges
    merged = memory._merge_ranges([range1, range2])
    
    # Check results
    assert len(merged) == 2  # Should not merge
    
    # Check if input objects were modified (should not be)
    assert range1.end == original_range1_end
    assert range2.end == original_range2_end
    
    print("Non-overlapping ranges not modified (correct)")

if __name__ == "__main__":
    print("Testing _merge_ranges bug...")
    bug_found = test_merge_ranges_modifies_input()
    test_merge_ranges_does_not_modify_non_overlapping()
    
    if bug_found:
        print("\n✓ BUG FOUND: _merge_ranges modifies input objects!")
    else:
        print("\n✗ No bug found (unexpected)")