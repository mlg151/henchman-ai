"""Test for algorithm bug in should_read_file coverage checking."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry, LineRange


def test_should_read_file_coverage_algorithm_bug():
    """Test the algorithm for checking if requested range is covered by merged ranges.
    
    The algorithm in should_read_file walks through merged_ranges and checks coverage.
    There's a potential bug when merged_ranges has gaps (non-contiguous ranges).
    """
    memory = WorkingMemory(current_task="Test")
    
    # Add two NON-CONTIGUOUS ranges: 1-50 and 100-150 (gap: 51-99)
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "First read", "1-50"))
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Second read", "100-150"))
    
    # Request lines 1-150 (spans both ranges AND the gap)
    should_read, reason = memory.should_read_file("/test/file.py", 1, 150)
    
    # BUG: The algorithm should return True (need to read) because there's a gap (51-99)
    # But let's see what happens...
    print(f"Test 1 - Non-contiguous ranges (1-50, 100-150), request 1-150:")
    print(f"  should_read={should_read}, reason={reason}")
    
    # The merged_ranges will be [LineRange(1,50), LineRange(100,150)] (NOT merged because gap > 1)
    # Algorithm walks through:
    # - current_line = 1
    # - rng = LineRange(1,50): current_line (1) >= rng.start (1), current_line (1) <= rng.end (50)
    #   -> current_line = 51
    # - rng = LineRange(100,150): current_line (51) < rng.start (100) -> return True (gap found)
    # So it should return True. That's correct!
    
    # Test 2: Request lines 1-50 (fully covered by first range)
    should_read2, reason2 = memory.should_read_file("/test/file.py", 1, 50)
    print(f"\nTest 2 - Non-contiguous ranges (1-50, 100-150), request 1-50:")
    print(f"  should_read={should_read2}, reason={reason2}")
    # Should return False (already read)
    
    # Test 3: Request lines 100-150 (fully covered by second range)
    should_read3, reason3 = memory.should_read_file("/test/file.py", 100, 150)
    print(f"\nTest 3 - Non-contiguous ranges (1-50, 100-150), request 100-150:")
    print(f"  should_read={should_read3}, reason={reason3}")
    # Should return False (already read)
    
    # Test 4: Request lines 60-90 (in the gap)
    should_read4, reason4 = memory.should_read_file("/test/file.py", 60, 90)
    print(f"\nTest 4 - Non-contiguous ranges (1-50, 100-150), request 60-90 (in gap):")
    print(f"  should_read={should_read4}, reason={reason4}")
    # Should return True (need to read)
    
    # Test 5: Request lines 40-110 (overlaps first range, gap, and second range)
    should_read5, reason5 = memory.should_read_file("/test/file.py", 40, 110)
    print(f"\nTest 5 - Non-contiguous ranges (1-50, 100-150), request 40-110 (overlaps all):")
    print(f"  should_read={should_read5}, reason={reason5}")
    # Should return True (need to read gap 51-99 and part of second range 100-110)


def test_should_read_file_adjacent_ranges():
    """Test with adjacent ranges (50-99, 100-150) which should be merged."""
    memory = WorkingMemory(current_task="Test")
    
    # Add two ADJACENT ranges: 50-99 and 100-150 (adjacent: 99+1 = 100)
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "First read", "50-99"))
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Second read", "100-150"))
    
    # _merge_ranges should merge these into LineRange(50, 150)
    # Request lines 50-150
    should_read, reason = memory.should_read_file("/test/file.py", 50, 150)
    
    print(f"\nTest - Adjacent ranges (50-99, 100-150), request 50-150:")
    print(f"  should_read={should_read}, reason={reason}")
    # Should return False (already read, merged into 50-150)


def test_should_read_file_overlapping_ranges():
    """Test with overlapping ranges (1-100, 50-150) which should be merged."""
    memory = WorkingMemory(current_task="Test")
    
    # Add two OVERLAPPING ranges: 1-100 and 50-150
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "First read", "1-100"))
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Second read", "50-150"))
    
    # _merge_ranges should merge these into LineRange(1, 150)
    # Request lines 1-150
    should_read, reason = memory.should_read_file("/test/file.py", 1, 150)
    
    print(f"\nTest - Overlapping ranges (1-100, 50-150), request 1-150:")
    print(f"  should_read={should_read}, reason={reason}")
    # Should return False (already read, merged into 1-150)


def test_should_read_file_single_range_covered():
    """Test simple case: single range covers requested range."""
    memory = WorkingMemory(current_task="Test")
    
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Read", "10-50"))
    
    # Request lines 20-40 (fully contained)
    should_read, reason = memory.should_read_file("/test/file.py", 20, 40)
    
    print(f"\nTest - Single range (10-50), request 20-40 (contained):")
    print(f"  should_read={should_read}, reason={reason}")
    # Should return False (already read)


def test_should_read_file_single_range_not_covered():
    """Test simple case: single range doesn't cover requested range."""
    memory = WorkingMemory(current_task="Test")
    
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Read", "10-50"))
    
    # Request lines 60-80 (not covered)
    should_read, reason = memory.should_read_file("/test/file.py", 60, 80)
    
    print(f"\nTest - Single range (10-50), request 60-80 (not covered):")
    print(f"  should_read={should_read}, reason={reason}")
    # Should return True (need to read)


if __name__ == "__main__":
    print("Testing should_read_file coverage algorithm...")
    print("=" * 60)
    
    test_should_read_file_coverage_algorithm_bug()
    test_should_read_file_adjacent_ranges()
    test_should_read_file_overlapping_ranges()
    test_should_read_file_single_range_covered()
    test_should_read_file_single_range_not_covered()
    
    print("\n" + "=" * 60)
    print("Tests complete. Check if algorithm behaves correctly.")