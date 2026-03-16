"""Test for floating point precision bug in should_read_file."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_memory_should_read_file_float_precision_bug():
    """Test should_read_file bug: float -1.000000000000001 not accepted as -1.
    
    BUG: When end=-1.000000000000001 (float very close to -1 but not exactly due to
    floating point precision), the method rejects it with "Invalid line number: end must be an integer".
    But end=-1.0 (float) is accepted (converted to None).
    
    This is inconsistent! Either:
    1. Accept all floats close to -1 (within tolerance)
    2. Reject all floats (only accept int -1)
    3. Convert float to int if close to integer
    
    Current behavior: accepts -1.0 but rejects -1.000000000000001
    """
    memory = WorkingMemory(current_task="Test")
    
    # Add entry with file read fully
    memory.add_recent_file(WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="full",
        key_insights=["Full file read"]
    ))
    
    # Test 1: end=-1.0 (float, exact) - should be accepted
    should_read1, reason1 = memory.should_read_file("/test/file.py", 1, -1.0)
    assert should_read1 is False, (
        f"end=-1.0 should be accepted (converted to None). "
        f"Got: should_read={should_read1}, reason={reason1}"
    )
    assert "already read" in reason1.lower()
    
    # Test 2: end=-1.000000000000001 (float, very close to -1) - currently rejected
    # This is the bug!
    should_read2, reason2 = memory.should_read_file("/test/file.py", 1, -1.000000000000001)
    # Currently returns True with error about invalid type
    # Should either be accepted (like -1.0) or have better error message
    print(f"end=-1.000000000000001: should_read={should_read2}, reason={reason2}")
    # The bug is that this gives misleading error: "Invalid line number: end must be an integer, got float=-1.000000000000001"
    # But the user thinks they passed -1 (which should be accepted)
    
    # Test 3: end=-1 (int) - should be accepted
    should_read3, reason3 = memory.should_read_file("/test/file.py", 1, -1)
    assert should_read3 is False, (
        f"end=-1 (int) should be accepted. "
        f"Got: should_read={should_read3}, reason={reason3}"
    )
    assert "already read" in reason3.lower()
    
    # Test 4: end=-1.0000000000000001 (float, even closer to -1)
    # In Python: -1.0000000000000001 == -1 is True due to floating point precision
    should_read4, reason4 = memory.should_read_file("/test/file.py", 1, -1.0000000000000001)
    print(f"end=-1.0000000000000001: should_read={should_read4}, reason={reason4}")
    # This might be accepted (if -1.0000000000000001 == -1 is True)


if __name__ == "__main__":
    test_memory_should_read_file_float_precision_bug()
    print("\nTest demonstrates floating point precision bug in should_read_file")