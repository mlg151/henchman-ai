"""Test for inconsistent error message bug in should_read_file."""
import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

def test_should_read_file_invalid_lines_read_consistent_error():
    """Test that invalid lines_read returns consistent error message.
    
    BUG: When lines_read is invalid (e.g., None, empty string, "invalid") and
    start=None, end=None (read entire file), should_read_file returns misleading
    "File not fully read - partial read recorded" instead of accurate
    "Cannot determine - invalid lines_read format".
    
    For partial range requests (start=X or end=Y), it correctly returns the
    accurate error message.
    """
    # Test with lines_read=None
    memory = WorkingMemory(current_task="Test")
    
    # Create entry with lines_read=None (simulating YAML null)
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
    # Should return "Cannot determine - invalid lines_read format"
    should_read1, reason1 = memory.should_read_file("/test/file.py")
    print(f"Test 1 - Entire file: should_read={should_read1}, reason='{reason1}'")
    
    # Test 2: Read partial range (start=10, end=None)
    # Correctly returns "Cannot determine - invalid lines_read format"
    should_read2, reason2 = memory.should_read_file("/test/file.py", start=10)
    print(f"Test 2 - Partial range (start=10): should_read={should_read2}, reason='{reason2}'")
    
    # Test 3: Read specific range (start=10, end=20)
    # Correctly returns "Cannot determine - invalid lines_read format"
    should_read3, reason3 = memory.should_read_file("/test/file.py", 10, 20)
    print(f"Test 3 - Specific range (10-20): should_read={should_read3}, reason='{reason3}'")
    
    # Assertions
    assert should_read1 is True, "Should read when lines_read is invalid"
    assert should_read2 is True, "Should read when lines_read is invalid"
    assert should_read3 is True, "Should read when lines_read is invalid"
    
    # BUG: reason1 is wrong, reason2 and reason3 are correct
    # The test should fail because reason1 != "Cannot determine - invalid lines_read format"
    assert "invalid lines_read format" in reason1.lower(), (
        f"Entire file request should report 'invalid lines_read format', got: '{reason1}'"
    )
    assert "invalid lines_read format" in reason2.lower(), (
        f"Partial range should report 'invalid lines_read format', got: '{reason2}'"
    )
    assert "invalid lines_read format" in reason3.lower(), (
        f"Specific range should report 'invalid lines_read format', got: '{reason3}'"
    )

def test_should_read_file_empty_string_lines_read():
    """Test with empty string lines_read."""
    memory = WorkingMemory(current_task="Test")
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="",  # Empty string
    )
    memory.add_recent_file(entry)
    
    # Entire file request
    should_read1, reason1 = memory.should_read_file("/test/file.py")
    print(f"Empty string - Entire file: should_read={should_read1}, reason='{reason1}'")
    
    # Should return "Cannot determine - invalid lines_read format" or similar
    # Not "File not fully read - partial read recorded"
    assert should_read1 is True
    assert "invalid lines_read format" in reason1.lower() or "cannot determine" in reason1.lower(), (
        f"Should report invalid lines_read, got: '{reason1}'"
    )

def test_should_read_file_invalid_format_lines_read():
    """Test with invalid format lines_read."""
    memory = WorkingMemory(current_task="Test")
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="invalid-format",  # Invalid format
    )
    memory.add_recent_file(entry)
    
    # Entire file request
    should_read1, reason1 = memory.should_read_file("/test/file.py")
    print(f"Invalid format - Entire file: should_read={should_read1}, reason='{reason1}'")
    
    assert should_read1 is True
    assert "invalid lines_read format" in reason1.lower() or "cannot determine" in reason1.lower(), (
        f"Should report invalid lines_read, got: '{reason1}'"
    )

if __name__ == "__main__":
    print("Running tests...")
    try:
        test_should_read_file_invalid_lines_read_consistent_error()
        print("\nTest 1 FAILED (should have failed but didn't)")
    except AssertionError as e:
        print(f"\nTest 1 correctly failed: {e}")
    
    print("\n" + "="*60 + "\n")
    
    try:
        test_should_read_file_empty_string_lines_read()
        print("Test 2 passed")
    except AssertionError as e:
        print(f"Test 2 failed: {e}")
    
    print("\n" + "="*60 + "\n")
    
    try:
        test_should_read_file_invalid_format_lines_read()
        print("Test 3 passed")
    except AssertionError as e:
        print(f"Test 3 failed: {e}")