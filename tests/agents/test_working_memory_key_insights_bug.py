"""Test for the key_insights string bug in working_memory.py.

BUG: When a WorkingMemoryEntry is created with key_insights as a string
(instead of list[str]), the add_recent_file method converts it to a list
of characters using list(string), which is incorrect.

Example:
  entry = WorkingMemoryEntry(..., key_insights="Important finding")
  memory.add_recent_file(entry)
  # key_insights becomes ['I', 'm', 'p', 'o', 'r', 't', 'a', 'n', 't', ' ', 'f', 'i', 'n', 'd', 'i', 'n', 'g']
  # Should be ["Important finding"] or raise validation error
"""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_key_insights_string_bug():
    """Test that key_insights as string creates incorrect list of characters."""
    # Create entry with string key_insights (type hint says list[str] but Python doesn't enforce)
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="1-10",
        key_insights="Important finding about the file"  # String instead of list!
    )
    
    memory = WorkingMemory(current_task="Test")
    
    # This should fail or handle gracefully
    # Currently: list("Important finding about the file") creates list of chars
    memory.add_recent_file(entry)
    
    # Check what happened
    stored_entry = memory.recent_files[0]
    
    # BUG: key_insights is list of characters, not list with single string
    print(f"key_insights type: {type(stored_entry.key_insights)}")
    print(f"key_insights value: {stored_entry.key_insights}")
    # This is WRONG - should be ["Important finding about the file"]
    # But currently it's ['I', 'm', 'p', 'o', 'r', 't', 'a', 'n', 't', ' ', 'f', 'i', 'n', 'd', 'i', 'n', 'g', ' ', 'a', 'b', 'o', 'u', 't', ' ', 't', 'h', 'e', ' ', 'f', 'i', 'l', 'e']
    
    # The bug: list(string) splits string into characters
    # This assertion expects the buggy behavior:
    # assert stored_entry.key_insights == ['I', 'm', 'p', 'o', 'r', 't', 'a', 'n', 't', ' ', 'f', 'i', 'n', 'd', 'i', 'n', 'g', ' ', 'a', 'b', 'o', 'u', 't', ' ', 't', 'h', 'e', ' ', 'f', 'i', 'l', 'e'], \
    #     f"Expected list of characters due to bug, got {stored_entry.key_insights}"
    
    # What we SHOULD get (if bug fixed):
    assert stored_entry.key_insights == ["Important finding about the file"], \
        f"Expected ['Important finding about the file'], got {stored_entry.key_insights}"
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="1-10",
        key_insights=["Important finding about the file"]  # Correct: list with one string
    )
    
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(entry)
    
    stored_entry = memory.recent_files[0]
    
    # This works correctly
    assert stored_entry.key_insights == ["Important finding about the file"], \
        f"Expected ['Important finding about the file'], got {stored_entry.key_insights}"
    
    print("✓ List key_insights works correctly")


def test_key_insights_none():
    """Test that key_insights as None works correctly."""
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="1-10",
        key_insights=None  # None should become empty list
    )
    
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(entry)
    
    stored_entry = memory.recent_files[0]
    
    # None should become empty list
    assert stored_entry.key_insights == [], \
        f"Expected [], got {stored_entry.key_insights}"
    
    print("✓ None key_insights becomes empty list")


if __name__ == "__main__":
    print("Testing key_insights bug...")
    print("=" * 60)
    
    test_key_insights_string_bug()
    print()
    
    test_key_insights_correct_list()
    print()
    
    test_key_insights_none()
    
    print("=" * 60)
    print("Bug confirmed: string key_insights converted to list of characters")
    print("Fix: In add_recent_file, check if key_insights is string and wrap in list")