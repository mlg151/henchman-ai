"""Debug the failing test."""

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

def test():
    memory = WorkingMemory(current_task="Test")
    
    # Add a file read with lines 10-20
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-20"))
    
    # Request lines 5-15 (overlaps with 10-20)
    should_read, reason = memory.should_read_file("/test/file.py", 5, 15)
    
    print(f"should_read: {should_read}")
    print(f"reason: {reason}")
    
    # What does the code return?
    # Let me trace through the logic...
    # 1. File is in memory with lines 10-20
    # 2. Requested range: 5-15
    # 3. merged_ranges = [LineRange(10, 20)]
    # 4. current_line = 5
    # 5. For rng in merged_ranges (only one range):
    #    - current_line < rng.start? 5 < 10? True
    #    - Returns "New or partially overlapping lines need to be read"
    
    # So should_read should be True!
    
    # Let me also test the second case
    should_read2, reason2 = memory.should_read_file("/test/file.py", 10, 10)
    print(f"\nshould_read2: {should_read2}")
    print(f"reason2: {reason2}")

if __name__ == "__main__":
    test()