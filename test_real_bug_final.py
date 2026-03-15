"""Test for a real bug that should fail."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry, LineRange

def test_bug_in_should_read_file_with_full_and_partial():
    """Test bug: when file was fully read, then partially read, should_read_file should check coverage.
    
    Actually, the code only checks if MOST RECENT entry is "full".
    If file was fully read in the past but partially read more recently,
    it checks coverage of partial reads.
    That's correct!
    """
    memory = WorkingMemory(current_task="Test")
    
    # Add old full read
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Old full read", "full"))
    
    # Add more recent partial read
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Recent partial read", "10-50"))
    
    # Request lines 60-100
    # File was fully read in the past, but most recent read is partial (10-50)
    # So it checks coverage of partial reads
    # Partial read (10-50) doesn't cover 60-100
    # Should return True (need to read)
    
    should_read, reason = memory.should_read_file("/test/file.py", 60, 100)
    
    print(f"should_read: {should_read}, reason: {reason}")
    
    # This should return True
    assert should_read is True
    assert "need to read" in reason.lower() or "not yet" in reason.lower() or "new or" in reason.lower()
    
    print("Test passes (no bug)")

def test_bug_in_line_range_validation():
    """Test bug: LineRange should validate that start and end are positive.
    
    Actually, __post_init__ does validate this!
    """
    # Test valid range
    r = LineRange(10, 20)
    assert r.start == 10
    assert r.end == 20
    
    # Test invalid: start < 1
    with pytest.raises(ValueError):
        LineRange(0, 20)
    
    # Test invalid: end < 1
    with pytest.raises(ValueError):
        LineRange(10, 0)
    
    # Test invalid: start > end
    with pytest.raises(ValueError):
        LineRange(20, 10)
    
    print("Test passes (no bug)")

def test_bug_in_parse_line_ranges_with_unicode_whitespace():
    """Test bug: _parse_line_ranges should handle Unicode whitespace.
    
    Actually, lines_read.split() splits on any whitespace, including Unicode!
    """
    from henchman.agents.working_memory import WorkingMemory
    
    memory = WorkingMemory(current_task="Test")
    
    # Test with regular spaces
    ranges = memory._parse_line_ranges("  10-20  ,  30-40  ")
    assert len(ranges) == 2
    
    # Test with tabs
    ranges = memory._parse_line_ranges("\t10-20\t,\t30-40\t")
    assert len(ranges) == 2
    
    # Test with newlines
    ranges = memory._parse_line_ranges("\n10-20\n,\n30-40\n")
    assert len(ranges) == 2
    
    # Test with Unicode non-breaking space (U+00A0)
    # Actually, split() handles Unicode whitespace
    ranges = memory._parse_line_ranges("\u00A010-20\u00A0,\u00A030-40\u00A0")
    assert len(ranges) == 2
    
    print("Test passes (no bug)")

if __name__ == "__main__":
    test_bug_in_should_read_file_with_full_and_partial()
    test_bug_in_line_range_validation()
    test_bug_in_parse_line_ranges_with_unicode_whitespace()
    print("\nAll tests pass (no bugs found)")