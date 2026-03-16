"""Test for bug: lines_read=None vs lines_read="" should be treated identically."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_lines_read_none_vs_empty_consistency():
    """Test that lines_read=None and lines_read="" give same reason.
    
    BUG: lines_read=None returns "Cannot determine - no valid line ranges"
    while lines_read="" returns "No lines have been read".
    They should both return "No lines have been read".
    """
    # Test with lines_read=None
    memory1 = WorkingMemory(current_task="Test")
    entry1 = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read=None,
        key_insights=[],
    )
    memory1.add_recent_file(entry1)
    should_read1, reason1 = memory1.should_read_file("/test/file.py")
    
    # Test with lines_read=""
    memory2 = WorkingMemory(current_task="Test")
    entry2 = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="",
        key_insights=[],
    )
    memory2.add_recent_file(entry2)
    should_read2, reason2 = memory2.should_read_file("/test/file.py")
    
    print(f"lines_read=None:  should_read={should_read1}, reason='{reason1}'")
    print(f"lines_read='':    should_read={should_read2}, reason='{reason2}'")
    
    # Both should return True (need to read)
    assert should_read1 is True
    assert should_read2 is True
    
    # BUG: reasons are different!
    # lines_read=None: "Cannot determine - no valid line ranges"
    # lines_read="": "No lines have been read"
    # They should be the same!
    
    # This test will FAIL with current code
    assert reason1 == reason2, f"Reasons should be identical: None='{reason1}' vs ''='{reason2}'"
    
    # Additionally, both should say "No lines have been read"
    assert "no lines have been read" in reason1.lower()
    assert "no lines have been read" in reason2.lower()


def test_lines_read_none_reason():
    """Test specifically that lines_read=None gives correct reason."""
    memory = WorkingMemory(current_task="Test")
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read=None,
        key_insights=[],
    )
    memory.add_recent_file(entry)
    
    should_read, reason = memory.should_read_file("/test/file.py")
    
    print(f"\nlines_read=None reason check:")
    print(f"  Actual reason: '{reason}'")
    print(f"  Should contain: 'no lines have been read'")
    
    # BUG: This will fail with current code
    # Actual: "Cannot determine - no valid line ranges"
    # Expected: "No lines have been read"
    assert "no lines have been read" in reason.lower(), (
        f"lines_read=None should give reason 'No lines have been read', got '{reason}'"
    )


def test_lines_read_empty_reason():
    """Test that lines_read="" gives correct reason (baseline)."""
    memory = WorkingMemory(current_task="Test")
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="",
        key_insights=[],
    )
    memory.add_recent_file(entry)
    
    should_read, reason = memory.should_read_file("/test/file.py")
    
    print(f"\nlines_read='' reason check:")
    print(f"  Actual reason: '{reason}'")
    print(f"  Should contain: 'no lines have been read'")
    
    # This should pass with current code
    assert "no lines have been read" in reason.lower(), (
        f"lines_read='' should give reason 'No lines have been read', got '{reason}'"
    )


if __name__ == "__main__":
    print("Testing lines_read=None vs lines_read='' consistency bug...")
    print("=" * 60)
    
    try:
        test_lines_read_none_vs_empty_consistency()
        print("✓ Test 1 passed")
    except AssertionError as e:
        print(f"✗ Test 1 failed (expected): {e}")
    
    try:
        test_lines_read_none_reason()
        print("✓ Test 2 passed")
    except AssertionError as e:
        print(f"✗ Test 2 failed (expected): {e}")
    
    try:
        test_lines_read_empty_reason()
        print("✓ Test 3 passed")
    except AssertionError as e:
        print(f"✗ Test 3 failed (unexpected): {e}")
    
    print("\n" + "=" * 60)
    print("Bug confirmed: lines_read=None and lines_read='' give different reasons.")