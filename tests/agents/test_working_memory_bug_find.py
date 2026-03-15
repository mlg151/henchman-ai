"""Test to find a real bug in working_memory.py."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry, LineRange


def test_memory_should_read_file_edge_case_negative_zero():
    """Test edge case: what if start or end is -0?"""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="1-50"
    ))
    
    # Python doesn't have negative zero as a distinct value for int
    # But let's test with float -0.0
    should_read, reason = memory.should_read_file("/test/file.py", -0.0, 10)
    print(f"start=-0.0: should_read={should_read}, reason={reason}")
    # -0.0 is a float, not int, so should be rejected
    assert should_read is True
    assert "invalid" in reason.lower() or "integer" in reason.lower()


def test_memory_should_read_file_edge_case_very_large_numbers():
    """Test with very large line numbers."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="1-1000"
    ))
    
    # Very large start number
    should_read, reason = memory.should_read_file("/test/file.py", 1000000, 1000010)
    print(f"start=1000000: should_read={should_read}, reason={reason}")
    # Should return True because lines 1000000-1000010 haven't been read
    assert should_read is True
    assert "need to be read" in reason.lower() or "beyond" in reason.lower() or "not in" in reason.lower()


def test_memory_should_read_file_edge_case_none_string():
    """Test with None as string 'None'."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="1-50"
    ))
    
    # What if someone passes string "None"?
    # This would be caught by type(start) is not int check
    # But let's see what happens
    try:
        should_read, reason = memory.should_read_file("/test/file.py", "None", 10)
        print(f"start='None': should_read={should_read}, reason={reason}")
        assert should_read is True
        assert "invalid" in reason.lower() or "integer" in reason.lower()
    except Exception as e:
        print(f"Exception with start='None': {e}")
        # Might raise an exception, which is also a bug!


def test_memory_should_read_file_edge_case_empty_string_lines_read():
    """Test with empty string as lines_read."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read=""  # Empty string!
    ))
    
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)
    print(f"lines_read='': should_read={should_read}, reason={reason}")
    # Empty string should be treated as invalid
    assert should_read is True
    assert "invalid lines_read format" in reason.lower() or "cannot determine" in reason.lower()


def test_memory_should_read_file_edge_case_none_lines_read():
    """Test with None as lines_read."""
    memory = WorkingMemory(current_task="Test")
    # Can't create WorkingMemoryEntry with lines_read=None because it's typed as str
    # But what if from_dict loads None?
    entry = WorkingMemoryEntry.from_dict({
        "path": "/test/file.py",
        "purpose": "Test",
        "lines_read": None,  # None instead of string!
        "key_insights": [],
        "timestamp": "2024-01-01T00:00:00Z"
    })
    memory.add_recent_file(entry)
    
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)
    print(f"lines_read=None: should_read={should_read}, reason={reason}")
    # None should be treated as invalid
    assert should_read is True
    assert "invalid lines_read format" in reason.lower() or "cannot determine" in reason.lower()


def test_memory_should_read_file_edge_case_whitespace_only():
    """Test with whitespace-only lines_read."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="   \t\n  "  # Only whitespace
    ))
    
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)
    print(f"lines_read='   \\t\\n  ': should_read={should_read}, reason={reason}")
    # Whitespace-only should be treated as invalid
    assert should_read is True
    assert "invalid lines_read format" in reason.lower() or "cannot determine" in reason.lower()


def test_memory_should_read_file_edge_case_comma_only():
    """Test with comma-only lines_read."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read=","  # Just a comma
    ))
    
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)
    print(f"lines_read=',': should_read={should_read}, reason={reason}")
    # Comma-only should be treated as invalid
    assert should_read is True
    assert "invalid lines_read format" in reason.lower() or "cannot determine" in reason.lower()


def test_memory_should_read_file_edge_case_multiple_commas():
    """Test with multiple commas lines_read."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="10-20,,30-40"  # Double comma
    ))
    
    should_read, reason = memory.should_read_file("/test/file.py", 25, 35)
    print(f"lines_read='10-20,,30-40': should_read={should_read}, reason={reason}")
    # Should parse 10-20 and 30-40, skip empty part
    # Actually, this might work or might fail


def test_memory_line_range_validation():
    """Test LineRange validation edge cases."""
    # Test with start=0, end=10 (invalid start)
    try:
        r = LineRange(0, 10)
        print(f"LineRange(0, 10) created: {r}")
        # Should have raised ValueError
        assert False, "LineRange(0, 10) should raise ValueError"
    except ValueError as e:
        print(f"LineRange(0, 10) correctly raised ValueError: {e}")
    
    # Test with start=10, end=0 (invalid end and start > end)
    try:
        r = LineRange(10, 0)
        print(f"LineRange(10, 0) created: {r}")
        # Should have raised ValueError
        assert False, "LineRange(10, 0) should raise ValueError"
    except ValueError as e:
        print(f"LineRange(10, 0) correctly raised ValueError: {e}")
    
    # Test with start=1, end=1 (valid single line)
    r = LineRange(1, 1)
    print(f"LineRange(1, 1) created: {r}")
    assert r.start == 1 and r.end == 1
    
    # Test with start=5, end=5 (valid single line)
    r = LineRange(5, 5)
    print(f"LineRange(5, 5) created: {r}")
    assert r.start == 5 and r.end == 5


if __name__ == "__main__":
    print("Running edge case tests...")
    print("=" * 60)
    
    tests = [
        test_memory_should_read_file_edge_case_negative_zero,
        test_memory_should_read_file_edge_case_very_large_numbers,
        test_memory_should_read_file_edge_case_none_string,
        test_memory_should_read_file_edge_case_empty_string_lines_read,
        test_memory_should_read_file_edge_case_none_lines_read,
        test_memory_should_read_file_edge_case_whitespace_only,
        test_memory_should_read_file_edge_case_comma_only,
        test_memory_should_read_file_edge_case_multiple_commas,
        test_memory_line_range_validation,
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
    print("Edge case tests complete.")