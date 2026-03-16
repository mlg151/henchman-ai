"""Test for actual core bug in working_memory.py."""

import pytest

from henchman.agents.working_memory import (
    LineRange,
    WorkingMemory,
    WorkingMemoryEntry,
)


def test_should_read_file_bool_input_bug():
    """Test actual bug: bool values should be rejected as line numbers.
    
    BUG: In should_read_file, line 527: `if type(start) is not int:` 
    This correctly rejects bool because bool is a subclass of int in Python.
    But let me test if this actually works.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Test with bool True (which is subclass of int)
    should_read, reason = memory.should_read_file("/test/file.py", True, 10)
    assert should_read is True
    assert "must be an integer" in reason or "invalid" in reason
    
    # Test with bool False
    should_read, reason = memory.should_read_file("/test/file.py", False, 10)
    assert should_read is True
    assert "must be an integer" in reason or "invalid" in reason
    
    # Test with bool as end
    should_read, reason = memory.should_read_file("/test/file.py", 1, True)
    assert should_read is True
    assert "must be an integer" in reason or "invalid" in reason


def test_should_read_file_none_handling_bug():
    """Test bug with None handling in validation.
    
    BUG: The check at line 549: `if start is not None and end is not None and end != -1 and start > end:`
    What if end is None (converted from -1)? Then end != -1 is True (None != -1), 
    but end is not None is False, so condition is False. That's correct.
    
    But what if someone passes end=None directly? Line 534: `if end is not None:` 
    skips validation for None. That's correct because None means "no end specified".
    
    Actually, the real bug might be elsewhere. Let me test something else.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Test with end=None (valid: means "read to EOF")
    # File doesn't exist in recent files, so should return "File not in recent files"
    should_read, reason = memory.should_read_file("/test/file.py", 1, None)
    assert should_read is True
    assert "File not in recent files" in reason
    
    # Now test with a file in recent files
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-50"))
    
    # Test with start=1, end=None (read from line 1 to EOF)
    # We've read lines 1-50, but don't know about lines beyond 50
    should_read, reason = memory.should_read_file("/test/file.py", 1, None)
    assert should_read is True
    # Should say something like "May need to read lines beyond 50"
    assert "beyond" in reason.lower() or "may need" in reason.lower()
    
    # Test with start=None, end=10 (read from beginning to line 10)
    # We've read lines 1-50, which includes 1-10
    should_read, reason = memory.should_read_file("/test/file.py", end=10)
    assert should_read is True
    # Should say something like "May need to read lines before 1" or similar
    # Actually, we've read line 1, so it's covered...
    # The logic is complex, but at least it shouldn't crash


def test_line_range_overlaps_edge_case_bug():
    """Test edge case bug in LineRange.overlaps().
    
    BUG: LineRange(1, 10).overlaps(LineRange(10, 20)) returns True
    because start <= other.end (1 <= 20) and end >= other.start (10 >= 10).
    This is correct: they overlap at line 10.
    """
    r1 = LineRange(1, 10)
    r2 = LineRange(10, 20)
    assert r1.overlaps(r2) is True  # They touch at line 10
    
    r3 = LineRange(1, 9)
    r4 = LineRange(10, 20)
    assert r3.overlaps(r4) is False  # No overlap, line 9 and 10 are adjacent but not overlapping
    
    # Test with single line ranges
    r5 = LineRange(5, 5)
    r6 = LineRange(5, 5)
    assert r5.overlaps(r6) is True
    
    r7 = LineRange(5, 5)
    r8 = LineRange(6, 6)
    assert r7.overlaps(r8) is False


def test_merge_ranges_adjacent_bug():
    """Test bug in _merge_ranges with adjacent ranges.
    
    BUG: _merge_ranges merges adjacent ranges (end+1 >= start).
    LineRange(1, 10) and LineRange(11, 20) are adjacent (10+1 = 11).
    Should they be merged? Current code merges them.
    """
    from henchman.agents.working_memory import WorkingMemory
    
    ranges = [LineRange(1, 10), LineRange(11, 20)]
    merged = WorkingMemory._merge_ranges(ranges)
    # Should merge into LineRange(1, 20)
    assert len(merged) == 1
    assert merged[0] == LineRange(1, 20)
    
    # Test with gap
    ranges2 = [LineRange(1, 10), LineRange(12, 20)]  # Gap at line 11
    merged2 = WorkingMemory._merge_ranges(ranges2)
    # Should NOT merge, should keep as two ranges
    assert len(merged2) == 2
    assert merged2[0] == LineRange(1, 10)
    assert merged2[1] == LineRange(12, 20)


def test_real_core_bug_should_read_file_with_invalid_lines_read():
    """Test that bug is FIXED: should_read_file now handles invalid lines_read consistently.
    
    BUG WAS: When lines_read contains invalid format (e.g., "10-20,invalid,30-40"),
    _parse_line_ranges skips invalid parts and returns [LineRange(10,20), LineRange(30,40)].
    But _validate_lines_read (called in WorkingMemoryEntry.__post_init__) raised ValueError
    for invalid format.
    
    This inconsistency caused deserialization to fail for saved working memory
    with invalid lines_read format.
    
    FIX: _validate_lines_read now accepts strings with invalid parts as long as
    there's at least one valid part (consistent with _parse_line_ranges).
    """
    # Test that creating entry with invalid lines_read but valid parts now works
    entry = WorkingMemoryEntry("/test/file.py", "Test", "10-20,invalid,30-40")
    assert entry.path == "/test/file.py"
    assert entry.lines_read == "10-20,invalid,30-40"
    
    # _parse_line_ranges handles it gracefully
    from henchman.agents.working_memory import WorkingMemory
    ranges = WorkingMemory._parse_line_ranges("10-20,invalid,30-40")
    assert len(ranges) == 2
    assert ranges[0] == LineRange(10, 20)
    assert ranges[1] == LineRange(30, 40)
    
    # Now validation and parsing are consistent!
    # Both accept strings with invalid parts as long as there's at least one valid part
    # This fixes the deserialization bug
    
    # Test that completely invalid string still raises ValueError
    with pytest.raises(ValueError, match="Invalid lines_read"):
        WorkingMemoryEntry("/test/file.py", "Test", "invalid,also-invalid")