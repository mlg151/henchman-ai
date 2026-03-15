"""Test to find a real bug in working_memory.py."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry, LineRange


def test_lines_read_empty_string():
    """Test with empty string as lines_read."""
    memory = WorkingMemory(current_task="Test")
    
    # Add entry with empty lines_read
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="",  # Empty string
        key_insights=[],
    )
    memory.add_recent_file(entry)
    
    # Request lines 10-20
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)
    
    print(f"Test - Empty lines_read string:")
    print(f"  should_read={should_read}, reason={reason}")
    # _parse_line_ranges returns [] for empty string
    # should_read_file returns True with "Cannot determine - invalid lines_read format"
    assert should_read is True
    assert "invalid lines_read format" in reason or "Cannot determine" in reason


def test_lines_read_none():
    """Test with None as lines_read (shouldn't happen but defensive)."""
    memory = WorkingMemory(current_task="Test")
    
    # Can't create WorkingMemoryEntry with lines_read=None because type is str
    # But what if from_dict creates it?
    data = {
        "path": "/test/file.py",
        "purpose": "Test",
        "lines_read": None,  # None instead of string
        "key_insights": [],
        "timestamp": "2024-01-01T00:00:00Z",
    }
    entry = WorkingMemoryEntry.from_dict(data)
    memory.add_recent_file(entry)
    
    # Request lines 10-20
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)
    
    print(f"\nTest - None lines_read (from_dict):")
    print(f"  should_read={should_read}, reason={reason}")
    # _parse_line_ranges returns [] for None
    # should_read_file returns True with "Cannot determine - invalid lines_read format"


def test_lines_read_invalid_format():
    """Test with invalid lines_read format."""
    memory = WorkingMemory(current_task="Test")
    
    # Add entry with invalid format
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="abc-def",  # Not integers
        key_insights=[],
    )
    memory.add_recent_file(entry)
    
    # Request lines 10-20
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)
    
    print(f"\nTest - Invalid lines_read 'abc-def':")
    print(f"  should_read={should_read}, reason={reason}")
    # _parse_line_ranges returns [] (skips invalid)
    # should_read_file returns True with "Cannot determine - invalid lines_read format"


def test_lines_read_negative_numbers():
    """Test with negative line numbers in lines_read."""
    memory = WorkingMemory(current_task="Test")
    
    # Add entry with negative line numbers
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="-10--5",  # Negative numbers
        key_insights=[],
    )
    memory.add_recent_file(entry)
    
    # Request lines 10-20
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)
    
    print(f"\nTest - Negative line numbers '-10--5':")
    print(f"  should_read={should_read}, reason={reason}")
    # _parse_line_ranges skips negative numbers (start < 1 or end < 1)
    # Returns []
    # should_read_file returns True with "Cannot determine - invalid lines_read format"


def test_lines_read_zero():
    """Test with zero line numbers (invalid, 1-indexed)."""
    memory = WorkingMemory(current_task="Test")
    
    # Add entry with zero line numbers
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="0-10",  # start=0 (invalid)
        key_insights=[],
    )
    memory.add_recent_file(entry)
    
    # Request lines 10-20
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)
    
    print(f"\nTest - Zero start line '0-10':")
    print(f"  should_read={should_read}, reason={reason}")
    # _parse_line_ranges skips (start < 1)
    # Returns []
    # should_read_file returns True with "Cannot determine - invalid lines_read format"


def test_lines_read_start_greater_than_end():
    """Test with start > end (invalid range)."""
    memory = WorkingMemory(current_task="Test")
    
    # Add entry with invalid range (start > end)
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="50-10",  # 50 > 10
        key_insights=[],
    )
    memory.add_recent_file(entry)
    
    # Request lines 10-20
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)
    
    print(f"\nTest - Invalid range '50-10' (start > end):")
    print(f"  should_read={should_read}, reason={reason}")
    # _parse_line_ranges skips (start > end)
    # Returns []
    # should_read_file returns True with "Cannot determine - invalid lines_read format"


def test_multiple_entries_mixed_valid_invalid():
    """Test with multiple entries, some valid, some invalid."""
    memory = WorkingMemory(current_task="Test")
    
    # Add invalid entry first
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Invalid read",
        lines_read="abc-def",  # Invalid
    ))
    
    # Add valid entry second (more recent)
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Valid read",
        lines_read="10-50",  # Valid
    ))
    
    # Request lines 20-40 (within valid range)
    should_read, reason = memory.should_read_file("/test/file.py", 20, 40)
    
    print(f"\nTest - Mixed valid/invalid entries:")
    print(f"  should_read={should_read}, reason={reason}")
    # Should return False (lines 20-40 are within 10-50)
    # The invalid entry should be ignored


def test_unicode_dash_characters():
    """Test with Unicode dash characters in lines_read."""
    memory = WorkingMemory(current_task="Test")
    
    # Test with en dash (U+2013)
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="10–50",  # en dash
        key_insights=[],
    )
    memory.add_recent_file(entry)
    
    # Request lines 20-40
    should_read, reason = memory.should_read_file("/test/file.py", 20, 40)
    
    print(f"\nTest - Unicode en dash '10–50':")
    print(f"  should_read={should_read}, reason={reason}")
    # _parse_line_ranges should parse Unicode dash
    # Should return False (20-40 within 10-50)


if __name__ == "__main__":
    print("Testing edge cases in working_memory.py...")
    print("=" * 60)
    
    test_lines_read_empty_string()
    test_lines_read_none()
    test_lines_read_invalid_format()
    test_lines_read_negative_numbers()
    test_lines_read_zero()
    test_lines_read_start_greater_than_end()
    test_multiple_entries_mixed_valid_invalid()
    test_unicode_dash_characters()
    
    print("\n" + "=" * 60)
    print("Tests complete.")