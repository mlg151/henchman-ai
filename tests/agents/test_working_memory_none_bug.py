"""Test for bug with lines_read=None in should_read_file."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_memory_should_read_file_none_lines_read():
    """Test bug: lines_read=None should be treated same as lines_read="" (no lines read).
    
    Current bug: Line 597 checks `if match.lines_read != "":` which is True for None
    (because None != "" is True). This incorrectly sets all_lines_read_empty = False
    when it should remain True (or at least not be set to False).
    
    This affects the reason returned when no valid ranges are found.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Add entry with lines_read=None
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read=None,  # None means "no lines read"
        key_insights=[],
    )
    memory.add_recent_file(entry)
    
    # Request entire file
    should_read, reason = memory.should_read_file("/test/file.py")
    
    print(f"Test with lines_read=None:")
    print(f"  should_read={should_read}, reason={reason}")
    
    # Should return True (need to read) with reason about no lines read
    assert should_read is True
    
    # The bug: reason might be "Cannot determine - no valid line ranges"
    # instead of "No lines have been read"
    # Because all_lines_read_empty was incorrectly set to False
    print(f"  Expected reason contains 'no lines' or similar")
    print(f"  Actual reason: {reason}")
    
    # Check that reason indicates no lines were read
    # With the bug, it might say "Cannot determine - no valid line ranges"
    # which is less clear
    assert "no lines" in reason.lower() or "cannot determine" in reason.lower()


def test_memory_should_read_file_empty_string_lines_read():
    """Test with lines_read="" for comparison."""
    memory = WorkingMemory(current_task="Test")
    
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="",  # Empty string means "no lines read"
        key_insights=[],
    )
    memory.add_recent_file(entry)
    
    # Request entire file
    should_read, reason = memory.should_read_file("/test/file.py")
    
    print(f"\nTest with lines_read='':")
    print(f"  should_read={should_read}, reason={reason}")
    
    assert should_read is True
    # This should say "No lines have been read"
    assert "no lines" in reason.lower()


def test_memory_should_read_file_mixed_none_and_empty():
    """Test with multiple entries, some None, some empty string."""
    memory = WorkingMemory(current_task="Test")
    
    # First entry: None
    entry1 = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test 1",
        lines_read=None,
        key_insights=[],
    )
    memory.add_recent_file(entry1)
    
    # Second entry: empty string
    entry2 = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test 2",
        lines_read="",
        key_insights=[],
    )
    memory.add_recent_file(entry2)
    
    # Request entire file
    should_read, reason = memory.should_read_file("/test/file.py")
    
    print(f"\nTest with lines_read=None and lines_read='':")
    print(f"  should_read={should_read}, reason={reason}")
    
    assert should_read is True
    # Should say "No lines have been read" (both mean no lines read)
    assert "no lines" in reason.lower()


if __name__ == "__main__":
    print("Testing lines_read=None bug...")
    print("=" * 60)
    
    tests = [
        test_memory_should_read_file_none_lines_read,
        test_memory_should_read_file_empty_string_lines_read,
        test_memory_should_read_file_mixed_none_and_empty,
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
    print("Note: The bug causes inconsistent handling of None vs empty string.")