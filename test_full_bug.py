"""Test the 'full' case-insensitive bug more carefully."""
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry, LineRange

# Test what LineRange.from_str("FULL") returns
print("Test LineRange.from_str('FULL'):")
r = LineRange.from_str("FULL")
print(f"  Result: {r}")
print(f"  Expected: None (not a valid range)")
print()

# Test the actual should_read_file logic
memory = WorkingMemory(current_task="Test")
memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "FULL"))

print("Test should_read_file with 'FULL':")
print(f"  Entry lines_read: 'FULL'")
print(f"  match.lines_read.lower() == 'full': {'FULL'.lower() == 'full'}")

# Manually trace through should_read_file logic
match = next((e for e in reversed(memory.recent_files) if e.path == "/test/file.py"), None)
print(f"\nManual trace:")
print(f"  1. match found: {match is not None}")
print(f"  2. match.lines_read.lower() == 'full': {match.lines_read.lower() == 'full'}")
print(f"  3. If true, returns False, 'File already read (full)'")
print(f"  4. Otherwise, continues to LineRange.from_str('FULL') which returns None")
print(f"  5. Then returns True, 'Cannot determine overlap - invalid lines_read format'")

# Actually call the method
should_read, reason = memory.should_read_file("/test/file.py", 10, 50)
print(f"\nActual result: should_read={should_read}, reason={reason}")
print(f"Expected: should_read=False, reason contains 'already read'")