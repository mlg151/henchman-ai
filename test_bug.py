"""Test to demonstrate the bug in should_read_file with full then partial reads."""

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

def test_full_then_partial_bug():
    """Test that should_read_file incorrectly handles full read followed by partial read."""
    memory = WorkingMemory(current_task="Test")
    
    # Add old full read
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Old full read", "full"))
    
    # Add more recent partial read
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Recent partial read", "10-50"))
    
    # Request lines 60-100
    # The file was read fully in the past, so lines 60-100 WERE read
    # But the most recent read was partial (10-50)
    # According to the comment: "If file was read fully in the past but partially more recently,
    # we should check if the requested range is covered by recent partial reads"
    # Recent partial read (10-50) does NOT cover 60-100
    # So should return True (need to read)
    
    should_read, reason = memory.should_read_file("/test/file.py", 60, 100)
    print(f"Result: should_read={should_read}, reason={reason}")
    
    # Actually, let me think about this more...
    # If file was fully read in the past, we have that knowledge.
    # But if we then partially read it more recently, maybe the file changed?
    # Or maybe we're focusing on a specific part?
    # The comment suggests we should only consider recent partial reads.
    
    # Let me test another case: file was partially read, then fully read
    memory2 = WorkingMemory(current_task="Test")
    memory2.add_recent_file(WorkingMemoryEntry("/test/file2.py", "Partial read", "10-50"))
    memory2.add_recent_file(WorkingMemoryEntry("/test/file2.py", "Full read", "full"))
    
    # Request lines 60-100
    # Most recent read was "full", so should return False
    should_read2, reason2 = memory2.should_read_file("/test/file2.py", 60, 100)
    print(f"Result2: should_read={should_read2}, reason={reason2}")
    
    # Now test the actual bug: full read returns empty list from _parse_line_ranges
    # So when checking coverage, full reads don't contribute
    memory3 = WorkingMemory(current_task="Test")
    memory3.add_recent_file(WorkingMemoryEntry("/test/file3.py", "Full read", "full"))
    
    # Request lines 10-50
    # Most recent (and only) read is "full", so should return False
    should_read3, reason3 = memory3.should_read_file("/test/file3.py", 10, 50)
    print(f"Result3: should_read={should_read3}, reason={reason3}")
    
    # But what about when start=None, end=None (read entire file)?
    should_read4, reason4 = memory3.should_read_file("/test/file3.py")
    print(f"Result4 (read entire file): should_read={should_read4}, reason={reason4}")

if __name__ == "__main__":
    test_full_then_partial_bug()