#!/usr/bin/env python3
"""Test for the multiple ranges bug in working_memory.py"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry, LineRange

print("Test 1: Single range '10-20'")
rng = LineRange.from_str("10-20")
print(f"  LineRange.from_str('10-20') = {rng}")
print(f"  Expected: LineRange(start=10, end=20)")
print(f"  Pass: {rng == LineRange(10, 20) if rng else False}")

print("\nTest 2: Multiple ranges '10-20,30-40'")
rng2 = LineRange.from_str("10-20,30-40")
print(f"  LineRange.from_str('10-20,30-40') = {rng2}")
print(f"  Expected: None (because format not supported)")
print(f"  Pass: {rng2 is None}")

print("\nTest 3: Test should_read_file with multiple ranges")
memory = WorkingMemory(current_task="Test")
# This should work according to docstring but doesn't
memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-20,30-40"))

# Request lines 15-25 (partially covered by first range)
should_read, reason = memory.should_read_file("/test/file.py", 15, 25)
print(f"  should_read_file('/test/file.py', 15, 25)")
print(f"    should_read: {should_read}")
print(f"    reason: {reason}")
print(f"  Expected: False (lines 15-20 are covered by first range)")
print(f"  Actual result: {'False' if not should_read else 'True'} with reason containing {reason}")

print("\nTest 4: Check what happens with invalid format")
# Since LineRange.from_str returns None for "10-20,30-40", valid_ranges will be empty
# So should_read_file should return "Cannot determine overlap - invalid lines_read format"
memory2 = WorkingMemory(current_task="Test")
memory2.add_recent_file(WorkingMemoryEntry("/test/file2.py", "Test", "10-20,30-40"))

should_read2, reason2 = memory2.should_read_file("/test/file2.py", 1, 100)
print(f"  should_read_file('/test/file2.py', 1, 100)")
print(f"    should_read: {should_read2}")
print(f"    reason: {reason2}")
print(f"  Expected: True with 'Cannot determine overlap - invalid lines_read format'")
print(f"  Actual: {'True' if should_read2 else 'False'} with reason containing {reason2}")
print(f"  'cannot determine' in reason2.lower(): {'cannot determine' in reason2.lower()}")