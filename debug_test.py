#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Monkey-patch to add debug prints
import henchman.agents.working_memory as wm

original_should_read = wm.WorkingMemory.should_read_file

def debug_should_read(self, path, start=None, end=None):
    print(f"DEBUG: should_read_file called with path={path}, start={start}, end={end}")
    
    # Call original but intercept at key points
    # Actually, let's just trace through the logic manually
    
    # Normalize path
    normalized_path = wm._normalize_path(path)
    print(f"DEBUG: normalized_path={normalized_path}")
    
    # Find most recent entry
    lines_read = None
    for entry in reversed(self.recent_files):
        if wm._normalize_path(entry.path) == normalized_path:
            lines_read = entry.lines_read
            print(f"DEBUG: found entry with lines_read={lines_read}")
            break
    
    if lines_read is None:
        print(f"DEBUG: no entry found, returning True")
        return True, "File not previously recorded in working memory"
    
    # Check for "full"
    if isinstance(lines_read, str):
        normalized = "".join(lines_read.split()).lower()
        print(f"DEBUG: normalized lines_read={normalized}")
        if normalized == "full":
            print(f"DEBUG: lines_read is 'full', returning False")
            return False, "File already read (full)"
    
    # Parse line ranges
    valid_ranges = wm.WorkingMemory._parse_line_range(lines_read)
    print(f"DEBUG: valid_ranges={valid_ranges}")
    
    # Check for invalid lines_read
    if not valid_ranges:
        print(f"DEBUG: valid_ranges is empty")
        # Check start > end before returning
        if start is not None and end is not None and start > end:
            print(f"DEBUG: start={start} > end={end}, returning 'Invalid line range'")
            return True, f"Invalid line range: start ({start}) > end ({end}) - treating as new read"
        print(f"DEBUG: returning 'Cannot determine overlap'")
        return True, "Cannot determine overlap - invalid lines_read format"
    
    # Rest of logic...
    print(f"DEBUG: calling original method for rest of logic")
    return original_should_read(self, path, start, end)

wm.WorkingMemory.should_read_file = debug_should_read

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

print("Test 1: invalid lines_read AND start > end")
memory = WorkingMemory(current_task="Test")
memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "invalid-format"))

should_read, reason = memory.should_read_file("/test/file.py", 50, 10)
print(f"\nFinal result: should_read={should_read}, reason={reason}")
print(f"Expected: 'Invalid line range'")
print(f"Match: {'invalid line range' in reason.lower()}")

print("\n" + "="*50 + "\n")

print("Test 2: invalid lines_read but valid range (start < end)")
memory2 = WorkingMemory(current_task="Test")
memory2.add_recent_file(WorkingMemoryEntry("/test/file2.py", "Test", "invalid-format"))

should_read2, reason2 = memory2.should_read_file("/test/file2.py", 10, 50)
print(f"\nFinal result: should_read={should_read2}, reason={reason2}")
print(f"Expected: 'Cannot determine overlap'")
print(f"Match: {'cannot determine' in reason2.lower()}")