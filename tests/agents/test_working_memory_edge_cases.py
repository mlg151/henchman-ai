"""Test edge cases in working_memory.py to find bugs."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry, LineRange


def test_merge_ranges_empty_list():
    """Test _merge_ranges with empty list."""
    memory = WorkingMemory(current_task="Test")
    
    ranges = memory._merge_ranges([])
    assert ranges == []
    
    print("✓ _merge_ranges([]) returns []")


def test_merge_ranges_single_range():
    """Test _merge_ranges with single range."""
    memory = WorkingMemory(current_task="Test")
    
    ranges = memory._merge_ranges([LineRange(10, 20)])
    assert ranges == [LineRange(10, 20)]
    
    print("✓ _merge_ranges([LineRange(10, 20)]) returns same")


def test_merge_ranges_unsorted():
    """Test _merge_ranges with unsorted ranges."""
    memory = WorkingMemory(current_task="Test")
    
    # Unsorted: 30-40, 10-20, 25-30
    ranges = memory._merge_ranges([
        LineRange(30, 40),
        LineRange(10, 20),
        LineRange(25, 30),
    ])
    # Should sort and merge: 10-20, 25-30 (adjacent? 20+1=21, 25>21 so not adjacent), 30-40
    # 25-30 and 30-40 overlap at line 30, so merge to 25-40
    # 10-20 and 25-40 are not adjacent (gap at 21-24)
    # So result should be [LineRange(10, 20), LineRange(25, 40)]
    assert ranges == [LineRange(10, 20), LineRange(25, 40)]
    
    print("✓ _merge_ranges sorts and merges correctly")


def test_merge_ranges_fully_overlapping():
    """Test _merge_ranges with fully overlapping ranges."""
    memory = WorkingMemory(current_task="Test")
    
    # 10-30 fully contains 15-25
    ranges = memory._merge_ranges([
        LineRange(10, 30),
        LineRange(15, 25),
    ])
    # Should merge to 10-30
    assert ranges == [LineRange(10, 30)]
    
    print("✓ _merge_ranges merges fully overlapping ranges")


def test_line_range_validation():
    """Test LineRange validation."""
    # Valid range
    r1 = LineRange(1, 10)
    assert r1.start == 1
    assert r1.end == 10
    
    # Invalid: start < 1
    with pytest.raises(ValueError, match="must be positive"):
        LineRange(0, 10)
    
    # Invalid: end < 1
    with pytest.raises(ValueError, match="must be positive"):
        LineRange(1, 0)
    
    # Invalid: start > end
    with pytest.raises(ValueError, match="start.*>.*end"):
        LineRange(10, 1)
    
    print("✓ LineRange validation works correctly")


def test_should_read_file_edge_cases():
    """Test should_read_file with edge cases."""
    memory = WorkingMemory(current_task="Test")
    
    # Test 1: File not in memory at all
    should_read, reason = memory.should_read_file("/nonexistent.py", 1, 10)
    assert should_read is True
    assert "not in recent files" in reason.lower()
    
    # Test 2: File marked as "full"
    entry = WorkingMemoryEntry(
        path="/test.py",
        purpose="Test",
        lines_read="full",
        key_insights=[],
    )
    memory.add_recent_file(entry)
    
    should_read, reason = memory.should_read_file("/test.py", 1, 100)
    assert should_read is False
    assert "already read" in reason.lower()
    
    # Test 3: File with empty lines_read (means no lines read)
    memory2 = WorkingMemory(current_task="Test")
    entry2 = WorkingMemoryEntry(
        path="/test2.py",
        purpose="Test",
        lines_read="",  # Empty string = no lines read
        key_insights=[],
    )
    memory2.add_recent_file(entry2)
    
    should_read, reason = memory2.should_read_file("/test2.py", 1, 10)
    assert should_read is True
    assert "no lines" in reason.lower() or "not read" in reason.lower()
    
    # Test 4: Request lines 1-10 when lines 5-15 have been read
    memory3 = WorkingMemory(current_task="Test")
    entry3 = WorkingMemoryEntry(
        path="/test3.py",
        purpose="Test",
        lines_read="5-15",
        key_insights=[],
    )
    memory3.add_recent_file(entry3)
    
    # Lines 1-4 not read, lines 5-10 read
    should_read, reason = memory3.should_read_file("/test3.py", 1, 10)
    assert should_read is True
    assert "need to be read" in reason.lower() or "overlapping" in reason.lower()
    
    # Test 5: Request lines 10-20 when lines 5-15 have been read
    # Lines 10-15 read, lines 16-20 not read
    should_read, reason = memory3.should_read_file("/test3.py", 10, 20)
    assert should_read is True
    
    print("✓ should_read_file handles edge cases correctly")


def test_parse_line_ranges_edge_cases():
    """Test _parse_line_ranges with edge cases."""
    memory = WorkingMemory(current_task="Test")
    
    # Empty string
    ranges = memory._parse_line_ranges("")
    assert ranges == []
    
    # Whitespace only
    ranges = memory._parse_line_ranges("   ")
    assert ranges == []
    
    # "full" with spaces
    ranges = memory._parse_line_ranges("  full  ")
    assert ranges == []
    
    # Single line
    ranges = memory._parse_line_ranges("42")
    assert ranges == [LineRange(42, 42)]
    
    # Multiple single lines
    ranges = memory._parse_line_ranges("1,2,3")
    assert ranges == [LineRange(1, 1), LineRange(2, 2), LineRange(3, 3)]
    
    # Mixed: ranges and single lines
    ranges = memory._parse_line_ranges("1-10,15,20-25")
    assert ranges == [LineRange(1, 10), LineRange(15, 15), LineRange(20, 25)]
    
    # With invalid parts (should be skipped)
    ranges = memory._parse_line_ranges("1-10,invalid,20-25")
    # "invalid" is skipped
    assert ranges == [LineRange(1, 10), LineRange(20, 25)]
    
    # Unicode dash
    ranges = memory._parse_line_ranges("1\u201310")  # EN DASH
    assert ranges == [LineRange(1, 10)]
    
    print("✓ _parse_line_ranges handles edge cases correctly")


if __name__ == "__main__":
    print("Testing edge cases in working_memory.py")
    print("=" * 60)
    
    test_merge_ranges_empty_list()
    test_merge_ranges_single_range()
    test_merge_ranges_unsorted()
    test_merge_ranges_fully_overlapping()
    test_line_range_validation()
    test_should_read_file_edge_cases()
    test_parse_line_ranges_edge_cases()
    
    print("\n" + "=" * 60)
    print("All edge case tests pass (no bugs found)")