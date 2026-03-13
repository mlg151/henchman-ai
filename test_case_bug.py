from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

# Test case sensitivity
print("Testing case sensitivity:")
memory = WorkingMemory(current_task="Test")

# Test with "full" (lowercase)
memory1 = WorkingMemory(current_task="Test")
memory1.add_recent_file(WorkingMemoryEntry("/test/file1.py", "Test", "full"))
should_read1, reason1 = memory1.should_read_file("/test/file1.py", 10, 50)
print(f"lines_read='full': should_read={should_read1}, reason='{reason1}'")

# What if lines_read is "FULL" (uppercase)?
# We can't create a WorkingMemoryEntry with lines_read="FULL" because it's a parameter
# But what if it comes from deserialization?
# Actually, let me check the code...

print("\nChecking the code logic:")
print("if match.lines_read == 'full':  # Case-sensitive!")
print("So if lines_read is 'FULL' or 'Full', this check fails!")
print("Then LineRange.from_str('FULL') returns None")
print("Then we return True, 'Cannot determine overlap - invalid lines_read format'")
print("That's a BUG!")

# Let me test what happens with invalid lines_read
memory2 = WorkingMemory(current_task="Test")
# Create entry with invalid lines_read
entry = WorkingMemoryEntry("/test/file2.py", "Test", "FULL")  # Uppercase
print(f"\nCreated entry with lines_read='FULL': {entry.lines_read}")
memory2.add_recent_file(entry)
should_read2, reason2 = memory2.should_read_file("/test/file2.py", 10, 50)
print(f"lines_read='FULL': should_read={should_read2}, reason='{reason2}'")
print("This should return False (file read fully) but returns True!")