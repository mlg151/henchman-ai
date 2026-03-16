"""Test for an actual bug in working_memory.py."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_memory_should_read_file_merge_bug():
    """Test potential bug in range merging logic.
    
    Scenario: File was read in two separate ranges: 1-10 and 20-30.
    There's a gap at 11-19.
    Request to read lines 5-25.
    
    The merged ranges would be [1-10, 20-30] (not merged because gap > 1).
    The requested range 5-25 overlaps with both but is not fully contained.
    Should return True (need to read).
    """
    memory = WorkingMemory(current_task="Test")
    
    # Add two non-adjacent reads
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "First", "1-10"))
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Second", "20-30"))
    
    # Request lines 5-25 (overlaps both, gap in middle)
    should_read, reason = memory.should_read_file("/test/file.py", 5, 25)
    
    print(f"Ranges: 1-10, 20-30")
    print(f"Request: 5-25")
    print(f"Result: should_read={should_read}, reason={reason}")
    
    # Lines 5-10 are read, 11-19 are NOT read (gap), 20-25 are read
    # So we need to read lines 11-19
    assert should_read is True, f"Should need to read lines 11-19. Got: {should_read}"
    assert "need to be read" in reason.lower() or "new or partially" in reason.lower()


def test_memory_should_read_file_covered_by_multiple():
    """Test when requested range is covered by multiple non-adjacent ranges.
    
    Scenario: File was read 1-10 and 11-20 (adjacent, would merge to 1-20).
    Request to read 5-15.
    
    The merged ranges would be [1-20] (adjacent, so merged).
    Requested range 5-15 is fully contained in 1-20.
    Should return False (already read).
    """
    memory = WorkingMemory(current_task="Test")
    
    # Add two adjacent reads (should merge)
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "First", "1-10"))
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Second", "11-20"))
    
    # Request lines 5-15 (fully contained in merged 1-20)
    should_read, reason = memory.should_read_file("/test/file.py", 5, 15)
    
    print(f"Ranges: 1-10, 11-20 (adjacent, should merge to 1-20)")
    print(f"Request: 5-15")
    print(f"Result: should_read={should_read}, reason={reason}")
    
    # Should be False (fully contained in merged range 1-20)
    assert should_read is False, f"Lines 5-15 are fully contained in merged range 1-20. Got: {should_read}"
    assert "already read" in reason.lower() or "covered" in reason.lower()


def test_memory_should_read_file_edge_case_merge():
    """Test edge case of merging.
    
    Scenario: Ranges 1-5 and 6-10 are adjacent (5 and 6).
    Should merge to 1-10.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Test _merge_ranges directly
    from henchman.agents.working_memory import LineRange
    
    ranges = [LineRange(1, 5), LineRange(6, 10)]
    merged = memory._merge_ranges(ranges)
    print(f"Ranges {ranges} merged to {merged}")
    assert len(merged) == 1
    assert merged[0].start == 1
    assert merged[0].end == 10
    
    # Now test through should_read_file
    memory2 = WorkingMemory(current_task="Test")
    memory2.add_recent_file(WorkingMemoryEntry("/test/file.py", "First", "1-5"))
    memory2.add_recent_file(WorkingMemoryEntry("/test/file.py", "Second", "6-10"))
    
    should_read, reason = memory2.should_read_file("/test/file.py", 1, 10)
    print(f"Adjacent ranges 1-5, 6-10, request 1-10: should_read={should_read}")
    # Should be False (fully contained after merging)
    assert should_read is False, f"Lines 1-10 are fully contained after merging. Got: {should_read}"


def test_memory_should_read_file_empty_ranges():
    """Test when _parse_line_ranges returns empty list.
    
    Scenario: lines_read is invalid (e.g., "invalid").
    _parse_line_ranges returns [].
    What should happen?
    """
    memory = WorkingMemory(current_task="Test")
    
    # Can't create WorkingMemoryEntry with invalid lines_read - it validates!
    # So test with empty string
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", ""))
    
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)
    
    print(f"lines_read='', request 10-20: should_read={should_read}, reason={reason}")
    
    # _parse_line_ranges("") returns []
    # valid_ranges is empty
    # After fix: empty lines_read is valid "no lines read", not "invalid format"
    assert should_read is True
    assert "no lines" in reason.lower() or "not read" in reason.lower()


if __name__ == "__main__":
    print("Running actual bug tests...")
    print("=" * 60)
    
    tests = [
        test_memory_should_read_file_merge_bug,
        test_memory_should_read_file_covered_by_multiple,
        test_memory_should_read_file_edge_case_merge,
        test_memory_should_read_file_empty_ranges,
    ]
    
    for test in tests:
        print(f"\n{test.__name__}...")
        try:
            test()
            print("  ✓ PASS")
        except AssertionError as e:
            print(f"  ✗ FAIL: {e}")
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
    
    print("\n" + "=" * 60)
    print("Tests completed.")