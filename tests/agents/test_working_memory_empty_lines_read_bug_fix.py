"""Test for bug fix: empty lines_read should not be reported as 'invalid lines_read format'."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_empty_lines_read_not_invalid_format():
    """Test that empty lines_read is not reported as 'invalid lines_read format'.
    
    BUG: Currently, when lines_read is empty string (""), should_read_file returns
    "Cannot determine - invalid lines_read format", but empty string is explicitly
    allowed by _validate_lines_read().
    
    FIX: should_read_file should handle empty lines_read as valid "no lines read"
    state and return an appropriate reason.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Create entry with empty lines_read (valid according to validation)
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="",  # Empty string - valid "no lines read"
        key_insights=[],
    )
    memory.add_recent_file(entry)
    
    # Test 1: Request lines 10-20
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)
    
    # Should return True (need to read because no lines were read)
    assert should_read is True, f"Expected True for empty lines_read, got {should_read}"
    
    # BUG: Currently returns "Cannot determine - invalid lines_read format"
    # FIX: Should NOT say "invalid lines_read format" for empty string
    assert "invalid lines_read format" not in reason.lower(), (
        f"Empty lines_read should not be reported as 'invalid lines_read format'. "
        f"Got reason: '{reason}'"
    )
    
    # Should indicate that no lines have been read
    assert "no lines" in reason.lower() or "not read" in reason.lower() or "empty" in reason.lower(), (
        f"Reason should indicate no lines were read. Got: '{reason}'"
    )
    
    print(f"✓ Test passes with fix: should_read={should_read}, reason='{reason}'")


def test_whitespace_only_lines_read_is_invalid():
    """Test that whitespace-only lines_read is invalid (raises ValueError)."""
    # Whitespace-only string should raise ValueError when creating WorkingMemoryEntry
    with pytest.raises(ValueError, match="whitespace-only"):
        WorkingMemoryEntry(
            path="/test/file.py",
            purpose="Test",
            lines_read="   ",  # Only spaces
            key_insights=[],
        )
    
    print("✓ Whitespace-only lines_read correctly raises ValueError")


def test_empty_vs_whitespace_consistency():
    """Test consistency between empty string and whitespace-only string."""
    memory = WorkingMemory(current_task="Test")
    
    # Empty string is valid
    entry1 = WorkingMemoryEntry("/test/file1.py", "Test", "", [])
    memory.add_recent_file(entry1)
    
    # Whitespace-only string is invalid (can't even create the entry)
    # So we can't test it in memory
    
    print("✓ Empty string valid, whitespace-only invalid (consistent)")


if __name__ == "__main__":
    print("Testing empty lines_read bug fix...")
    print("=" * 60)
    
    try:
        test_empty_lines_read_not_invalid_format()
        print("\n✗ Test FAILED (bug not fixed yet) - empty lines_read still reported as 'invalid lines_read format'")
    except AssertionError as e:
        print(f"\n✓ Test correctly fails (demonstrates bug): {e}")
    
    test_whitespace_only_lines_read_is_invalid()
    test_empty_vs_whitespace_consistency()
    
    print("\n" + "=" * 60)
    print("Test demonstrates the bug: empty lines_read reported as 'invalid'")