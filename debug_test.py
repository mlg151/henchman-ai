from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

memory = WorkingMemory(current_task="Test")

# Add partial read (most recent)
memory.add_recent_file(WorkingMemoryEntry(
    path="/test/file.py",
    purpose="Partial read",
    lines_read="10-50"
))

# Add older full read (not most recent)
memory.add_recent_file(WorkingMemoryEntry(
    path="/test/file.py",
    purpose="Full read (older)",
    lines_read="full"
))

print("Recent files (most recent first):")
for i, entry in enumerate(reversed(memory.recent_files)):
    print(f"  {i}: path={entry.path}, lines_read={entry.lines_read}, purpose={entry.purpose}")

# Request lines 60-100 (were in older full read)
should_read, reason = memory.should_read_file("/test/file.py", 60, 100)

print(f"\nshould_read_file('/test/file.py', 60, 100):")
print(f"  should_read: {should_read}")
print(f"  reason: {reason}")

# Also test the reverse order
print("\n" + "="*60)
print("Testing reverse order (full read most recent):")
memory2 = WorkingMemory(current_task="Test")

# Add older full read
memory2.add_recent_file(WorkingMemoryEntry(
    path="/test/file.py",
    purpose="Full read (older)",
    lines_read="full"
))

# Add partial read (most recent)
memory2.add_recent_file(WorkingMemoryEntry(
    path="/test/file.py",
    purpose="Partial read",
    lines_read="10-50"
))

print("\nRecent files (most recent first):")
for i, entry in enumerate(reversed(memory2.recent_files)):
    print(f"  {i}: path={entry.path}, lines_read={entry.lines_read}, purpose={entry.purpose}")

# Request lines 60-100 (were in older full read)
should_read2, reason2 = memory2.should_read_file("/test/file.py", 60, 100)

print(f"\nshould_read_file('/test/file.py', 60, 100):")
print(f"  should_read: {should_read2}")
print(f"  reason: {reason2}")