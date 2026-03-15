"""Test for bug where lines_read containing 'full' as token is not recognized."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_should_read_file_full_comma_range_bug():
    """Test bug: lines_read='full,10-20' should mean file was read fully."""
    memory = WorkingMemory(current_task="Test")
    
    # Add entry with lines_read containing 'full' but not exactly 'full'
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="full,10-20",  # Contains 'full' as first token
        key_insights=[],
    )
    memory.add_recent_file(entry)
    
    # Request lines 1-100
    should_read, reason = memory.should_read_file("/test/file.py", 1, 100)
    
    # BUG: Returns True (should read) because "full,10-20" != "full"
    # Should return False (file was read fully)
    assert should_read is False, (
        f"lines_read='full,10-20' contains 'full' token, so file should be considered fully read. "
        f"Got: should_read={should_read}, reason={reason}"
    )
    assert "already read" in reason.lower()


def test_should_read_file_range_comma_full_bug():
    """Test bug: lines_read='10-20,full' should mean file was read fully."""
    memory = WorkingMemory(current_task="Test")
    
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="10-20,full",  # Contains 'full' as second token
        key_insights=[],
    )
    memory.add_recent_file(entry)
    
    should_read, reason = memory.should_read_file("/test/file.py", 1, 100)
    
    # BUG: Returns True (should read) because "10-20,full" != "full"
    # Should return False (file was read fully)
    assert should_read is False, (
        f"lines_read='10-20,full' contains 'full' token, so file should be considered fully read. "
        f"Got: should_read={should_read}, reason={reason}"
    )
    assert "already read" in reason.lower()


def test_should_read_file_full_with_spaces_bug():
    """Test bug: lines_read='full , 10-20' should mean file was read fully."""
    memory = WorkingMemory(current_task="Test")
    
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="full , 10-20",  # Contains 'full' with spaces
        key_insights=[],
    )
    memory.add_recent_file(entry)
    
    should_read, reason = memory.should_read_file("/test/file.py", 1, 100)
    
    # BUG: Returns True (should read) because "full , 10-20" normalizes to "full,10-20" != "full"
    # Should return False (file was read fully)
    assert should_read is False, (
        f"lines_read='full , 10-20' contains 'full' token, so file should be considered fully read. "
        f"Got: should_read={should_read}, reason={reason}"
    )
    assert "already read" in reason.lower()


def test_should_read_file_uppercase_full_bug():
    """Test bug: lines_read='FULL,10-20' should mean file was read fully."""
    memory = WorkingMemory(current_task="Test")
    
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="FULL,10-20",  # Uppercase 'FULL'
        key_insights=[],
    )
    memory.add_recent_file(entry)
    
    should_read, reason = memory.should_read_file("/test/file.py", 1, 100)
    
    # BUG: Returns True (should read) because "FULL,10-20" normalizes to "full,10-20" != "full"
    # Should return False (file was read fully)
    assert should_read is False, (
        f"lines_read='FULL,10-20' contains 'full' token (case-insensitive), so file should be considered fully read. "
        f"Got: should_read={should_read}, reason={reason}"
    )
    assert "already read" in reason.lower()


def test_should_read_file_exact_full_still_works():
    """Test that exact 'full' still works (regression test)."""
    memory = WorkingMemory(current_task="Test")
    
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="full",  # Exact 'full'
        key_insights=[],
    )
    memory.add_recent_file(entry)
    
    should_read, reason = memory.should_read_file("/test/file.py", 1, 100)
    
    # Should return False (file was read fully)
    assert should_read is False, (
        f"lines_read='full' should mean file was read fully. "
        f"Got: should_read={should_read}, reason={reason}"
    )
    assert "already read" in reason.lower()


def test_should_read_file_full_with_whitespace_still_works():
    """Test that 'full' with whitespace still works (regression test)."""
    memory = WorkingMemory(current_task="Test")
    
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="  full  ",  # 'full' with spaces
        key_insights=[],
    )
    memory.add_recent_file(entry)
    
    should_read, reason = memory.should_read_file("/test/file.py", 1, 100)
    
    # Should return False (file was read fully)
    assert should_read is False, (
        f"lines_read='  full  ' should mean file was read fully. "
        f"Got: should_read={should_read}, reason={reason}"
    )
    assert "already read" in reason.lower()


if __name__ == "__main__":
    # Run tests to demonstrate the bug
    import sys
    
    print("Testing bug: lines_read containing 'full' token not recognized...")
    print("=" * 60)
    
    tests = [
        test_should_read_file_full_comma_range_bug,
        test_should_read_file_range_comma_full_bug,
        test_should_read_file_full_with_spaces_bug,
        test_should_read_file_uppercase_full_bug,
        test_should_read_file_exact_full_still_works,
        test_should_read_file_full_with_whitespace_still_works,
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
        print("\nBUG CONFIRMED: Tests fail with current implementation.")
        print("The bug is: should_read_file doesn't recognize 'full' as a token in lines_read.")
    else:
        print("\nAll tests pass (bug may have been fixed).")
    
    sys.exit(1 if failures > 0 else 0)