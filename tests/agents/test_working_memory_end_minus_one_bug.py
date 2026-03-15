"""Test for the real bug: should_read_file incorrectly rejects end=-1.

This is the "Unit of Doom" test that FAILS on the original code
and should PASS after the fix.
"""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_memory_should_read_file_end_minus_one_bug():
    """Test should_read_file bug: end=-1 should be valid (means "read to end of file").
    
    BUG: The validation in should_read_file rejects end=-1 with "Invalid line number: 
    end must be positive (1-indexed), got end=-1", but end=-1 is a valid special value
    that means "read to end of file" in the read_file tool.
    
    This test demonstrates the bug - it should FAIL on the original code.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="1-50"
    ))
    
    # Test with end=-1 (should be valid!)
    should_read, reason = memory.should_read_file("/test/file.py", 60, -1)
    
    # The bug: should_read_file returns True with error about invalid end=-1
    # But it should accept end=-1 as valid!
    
    # Expected behavior: end=-1 is valid, so it should check if lines 60-end need to be read
    # Since file was only read up to line 50, lines 60-end need to be read
    # So should_read should be True, but NOT with an error about invalid end
    
    # Check that end=-1 is accepted (no error about invalid end)
    assert "invalid" not in reason.lower() or "positive" not in reason.lower(), \
        f"end=-1 should be valid, but got error: {reason}"
    
    # Since lines 60-end haven't been read, should_read should be True
    assert should_read is True, f"Lines 60-end haven't been read, should_read should be True, got {should_read}"
    
    # The reason should indicate that new lines need to be read
    assert "new" in reason.lower() or "need" in reason.lower() or "not in" in reason.lower() or "beyond" in reason.lower(), \
        f"Should indicate lines need to be read, got: {reason}"


def test_memory_should_read_file_end_minus_one_with_full_read():
    """Test end=-1 when file was read fully."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="full"
    ))
    
    # Test with end=-1 when file was read fully
    should_read, reason = memory.should_read_file("/test/file.py", 10, -1)
    
    # end=-1 should be valid
    assert "invalid" not in reason.lower() or "positive" not in reason.lower(), \
        f"end=-1 should be valid, but got error: {reason}"
    
    # File was read fully, so should_read should be False
    assert should_read is False, f"File was read fully, should_read should be False, got {should_read}"
    assert "already read" in reason.lower() or "full" in reason.lower(), \
        f"Should indicate file already read, got: {reason}"


def test_memory_should_read_file_start_minus_one_still_invalid():
    """Test start=-1 (should still be invalid, only end=-1 is special)."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="1-50"
    ))
    
    # Test with start=-1 (should be invalid!)
    should_read, reason = memory.should_read_file("/test/file.py", -1, 100)
    
    # start=-1 should be invalid (only end=-1 is special)
    assert should_read is True, f"start=-1 is invalid, should_read should be True (error), got {should_read}"
    assert "invalid" in reason.lower() or "positive" in reason.lower(), \
        f"start=-1 should be invalid, got: {reason}"
    assert "start" in reason.lower(), f"Error should mention 'start', got: {reason}"


def test_memory_should_read_file_end_zero_still_invalid():
    """Test end=0 (should still be invalid, only end=-1 is special)."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="1-50"
    ))
    
    # Test with end=0 (should be invalid, different from end=-1)
    should_read, reason = memory.should_read_file("/test/file.py", 60, 0)
    
    # end=0 should be invalid (only end=-1 is special)
    assert should_read is True, f"end=0 is invalid, should_read should be True (error), got {should_read}"
    assert "invalid" in reason.lower() or "positive" in reason.lower(), \
        f"end=0 should be invalid, got: {reason}"
    assert "end" in reason.lower(), f"Error should mention 'end', got: {reason}"


def test_memory_should_read_file_end_minus_one_with_start_none():
    """Test end=-1 with start=None (read from beginning to end)."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="1-50"
    ))
    
    # Test with start=None, end=-1 (read entire file)
    should_read, reason = memory.should_read_file("/test/file.py", None, -1)
    
    # end=-1 should be valid even with start=None
    assert "invalid" not in reason.lower() or "positive" not in reason.lower(), \
        f"end=-1 should be valid with start=None, but got error: {reason}"
    
    # Since we're asking to read the entire file (None to -1) and file was only read 1-50,
    # we should check if the entire file needs to be read
    # Actually, with start=None, end=-1, we're asking "should I read the entire file?"
    # Since part of it (1-50) was already read, but not the rest, it should return True
    # But the logic might be more complex... let's just check it doesn't error on end=-1
    # The exact behavior can be refined later


if __name__ == "__main__":
    print("Running end=-1 bug tests...")
    print("=" * 60)
    
    tests = [
        test_memory_should_read_file_end_minus_one_bug,
        test_memory_should_read_file_end_minus_one_with_full_read,
        test_memory_should_read_file_start_minus_one_still_invalid,
        test_memory_should_read_file_end_zero_still_invalid,
        test_memory_should_read_file_end_minus_one_with_start_none,
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
    print("Tests complete.")