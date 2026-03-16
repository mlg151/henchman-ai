"""Test for core bug in should_read_file."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_should_read_file_completely_covered():
    """Test when requested range is completely covered by multiple ranges.
    
    Scenario: File was read 1-10 and 20-30 (non-adjacent).
    Request to read 5-25.
    
    Lines 5-10 are read, 11-19 are NOT read, 20-25 are read.
    So we need to read lines 11-19.
    Should return True.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "First", "1-10"))
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Second", "20-30"))
    
    # Request lines 5-25 (overlaps both, gap in middle)
    should_read, reason = memory.should_read_file("/test/file.py", 5, 25)
    
    print(f"Ranges: 1-10, 20-30")
    print(f"Request: 5-25")
    print(f"Result: should_read={should_read}, reason={reason}")
    
    # Should return True because lines 11-19 are not read
    assert should_read is True
    # Reason should indicate gap or partial coverage


def test_should_read_file_edge_case_at_boundary():
    """Test edge case at boundary.
    
    Scenario: File was read 1-10.
    Request to read 10-20.
    
    Line 10 is read, lines 11-20 are not.
    Should return True.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-10"))
    
    # Request lines 10-20 (10 is already read, 11-20 are not)
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)
    
    print(f"Range: 1-10")
    print(f"Request: 10-20")
    print(f"Result: should_read={should_read}, reason={reason}")
    
    # Should return True because lines 11-20 are not read
    assert should_read is True


def test_should_read_file_single_line():
    """Test single line request.
    
    Scenario: File was read 1-10.
    Request to read line 5.
    
    Line 5 is read.
    Should return False.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-10"))
    
    # Request line 5 (single line, already read)
    should_read, reason = memory.should_read_file("/test/file.py", 5, 5)
    
    print(f"Range: 1-10")
    print(f"Request: 5-5")
    print(f"Result: should_read={should_read}, reason={reason}")
    
    # Should return False because line 5 is read
    assert should_read is False


def test_should_read_file_single_line_not_read():
    """Test single line not read.
    
    Scenario: File was read 1-10.
    Request to read line 15.
    
    Line 15 is not read.
    Should return True.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-10"))
    
    # Request line 15 (single line, not read)
    should_read, reason = memory.should_read_file("/test/file.py", 15, 15)
    
    print(f"Range: 1-10")
    print(f"Request: 15-15")
    print(f"Result: should_read={should_read}, reason={reason}")
    
    # Should return True because line 15 is not read
    assert should_read is True


def test_should_read_file_with_full():
    """Test when file was read fully.
    
    Scenario: File was read fully.
    Request to read any range.
    
    Should return False.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Request any range
    should_read, reason = memory.should_read_file("/test/file.py", 1, 100)
    
    print(f"Range: full")
    print(f"Request: 1-100")
    print(f"Result: should_read={should_read}, reason={reason}")
    
    # Should return False because file was read fully
    assert should_read is False
    assert "already read" in reason.lower() or "full" in reason.lower()


def test_should_read_file_with_full_and_ranges():
    """Test when file was marked as full but also has ranges.
    
    Scenario: lines_read is "full,10-20" (redundant but valid).
    Request to read any range.
    
    Should return False (file was read fully).
    """
    memory = WorkingMemory(current_task="Test")
    # Can't create with "full,10-20" because WorkingMemoryEntry validates
    # But "full" in the string means file was read fully
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Request any range
    should_read, reason = memory.should_read_file("/test/file.py", 1, 100)
    
    print(f"Range: full")
    print(f"Request: 1-100")
    print(f"Result: should_read={should_read}, reason={reason}")
    
    # Should return False because file was read fully
    assert should_read is False


if __name__ == "__main__":
    print("Testing core functionality...")
    print("=" * 60)
    
    tests = [
        test_should_read_file_completely_covered,
        test_should_read_file_edge_case_at_boundary,
        test_should_read_file_single_line,
        test_should_read_file_single_line_not_read,
        test_should_read_file_with_full,
        test_should_read_file_with_full_and_ranges,
    ]
    
    for test in tests:
        print(f"\nRunning {test.__name__}...")
        try:
            test()
            print("  ✓ PASS")
        except AssertionError as e:
            print(f"  ✗ FAIL: {e}")
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
    
    print("\n" + "=" * 60)
    print("Tests complete.")