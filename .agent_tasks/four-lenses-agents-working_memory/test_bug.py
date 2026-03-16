"""Test for bug in working_memory.py"""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry, LineRange


def test_should_read_file_bug():
    """Test a potential bug in should_read_file."""
    memory = WorkingMemory(current_task="Test")
    
    # Add entry: file was read lines 10-50
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="10-50"
    ))
    
    # Test 1: Request lines 1-100 (should return True - need lines 1-9 and 51-100)
    should_read, reason = memory.should_read_file("/test/file.py", 1, 100)
    assert should_read is True, f"Expected True for lines 1-100, got {should_read}. Reason: {reason}"
    
    # Test 2: Request lines 20-40 (should return False - fully contained in 10-50)
    should_read, reason = memory.should_read_file("/test/file.py", 20, 40)
    assert should_read is False, f"Expected False for lines 20-40, got {should_read}. Reason: {reason}"
    
    # Test 3: Request lines 5-15 (partially before - should return True)
    should_read, reason = memory.should_read_file("/test/file.py", 5, 15)
    assert should_read is True, f"Expected True for lines 5-15, got {should_read}. Reason: {reason}"
    
    # Test 4: Request lines 45-60 (partially after - should return True)
    should_read, reason = memory.should_read_file("/test/file.py", 45, 60)
    assert should_read is True, f"Expected True for lines 45-60, got {should_read}. Reason: {reason}"
    
    # Test 5: Request lines 60-70 (completely after - should return True)
    should_read, reason = memory.should_read_file("/test/file.py", 60, 70)
    assert should_read is True, f"Expected True for lines 60-70, got {should_read}. Reason: {reason}"
    
    # Test 6: Request with start only (start=30, end=None: read from 30 to EOF)
    should_read, reason = memory.should_read_file("/test/file.py", start=30)
    assert should_read is True, f"Expected True for start=30, got {should_read}. Reason: {reason}"
    # Should say "May need to read lines beyond 50"
    
    # Test 7: Request with end only (start=None, end=40: read from beginning to 40)
    should_read, reason = memory.should_read_file("/test/file.py", end=40)
    assert should_read is True, f"Expected True for end=40, got {should_read}. Reason: {reason}"
    # Should say "May need to read lines before 10"
    
    print("All tests passed!")


def test_merge_ranges_bug():
    """Test _merge_ranges method."""
    memory = WorkingMemory(current_task="Test")
    
    # Test merging overlapping ranges
    ranges = [
        LineRange(10, 20),
        LineRange(15, 25),  # Overlaps with 10-20
        LineRange(30, 40),
        LineRange(35, 45),  # Overlaps with 30-40
    ]
    
    merged = memory._merge_ranges(ranges)
    print(f"Merged ranges: {[(r.start, r.end) for r in merged]}")
    
    # Should be: 10-25, 30-45
    assert len(merged) == 2
    assert merged[0].start == 10 and merged[0].end == 25
    assert merged[1].start == 30 and merged[1].end == 45
    
    # Test merging adjacent ranges (20-30 and 31-40 should merge)
    ranges2 = [
        LineRange(20, 30),
        LineRange(31, 40),  # Adjacent to 20-30
    ]
    
    merged2 = memory._merge_ranges(ranges2)
    print(f"Merged adjacent ranges: {[(r.start, r.end) for r in merged2]}")
    
    # Should be: 20-40
    assert len(merged2) == 1
    assert merged2[0].start == 20 and merged2[0].end == 40
    
    print("Merge tests passed!")


def test_parse_line_ranges_bug():
    """Test _parse_line_ranges method."""
    memory = WorkingMemory(current_task="Test")
    
    # Test valid formats
    test_cases = [
        ("full", []),
        ("10-20", [LineRange(10, 20)]),
        ("10-20,30-40", [LineRange(10, 20), LineRange(30, 40)]),
        ("10", [LineRange(10, 10)]),
        ("10,20,30", [LineRange(10, 10), LineRange(20, 20), LineRange(30, 30)]),
        ("", []),  # Empty string
    ]
    
    for input_str, expected in test_cases:
        result = memory._parse_line_ranges(input_str)
        print(f"'{input_str}' -> {[(r.start, r.end) for r in result]}")
        assert len(result) == len(expected)
        for r1, r2 in zip(result, expected):
            assert r1.start == r2.start and r1.end == r2.end
    
    # Test invalid formats (should return empty list or skip invalid parts)
    invalid_cases = [
        "invalid",
        "10-20,invalid",
        "10-20,30-40,invalid",
    ]
    
    for input_str in invalid_cases:
        result = memory._parse_line_ranges(input_str)
        print(f"'{input_str}' -> {[(r.start, r.end) for r in result]}")
        # Should parse valid parts and skip invalid
    
    print("Parse tests passed!")


if __name__ == "__main__":
    test_should_read_file_bug()
    test_merge_ranges_bug()
    test_parse_line_ranges_bug()
    print("\nAll tests passed!")