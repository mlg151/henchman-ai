"""Test to understand the bug in should_read_file."""
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

# Test 1: end=-1 (int)
memory = WorkingMemory(current_task="Test")
memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-100"))

print("Test 1: start=10, end=-1 (int)")
should_read, reason = memory.should_read_file("/test/file.py", 10, -1)
print(f"  Result: should_read={should_read}, reason={reason}")

# Test 2: end=-1.0 (float)
print("\nTest 2: start=10, end=-1.0 (float)")
try:
    should_read, reason = memory.should_read_file("/test/file.py", 10, -1.0)
    print(f"  Result: should_read={should_read}, reason={reason}")
except Exception as e:
    print(f"  Exception: {e}")

# Test 3: end=-2 (invalid, should be caught)
print("\nTest 3: start=10, end=-2 (invalid)")
should_read, reason = memory.should_read_file("/test/file.py", 10, -2)
print(f"  Result: should_read={should_read}, reason={reason}")

# Test 4: start=10, end=50 (valid, within 1-100)
print("\nTest 4: start=10, end=50 (valid, within 1-100)")
should_read, reason = memory.should_read_file("/test/file.py", 10, 50)
print(f"  Result: should_read={should_read}, reason={reason}")

# Test 5: start=10, end=None (partial range)
print("\nTest 5: start=10, end=None (partial range)")
should_read, reason = memory.should_read_file("/test/file.py", 10, None)
print(f"  Result: should_read={should_read}, reason={reason}")