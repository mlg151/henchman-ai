"""Test for the bug where key_insights string is not properly handled."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_add_recent_file_with_string_key_insights_bug():
    """Test add_recent_file bug: string key_insights should be split or rejected.
    
    BUG: When entry.key_insights is a string (e.g., "insight1,insight2"),
    add_recent_file wraps it in a list ["insight1,insight2"] instead of
    splitting it into ["insight1", "insight2"].
    
    This violates the type contract that key_insights should be list[str].
    
    FIXED: Now raises TypeError in WorkingMemoryEntry.__post_init__
    """
    memory = WorkingMemory(current_task="Test")
    
    # Create entry with string key_insights (violates type annotation)
    # After fix: Should raise TypeError in WorkingMemoryEntry.__post_init__
    with pytest.raises(TypeError, match="key_insights must be a list or None"):
        entry = WorkingMemoryEntry(
            path="/test/file.py",
            purpose="Test",
            lines_read="full",
            key_insights="insight1,insight2"  # String instead of list[str]
        )


def test_working_memory_entry_validation_bug():
    """Test that WorkingMemoryEntry doesn't validate key_insights type.
    
    BUG: __post_init__ only validates lines_read, not key_insights.
    
    FIXED: Now raises TypeError in __post_init__
    """
    # After fix: Should raise TypeError in __post_init__
    with pytest.raises(TypeError, match="key_insights must be a list or None"):
        entry = WorkingMemoryEntry(
            path="/test/file.py",
            purpose="Test",
            lines_read="full",
            key_insights="not a list"  # String instead of list
        )


def test_add_recent_file_preserves_list_key_insights():
    """Test that add_recent_file correctly handles list key_insights."""
    memory = WorkingMemory(current_task="Test")
    
    # Create entry with proper list key_insights
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="full",
        key_insights=["insight1", "insight2"]  # Correct: list[str]
    )
    
    memory.add_recent_file(entry)
    insights = memory.get_file_insights("/test/file.py")
    
    # Should return the list as-is
    assert insights == ["insight1", "insight2"], (
        f"Expected ['insight1', 'insight2'], got {insights}"
    )


def test_add_recent_file_with_none_key_insights():
    """Test that add_recent_file handles None key_insights."""
    memory = WorkingMemory(current_task="Test")
    
    # Create entry with None key_insights
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="full",
        key_insights=None  # None should become empty list
    )
    
    memory.add_recent_file(entry)
    insights = memory.get_file_insights("/test/file.py")
    
    # Should return empty list
    assert insights == [], f"Expected empty list, got {insights}"


if __name__ == "__main__":
    # Run tests to demonstrate the bug
    import sys
    
    print("Running key_insights bug tests...")
    print("=" * 60)
    
    tests = [
        test_add_recent_file_with_string_key_insights_bug,
        test_working_memory_entry_validation_bug,
        test_add_recent_file_preserves_list_key_insights,
        test_add_recent_file_with_none_key_insights,
    ]
    
    failures = 0
    for test in tests:
        print(f"\nRunning {test.__name__}...")
        try:
            test()
            print("  ✓ PASS (or bug not yet fixed)")
        except AssertionError as e:
            print(f"  ✗ FAIL: {e}")
            failures += 1
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            failures += 1
    
    print(f"\n" + "=" * 60)
    print(f"Total: {len(tests)} tests, {failures} failures")
    
    if failures > 0:
        print("\nBUG CONFIRMED: Tests fail with current implementation.")
    else:
        print("\nAll tests pass (bug may have been fixed).")
    
    sys.exit(1 if failures > 0 else 0)