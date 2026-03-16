"""Test for the real bug in working_memory.py.

The bug: should_read_file incorrectly handles end=-1 when start is provided.
When end=-1 and start is provided (e.g., start=10, end=-1), it means "read from line 10 to EOF".
The code converts end=-1 to None, then enters partial range logic, which is incorrect.
"""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry


def test_should_read_file_end_minus_one_with_start_bug():
    """Test the actual bug: end=-1 with start provided.
    
    When end=-1 and start is provided (e.g., start=10, end=-1),
    it means "read from line 10 to EOF".
    
    The current code converts end=-1 to None at line 538, then
    at line 580: if start is None or end is None:
    Since end is None, it enters partial range logic.
    
    But this is wrong! end=-1 with start means "read from start to EOF",
    not "read from start to ?".
    
    Example: File was read lines 1-50. Request: start=30, end=-1 (read lines 30-EOF).
    Since we've read lines 1-50, lines 30-50 are read, but we don't know about lines 51+.
    Should return True with reason about needing to read beyond line 50.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-50"))
    
    # Test: start=30, end=-1 (read from line 30 to EOF)
    # File was read lines 1-50, so lines 30-50 are read, but we don't know about lines 51+
    # Should return True with reason about needing to read beyond line 50
    should_read, reason = memory.should_read_file("/test/file.py", start=30, end=-1)
    
    # BUG: Currently converts end=-1 to None, then treats as partial range
    # Might return incorrect result
    print(f"Result: should_read={should_read}, reason={reason}")
    
    # The correct behavior should be:
    # 1. Recognize this means "read from line 30 to EOF"
    # 2. Check if we've read line 30 (we have, it's in 1-50)
    # 3. Check if we've read to EOF (we haven't, we only read to line 50)
    # 4. Return True with reason about needing to read beyond line 50
    assert should_read is True, (
        f"File read lines 1-50, requested lines 30-EOF. "
        f"Should return True (need lines 51+). Got: {should_read}, reason: {reason}"
    )
    # Should mention something about EOF or beyond
    # Current buggy behavior might return something else
    assert "beyond" in reason.lower() or "eof" in reason.lower() or "after" in reason.lower() or "need" in reason.lower(), (
        f"Reason should indicate need to read beyond current range. Got: {reason}"
    )


def test_should_read_file_end_minus_one_with_start_full_read():
    """Test end=-1 with start when file was read fully.
    
    If file was read fully, any range including end=-1 should return False.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # File was read fully, so reading from line 10 to EOF should return False
    should_read, reason = memory.should_read_file("/test/file.py", start=10, end=-1)
    
    print(f"Result: should_read={should_read}, reason={reason}")
    
    # Should return False (file was read fully)
    assert should_read is False, (
        f"File was read fully. start=10, end=-1 should return False. "
        f"Got: {should_read}, reason: {reason}"
    )
    assert "already read" in reason.lower()


def test_should_read_file_end_minus_one_no_start():
    """Test end=-1 without start (read from beginning to EOF).
    
    This is the original use case: read entire file.
    end=-1 gets converted to None, which is correct.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-50"))
    
    # Test: start=None, end=-1 (read entire file)
    # File was only partially read (1-50), so should return True
    should_read, reason = memory.should_read_file("/test/file.py", end=-1)
    
    print(f"Result: should_read={should_read}, reason={reason}")
    
    # Should return True (file may not be fully read - we can't determine without file size)
    assert should_read is True, (
        f"File only read lines 1-50, requested entire file (end=-1). "
        f"Should return True (conservative). Got: {should_read}, reason: {reason}"
    )
    # Accept either old message ("not fully read") or new more accurate message
    assert ("not fully read" in reason.lower() or 
            "partial" in reason.lower() or 
            "need" in reason.lower() or
            "cannot determine" in reason.lower() or
            "file size unknown" in reason.lower()), \
        f"Reason should indicate file may not be fully read. Got: {reason}"


if __name__ == "__main__":
    test_should_read_file_end_minus_one_with_start_bug()
    test_should_read_file_end_minus_one_with_start_full_read()
    test_should_read_file_end_minus_one_no_start()
    print("\nTests demonstrate the bug")