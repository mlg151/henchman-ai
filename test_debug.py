from henchman.agents.working_memory import LineRange, WorkingMemory, WorkingMemoryEntry

# Test LineRange.from_str
print("Testing LineRange.from_str('10-50'):")
result = LineRange.from_str("10-50")
print(f"Result: {result}")
if result:
    print(f"  start={result.start}, end={result.end}")

# Test should_read_file
print("\nTesting should_read_file:")
memory = WorkingMemory(current_task="Test")
memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-50"))
print(f"Added file with lines_read='10-50'")

should_read, reason = memory.should_read_file("/test/file.py", 30, 70)
print(f"should_read_file('/test/file.py', 30, 70):")
print(f"  should_read={should_read}")
print(f"  reason={reason}")

# Let's trace through the logic
print("\nTracing logic:")
match = next((e for e in reversed(memory.recent_files) if e.path == "/test/file.py"), None)
print(f"match found: {match is not None}")
if match:
    print(f"match.lines_read: '{match.lines_read}'")
    print(f"match.lines_read == 'full': {match.lines_read == 'full'}")
    
    rng = LineRange.from_str(match.lines_read)
    print(f"LineRange.from_str('{match.lines_read}'): {rng}")
    if rng:
        print(f"  rng.start={rng.start}, rng.end={rng.end}")
        requested = LineRange(30, 70)
        print(f"requested: start=30, end=70")
        print(f"requested.start >= rng.start: {requested.start >= rng.start}")
        print(f"requested.end <= rng.end: {requested.end <= rng.end}")
        print(f"Both true: {requested.start >= rng.start and requested.end <= rng.end}")