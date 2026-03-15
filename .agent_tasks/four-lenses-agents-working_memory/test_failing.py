"""Test that should fail to expose a bug."""

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

def test_bug_coverage_algorithm():
    """Test the coverage algorithm for a bug."""
    memory = WorkingMemory(current_task="Test")
    
    # File read with ranges: 1-10 and 20-30 (gap 11-19)
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "First", "1-10"))
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Second", "20-30"))
    
    # Test case 1: Request 5-15 (overlaps first range and gap)
    # 5-10 covered, 11-15 not covered (gap)
    # Should return True
    should_read, reason = memory.should_read_file("/test/file.py", 5, 15)
    print(f"Request 5-15: should_read={should_read}, reason={reason}")
    assert should_read is True, f"Expected True (gap 11-15), got {should_read}"
    
    # Test case 2: Request 15-25 (overlaps gap and second range)
    # 15-19 not covered (gap), 20-25 covered
    # Should return True
    should_read2, reason2 = memory.should_read_file("/test/file.py", 15, 25)
    print(f"Request 15-25: should_read={should_read2}, reason={reason2}")
    assert should_read2 is True, f"Expected True (gap 15-19), got {should_read2}"
    
    # Test case 3: Request 11-19 (entirely in gap)
    # Should return True
    should_read3, reason3 = memory.should_read_file("/test/file.py", 11, 19)
    print(f"Request 11-19: should_read={should_read3}, reason={reason3}")
    assert should_read3 is True, f"Expected True (entirely in gap), got {should_read3}"
    
    # Test case 4: Request 1-30 (entire range with gap)
    # Should return True
    should_read4, reason4 = memory.should_read_file("/test/file.py", 1, 30)
    print(f"Request 1-30: should_read={should_read4}, reason={reason4}")
    assert should_read4 is True, f"Expected True (gap 11-19), got {should_read4}"
    
    # Test case 5: Request 1-10 (fully covered)
    # Should return False
    should_read5, reason5 = memory.should_read_file("/test/file.py", 1, 10)
    print(f"Request 1-10: should_read={should_read5}, reason={reason5}")
    assert should_read5 is False, f"Expected False (fully covered), got {should_read5}"
    
    # Test case 6: Request 20-30 (fully covered)
    # Should return False
    should_read6, reason6 = memory.should_read_file("/test/file.py", 20, 30)
    print(f"Request 20-30: should_read={should_read6}, reason={reason6}")
    assert should_read6 is False, f"Expected False (fully covered), got {should_read6}"
    
    print("✓ All coverage algorithm tests pass (no bug found)")

def test_bug_single_range_edge():
    """Test edge case with single range."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-100"))
    
    # Request 50-150 (partially covered, need 101-150)
    should_read, reason = memory.should_read_file("/test/file.py", 50, 150)
    print(f"File read 1-100, request 50-150: should_read={should_read}, reason={reason}")
    # Should return True (need 101-150)
    assert should_read is True, f"Expected True (need 101-150), got {should_read}"
    
    # Request 101-150 (not covered at all)
    should_read2, reason2 = memory.should_read_file("/test/file.py", 101, 150)
    print(f"File read 1-100, request 101-150: should_read={should_read2}, reason={reason2}")
    # Should return True (not covered)
    assert should_read2 is True, f"Expected True (not covered), got {should_read2}"
    
    print("✓ Single range edge tests pass (no bug found)")

def test_bug_empty_ranges():
    """Test with empty/valid ranges."""
    memory = WorkingMemory(current_task="Test")
    
    # Add entry with empty lines_read (invalid)
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", ""))
    
    # Request 1-10
    should_read, reason = memory.should_read_file("/test/file.py", 1, 10)
    print(f"File with lines_read='', request 1-10: should_read={should_read}, reason={reason}")
    # Should return True (cannot determine)
    assert should_read is True, f"Expected True (cannot determine), got {should_read}"
    assert "cannot determine" in reason.lower() or "invalid" in reason.lower()
    
    print("✓ Empty ranges test passes (no bug found)")

if __name__ == "__main__":
    print("Testing for bugs in coverage algorithm...")
    print("=" * 60)
    
    test_bug_coverage_algorithm()
    print()
    
    test_bug_single_range_edge()
    print()
    
    test_bug_empty_ranges()
    
    print("=" * 60)
    print("All tests pass - no bugs found in coverage algorithm!")
    print("The code correctly handles gaps, partial coverage, and edge cases.")