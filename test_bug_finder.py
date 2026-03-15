from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

# Test 1: Empty lines_read
print("Test 1: Empty lines_read")
memory = WorkingMemory(current_task="Test")
memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", ""))
should_read, reason = memory.should_read_file("/test/file.py", 10, 50)
print(f"  should_read={should_read}, reason={reason}")
# Should return True (cannot determine)

# Test 2: Invalid lines_read
print("\nTest 2: Invalid lines_read")
memory2 = WorkingMemory(current_task="Test")
memory2.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "foo-bar-baz"))
should_read2, reason2 = memory2.should_read_file("/test/file.py", 10, 50)
print(f"  should_read={should_read2}, reason={reason2}")
# Should return True (cannot determine)

# Test 3: Multiple invalid entries
print("\nTest 3: Multiple invalid entries")
memory3 = WorkingMemory(current_task="Test")
memory3.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "foo"))
memory3.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "bar"))
should_read3, reason3 = memory3.should_read_file("/test/file.py", 10, 50)
print(f"  should_read={should_read3}, reason={reason3}")
# Should return True (cannot determine)

# Test 4: Mixed valid and invalid
print("\nTest 4: Mixed valid and invalid")
memory4 = WorkingMemory(current_task="Test")
memory4.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "foo"))
memory4.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-50"))
should_read4, reason4 = memory4.should_read_file("/test/file.py", 20, 40)
print(f"  should_read={should_read4}, reason={reason4}")
# Should return False (lines 20-40 are in range 10-50)

# Test 5: start > end
print("\nTest 5: start > end")
memory5 = WorkingMemory(current_task="Test")
memory5.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-50"))
should_read5, reason5 = memory5.should_read_file("/test/file.py", 50, 10)
print(f"  should_read={should_read5}, reason={reason5}")
# Should return True (invalid range)

# Test 6: start=0 (invalid)
print("\nTest 6: start=0 (invalid)")
memory6 = WorkingMemory(current_task="Test")
memory6.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-50"))
should_read6, reason6 = memory6.should_read_file("/test/file.py", 0, 50)
print(f"  should_read={should_read6}, reason={reason6}")
# Should return True (invalid line number)

# Test 7: end=0 (invalid)
print("\nTest 7: end=0 (invalid)")
memory7 = WorkingMemory(current_task="Test")
memory7.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-50"))
should_read7, reason7 = memory7.should_read_file("/test/file.py", 10, 0)
print(f"  should_read={should_read7}, reason={reason7}")
# Should return True (invalid line number)

# Test 8: start=None, end=Y with empty merged_ranges
print("\nTest 8: start=None, end=Y with empty merged_ranges")
memory8 = WorkingMemory(current_task="Test")
memory8.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "foo"))
should_read8, reason8 = memory8.should_read_file("/test/file.py", None, 50)
print(f"  should_read={should_read8}, reason={reason8}")
# Should return True (cannot determine)

# Test 9: start=X, end=None with empty merged_ranges
print("\nTest 9: start=X, end=None with empty merged_ranges")
memory9 = WorkingMemory(current_task="Test")
memory9.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "foo"))
should_read9, reason9 = memory9.should_read_file("/test/file.py", 10, None)
print(f"  should_read={should_read9}, reason={reason9}")
# Should return True (cannot determine)