"""Test for bug in range coverage checking."""

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry, LineRange

def test_coverage_bug_disjoint_ranges():
    """Test bug when requested range is between two disjoint read ranges.
    
    Scenario:
    - Read lines 1-30
    - Read lines 70-100
    - Request: lines 40-60 (in the gap)
    
    Should return True (need to read).
    """
    memory = WorkingMemory(current_task="Test")
    
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "First", "1-30"))
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Second", "70-100"))
    
    # Request lines in the gap
    should_read, reason = memory.should_read_file("/test/file.py", 40, 60)
    
    print(f"should_read: {should_read}, reason: {reason}")
    
    # Should return True (gap)
    assert should_read is True, f"Lines 40-60 are in gap between 1-30 and 70-100, should return True. Got: {should_read}"
    assert "need to be read" in reason.lower() or "gap" in reason.lower()
    
    # Now test with requested range that starts in first range, ends in gap
    should_read2, reason2 = memory.should_read_file("/test/file.py", 20, 50)
    print(f"should_read2: {should_read2}, reason2: {reason2}")
    # 20-30 is in first range, 31-50 is in gap
    assert should_read2 is True
    
    # Request range that starts in gap, ends in second range
    should_read3, reason3 = memory.should_read_file("/test/file.py", 50, 80)
    print(f"should_read3: {should_read3}, reason3: {reason3}")
    # 50-69 is in gap, 70-80 is in second range
    assert should_read3 is True
    
    # Request range fully in first range
    should_read4, reason4 = memory.should_read_file("/test/file.py", 10, 20)
    print(f"should_read4: {should_read4}, reason4: {reason4}")
    assert should_read4 is False, f"Lines 10-20 are fully within first range 1-30, should return False. Got: {should_read4}"
    
    # Request range fully in second range
    should_read5, reason5 = memory.should_read_file("/test/file.py", 80, 90)
    print(f"should_read5: {should_read5}, reason5: {reason5}")
    assert should_read5 is False

def test_coverage_bug_single_range_covering_multiple():
    """Test when one large range covers multiple smaller ones."""
    memory = WorkingMemory(current_task="Test")
    
    # Add smaller ranges
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "First", "10-20"))
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Second", "30-40"))
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Third", "50-60"))
    
    # Add a large range that covers all (most recent)
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Large", "1-100"))
    
    # Request lines 15-18 (in first small range, also in large range)
    should_read, reason = memory.should_read_file("/test/file.py", 15, 18)
    print(f"should_read: {should_read}, reason: {reason}")
    
    # Most recent is "1-100" (not "full"), so we check coverage
    # valid_ranges from all entries: [LineRange(10,20), LineRange(30,40), LineRange(50,60), LineRange(1,100)]
    # merged_ranges: LineRange(1,100) covers all
    # Should return False
    assert should_read is False, f"Lines 15-18 are covered by large range 1-100, should return False. Got: {should_read}"

if __name__ == "__main__":
    test_coverage_bug_disjoint_ranges()
    print("\n---")
    test_coverage_bug_single_range_covering_multiple()
    print("\nTests complete.")