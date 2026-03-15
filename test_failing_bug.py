"""Failing test for the bug - to be added to test_working_memory.py"""
import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

def test_memory_should_read_file_invalid_lines_read_consistent_error():
    """Test that invalid lines_read returns consistent error message for entire file requests.
    
    BUG: When lines_read is invalid (None, empty string, malformed) and start=None, end=None
    (read entire file), should_read_file returns misleading "File not fully read - partial read recorded"
    instead of accurate "Cannot determine - invalid lines_read format".
    
    For partial/specific range requests, it correctly returns the accurate error message.
    This test should FAIL with the current implementation.
    """
    # Test with lines_read=None (simulating YAML null)
    memory = WorkingMemory(current_task="Test")
    
    # Create entry with lines_read=None
    entry_dict = {
        "path": "/test/file.py",
        "purpose": "Test",
        "lines_read": None,
        "key_insights": [],
        "timestamp": "2024-01-01T00:00:00Z"
    }
    entry = WorkingMemoryEntry.from_dict(entry_dict)
    memory.add_recent_file(entry)
    
    # Test 1: Read entire file (start=None, end=None)
    # BUG: Returns "File not fully read - partial read recorded"
    should_read1, reason1 = memory.should_read_file("/test/file.py")
    assert should_read1 is True
    # This assertion should FAIL with current implementation
    assert "invalid lines_read format" in reason1.lower() or "cannot determine" in reason1.lower(), (
        f"Entire file request with invalid lines_read should report 'invalid lines_read format', "
        f"not '{reason1}'. BUG: returns misleading 'File not fully read - partial read recorded'."
    )
    
    # Test 2: Read partial range (start=10, end=None) - already works correctly
    should_read2, reason2 = memory.should_read_file("/test/file.py", start=10)
    assert should_read2 is True
    assert "invalid lines_read format" in reason2.lower() or "cannot determine" in reason2.lower()
    
    # Test 3: Read specific range (start=10, end=20) - already works correctly
    should_read3, reason3 = memory.should_read_file("/test/file.py", 10, 20)
    assert should_read3 is True
    assert "invalid lines_read format" in reason3.lower() or "cannot determine" in reason3.lower()

def test_memory_should_read_file_empty_string_lines_read():
    """Test with empty string lines_read."""
    memory = WorkingMemory(current_task="Test")
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="",  # Empty string
    )
    memory.add_recent_file(entry)
    
    should_read, reason = memory.should_read_file("/test/file.py")
    assert should_read is True
    # This should also fail with current implementation
    assert "invalid lines_read format" in reason.lower() or "cannot determine" in reason.lower(), (
        f"Empty lines_read should report 'invalid lines_read format', got: '{reason}'"
    )

def test_memory_should_read_file_invalid_format_lines_read():
    """Test with invalid format lines_read."""
    memory = WorkingMemory(current_task="Test")
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="invalid-format",  # Invalid format
    )
    memory.add_recent_file(entry)
    
    should_read, reason = memory.should_read_file("/test/file.py")
    assert should_read is True
    # This should also fail with current implementation
    assert "invalid lines_read format" in reason.lower() or "cannot determine" in reason.lower(), (
        f"Invalid format lines_read should report 'invalid lines_read format', got: '{reason}'"
    )

if __name__ == "__main__":
    # Run the tests
    import sys
    failures = 0
    
    tests = [
        test_memory_should_read_file_invalid_lines_read_consistent_error,
        test_memory_should_read_file_empty_string_lines_read,
        test_memory_should_read_file_invalid_format_lines_read,
    ]
    
    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__} passed")
        except AssertionError as e:
            print(f"✗ {test.__name__} FAILED (as expected): {e}")
            failures += 1
    
    if failures == len(tests):
        print(f"\nAll {len(tests)} tests failed as expected. Bug confirmed!")
        sys.exit(0)  # Success - tests correctly demonstrate the bug
    else:
        print(f"\nERROR: {len(tests) - failures} tests passed unexpectedly!")
        sys.exit(1)