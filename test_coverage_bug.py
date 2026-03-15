"""Test coverage algorithm edge cases."""

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry, LineRange

def test_coverage_algorithm():
    """Test the coverage checking algorithm for edge cases."""
    
    # Test case 1: Requested range exactly matches a merged range
    # Requested: 10-20, Merged: [10-20]
    # Should return False (covered)
    
    # Test case 2: Requested range is subset of a merged range
    # Requested: 15-18, Merged: [10-20]
    # Should return False (covered)
    
    # Test case 3: Requested range spans multiple merged ranges with no gaps
    # Requested: 10-30, Merged: [10-15, 16-20, 21-30]
    # Should return False (covered) - ranges are adjacent
    
    # Test case 4: Requested range has gap in middle
    # Requested: 10-30, Merged: [10-15, 25-30]
    # Should return True (gap 16-24)
    
    # Test case 5: Requested range starts before first merged range
    # Requested: 5-15, Merged: [10-20]
    # Should return True (lines 5-9 not covered)
    
    # Test case 6: Requested range ends after last merged range
    # Requested: 15-25, Merged: [10-20]
    # Should return True (lines 21-25 not covered)
    
    # Test case 7: Empty merged ranges
    # Requested: 10-20, Merged: []
    # Should return True (nothing covered)
    
    # Actually, let me trace through the algorithm for case 3:
    # current_line = 10
    # First range: 10-15
    #   current_line < 10? False
    #   current_line <= 15? True (10 <= 15)
    #   current_line = 15 + 1 = 16
    #   current_line > 30? False
    # Second range: 16-20
    #   current_line < 16? False (16 < 16 is False)
    #   current_line <= 20? True (16 <= 20)
    #   current_line = 20 + 1 = 21
    #   current_line > 30? False
    # Third range: 21-30
    #   current_line < 21? False (21 < 21 is False)
    #   current_line <= 30? True (21 <= 30)
    #   current_line = 30 + 1 = 31
    #   current_line > 30? True (31 > 30)
    # Return False (covered)
    
    # That works! Adjacent ranges (15 and 16) are handled correctly because
    # after first range, current_line = 16, which is equal to second range start (16)
    # So current_line < rng.start is False (16 < 16 is False)
    # And current_line <= rng.end is True (16 <= 20)
    
    # But wait! What if ranges overlap? Like [10-20, 15-25]
    # They would be merged by _merge_ranges into [10-25]
    
    print("Algorithm seems correct for these cases")
    
    # Actually, let me test a real edge case: what if merged_ranges is not sorted?
    # The algorithm sorts them first with sorted(ranges, key=lambda r: r.start)
    
    # What about when current_line == rng.start + 1? Actually, that's covered.
    
    # I think the algorithm is correct!
    
    # But wait! Let me check the actual implementation again...
    # The bug might be elsewhere. Let me look at the test file comments again.

if __name__ == "__main__":
    test_coverage_algorithm()