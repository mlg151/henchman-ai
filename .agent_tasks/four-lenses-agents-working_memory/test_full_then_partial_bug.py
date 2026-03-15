"""Test for bug when file was read fully then partially."""

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

def test_full_then_partial_bug():
    """Test bug: file read fully, then partially, requests lines not in partial read.
    
    Scenario:
    - Entry 1 (older): Read file fully ("full")
    - Entry 2 (newer): Read lines 10-50 (partial)
    - Request: Read lines 60-80
    
    Lines 60-80 WERE read in entry 1 (full), but current implementation returns True
    (should read) because it ignores older full reads when most recent is partial.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Older entry: full read
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Full read", "full"))
    # Newer entry: partial read  
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Partial read", "10-50"))
    
    # Request lines 60-80 (were read in full read but not in partial)
    should_read, reason = memory.should_read_file("/test/file.py", 60, 80)
    
    print(f"should_read: {should_read}, reason: {reason}")
    print(f"recent_files: {memory.recent_files}")
    
    # BUG: Returns True (should read), but lines 60-80 WERE read in the full read
    # Current behavior: True because most recent is partial (10-50) and 60-80 not in that range
    # Is this a bug or by design?
    
    # According to comment: "If file was read fully in the past but partially more recently,
    # we should check if the requested range is covered by recent partial reads."
    # So by design, we ignore older full reads.
    
    # But is this RIGHT? If file was read fully, we know its contents.
    # Even if we re-read it partially later (maybe to check specific lines),
    # the full read still happened.
    
    # Actually, maybe it's NOT a bug. The partial read might indicate the file
    # changed, or we're focusing on specific lines. If we want to read other
    # lines, we should re-read them.
    
    # Let me check what the tests expect...
    
    # Run existing test
    import pytest
    from tests.agents.test_working_memory import TestWorkingMemory
    
    test_obj = TestWorkingMemory()
    test_obj.test_memory_should_read_file_full_then_partial_bug()
    print("\nExisting test passes (expects True)")

if __name__ == "__main__":
    test_full_then_partial_bug()