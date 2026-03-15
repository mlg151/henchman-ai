"""Test for the key_insights=None bug in working_memory.py."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_memory_add_recent_file_with_none_key_insights():
    """Test add_recent_file bug when key_insights is None.
    
    BUG: In add_recent_file method, line 177:
        key_insights=list(entry.key_insights)
    
    This will fail with TypeError if entry.key_insights is None.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Create entry with key_insights=None (possible despite type hints)
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="1-10",
        key_insights=None,  # This is allowed at runtime despite type hints
    )
    
    # This should handle None gracefully, not crash
    try:
        memory.add_recent_file(entry)
        # If we get here, the bug might be fixed or entry wasn't created with None
        print("add_recent_file succeeded (bug may be fixed)")
    except TypeError as e:
        if "'NoneType' object is not iterable" in str(e):
            print(f"BUG CONFIRMED: TypeError: {e}")
            raise
        else:
            raise
    
    # Also test with empty list (should work)
    entry2 = WorkingMemoryEntry(
        path="/test/file2.py",
        purpose="Test",
        lines_read="1-10",
        key_insights=[],  # Empty list
    )
    memory.add_recent_file(entry2)
    print("Empty list works fine")
    
    # Test with actual insights
    entry3 = WorkingMemoryEntry(
        path="/test/file3.py",
        purpose="Test",
        lines_read="1-10",
        key_insights=["Important insight"],
    )
    memory.add_recent_file(entry3)
    print("List with items works fine")


def test_memory_working_memory_entry_default():
    """Test that WorkingMemoryEntry defaults key_insights to empty list."""
    # Default entry should have empty list, not None
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="1-10",
        # key_insights not specified, should use default_factory=list
    )
    assert entry.key_insights == [], f"Expected empty list, got {entry.key_insights}"
    assert isinstance(entry.key_insights, list), f"Expected list, got {type(entry.key_insights)}"
    
    # Explicitly set to empty list
    entry2 = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="1-10",
        key_insights=[],
    )
    assert entry2.key_insights == []
    
    # The bug is when someone explicitly passes None
    # This is possible despite type hints
    import dataclasses
    
    # We can create the entry with None using dataclasses.replace
    entry3 = dataclasses.replace(entry, key_insights=None)
    assert entry3.key_insights is None, f"Expected None, got {entry3.key_insights}"
    
    # Or by creating a new instance directly (bypassing type checking)
    entry4 = WorkingMemoryEntry.__new__(WorkingMemoryEntry)
    entry4.path = "/test/file.py"
    entry4.purpose = "Test"
    entry4.lines_read = "1-10"
    entry4.key_insights = None
    entry4.timestamp = "2024-01-01T00:00:00Z"
    
    assert entry4.key_insights is None
    print("Created entry with key_insights=None (possible at runtime)")


if __name__ == "__main__":
    # Run tests
    import sys
    
    print("Testing key_insights=None bug...")
    print("=" * 60)
    
    tests = [
        test_memory_add_recent_file_with_none_key_insights,
        test_memory_working_memory_entry_default,
    ]
    
    failures = 0
    for test in tests:
        print(f"\nRunning {test.__name__}...")
        try:
            test()
            print("  ✓ PASS")
        except AssertionError as e:
            print(f"  ✗ FAIL: {e}")
            failures += 1
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            failures += 1
    
    print(f"\n" + "=" * 60)
    print(f"Total: {len(tests)} tests, {failures} failures")
    
    if failures > 0:
        print("\nBUG CONFIRMED: add_recent_file doesn't handle key_insights=None.")
    else:
        print("\nAll tests pass (bug may have been fixed).")
    
    sys.exit(1 if failures > 0 else 0)