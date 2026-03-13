#!/usr/bin/env python3
"""Test to find bug in working_memory.py"""

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry, LineRange

def test_scenario_1():
    """Test: file read fully, ask for specific line range."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # File was read fully, any line range should be considered already read
    should_read, reason = memory.should_read_file("/test/file.py", 10, 50)
    print(f"Test 1 - File read fully, ask for lines 10-50:")
    print(f"  should_read: {should_read} (expected: False)")
    print(f"  reason: {reason}")
    assert should_read is False, f"File read fully should return False, got {should_read}"
    print("  PASS")

def test_scenario_2():
    """Test: file read partially, ask without line range."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-50"))
    
    # File was read partially (10-50), asking without line range means "read whole file"
    should_read, reason = memory.should_read_file("/test/file.py")
    print(f"\nTest 2 - File read 10-50, ask without line range (whole file):")
    print(f"  should_read: {should_read} (expected: True)")
    print(f"  reason: {reason}")
    assert should_read is True, f"File partially read, asking for whole file should return True, got {should_read}"
    print("  PASS")

def test_scenario_3():
    """Test: invalid lines_read format, ask without line range."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "invalid-format"))
    
    # Invalid format, can't determine what was read
    should_read, reason = memory.should_read_file("/test/file.py")
    print(f"\nTest 3 - Invalid lines_read format, ask without line range:")
    print(f"  should_read: {should_read} (expected: True)")
    print(f"  reason: {reason}")
    assert should_read is True, f"Invalid format should return True, got {should_read}"
    # Check reason doesn't say "partial read" when it's invalid format
    if "partial read" in reason:
        print(f"  WARNING: Reason says 'partial read' but format is invalid: {reason}")
    print("  PASS")

def test_scenario_4():
    """Test: start provided but end is None."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-100"))
    
    # File read 1-100, ask for lines 50-end (end=None)
    should_read, reason = memory.should_read_file("/test/file.py", 50, None)
    print(f"\nTest 4 - File read 1-100, ask for lines 50-end (end=None):")
    print(f"  should_read: {should_read}")
    print(f"  reason: {reason}")
    # Can't determine containment without knowing file size
    print("  Note: Can't determine if lines 50-∞ are contained in 1-100 without file size")

def test_scenario_5():
    """Test: LineRange.from_str with invalid range (start > end)."""
    result = LineRange.from_str("50-10")
    print(f"\nTest 5 - LineRange.from_str('50-10'):")
    print(f"  result: {result} (expected: None)")
    assert result is None, f"Invalid range 50-10 should return None, got {result}"
    print("  PASS")

def test_scenario_6():
    """Potential bug: what if lines_read is empty string?"""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", ""))
    
    should_read, reason = memory.should_read_file("/test/file.py", 10, 50)
    print(f"\nTest 6 - Empty lines_read string, ask for lines 10-50:")
    print(f"  should_read: {should_read}")
    print(f"  reason: {reason}")
    # Empty string != "full", and LineRange.from_str("") returns None
    # So should return True with "Cannot determine overlap - invalid lines_read format"
    print("  Expected: True, 'Cannot determine overlap - invalid lines_read format'")

def test_scenario_7():
    """Potential bug: what if lines_read is "10-10" (single line)?"""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-10"))
    
    # Ask for same single line
    should_read, reason = memory.should_read_file("/test/file.py", 10, 10)
    print(f"\nTest 7 - File read line 10 only, ask for line 10:")
    print(f"  should_read: {should_read} (expected: False)")
    print(f"  reason: {reason}")
    # LineRange(10,10) from_str should work
    # requested.start >= rng.start and requested.end <= rng.end → 10 >= 10 and 10 <= 10 → True
    assert should_read is False, f"Line 10 already read, should return False, got {should_read}"
    print("  PASS")

if __name__ == "__main__":
    test_scenario_1()
    test_scenario_2()
    test_scenario_3()
    test_scenario_4()
    test_scenario_5()
    test_scenario_6()
    test_scenario_7()
    print("\nAll tests passed!")