from henchman.agents.working_memory import LineRange, WorkingMemory, WorkingMemoryEntry

# Reproduce the exact test
print("Reproducing test_memory_should_read_file_overlap_but_not_contained:")
memory = WorkingMemory(current_task="Test")
entry = WorkingMemoryEntry("/test/file.py", "Test", "10-50")
print(f"Created WorkingMemoryEntry: path={entry.path}, lines_read='{entry.lines_read}'")
memory.add_recent_file(entry)

print(f"\nmemory.recent_files length: {len(memory.recent_files)}")
if memory.recent_files:
    stored = memory.recent_files[0]
    print(f"Stored entry: path={stored.path}, lines_read='{stored.lines_read}'")
    print(f"Type of lines_read: {type(stored.lines_read)}")
    print(f"Value of lines_read: '{stored.lines_read}'")
    print(f"stored.lines_read == '10-50': {stored.lines_read == '10-50'}")

# Test the three cases
print("\n1. Testing (1, 100):")
should_read, reason = memory.should_read_file("/test/file.py", 1, 100)
print(f"  Result: should_read={should_read}, reason='{reason}'")

print("\n2. Testing (30, 70):")
should_read2, reason2 = memory.should_read_file("/test/file.py", 30, 70)
print(f"  Result: should_read={should_read2}, reason='{reason2}'")

print("\n3. Testing (20, 40) - should be False (fully contained):")
should_read3, reason3 = memory.should_read_file("/test/file.py", 20, 40)
print(f"  Result: should_read={should_read3}, reason='{reason3}'")

# Let's trace through case 3 manually
print("\n--- Manual trace for case (20, 40) ---")
match = next((e for e in reversed(memory.recent_files) if e.path == "/test/file.py"), None)
print(f"match found: {match is not None}")
if match:
    print(f"match.lines_read: '{match.lines_read}'")
    print(f"match.lines_read == 'full': {match.lines_read == 'full'}")
    
    rng = LineRange.from_str(match.lines_read)
    print(f"LineRange.from_str('{match.lines_read}'): {rng}")
    if rng:
        print(f"  rng.start={rng.start}, rng.end={rng.end}")
        requested = LineRange(20, 40)
        print(f"requested: start=20, end=40")
        print(f"requested.start >= rng.start: {20 >= rng.start}")
        print(f"requested.end <= rng.end: {40 <= rng.end}")
        print(f"Both true: {20 >= rng.start and 40 <= rng.end}")
        if 20 >= rng.start and 40 <= rng.end:
            print("  Should return False!")
        else:
            print("  Should return True!")