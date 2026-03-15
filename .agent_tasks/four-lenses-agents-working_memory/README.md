# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-15T22:15:00Z
## Bug Summary
The `should_read_file` method incorrectly handles boolean values as line numbers when a file was read "full". Boolean values (True/False) are accepted because `bool` is a subclass of `int` in Python, and the type check `type(start) is not int` is in the wrong position relative to the "full file read" check.

## Lens
**Lens 1: The Intent vs. Reality Check** - Logic Gaps and Type Safety

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Boolean values (True/False) should be rejected as invalid line numbers with clear error messages | When file was read "full", boolean values are accepted: True=1, False=0, leading to incorrect "File already read (full)" response |
| Invalid input validation should happen BEFORE checking file read status | Invalid boolean validation happens AFTER checking if file was read "full" |
| Type safety: Only integers or None should be accepted for line numbers | Boolean values pass type check because bool is subclass of int |

## Root Cause
The validation logic for line numbers (lines 387-404) checks `type(start) is not int` to reject booleans, but this check is positioned AFTER the early return for "file not in recent files" (line 382) and BEFORE the check for "full file read" (lines 419-432). However, when tracing through the actual execution path, I see the validation DOES happen before the "full" check. Let me re-examine...

Actually, looking at the code structure:
1. Line 382: Check if file not in recent files → return early
2. Line 387-404: Validate line numbers (including boolean check)
3. Line 407-416: Convert end=-1 and validate range
4. Line 419-432: Check if file was read "full"

The validation IS before the "full" check. But the test `test_memory_should_read_file_boolean_line_numbers` passes, which suggests the bug might have been fixed or I'm misunderstanding something.

Let me run a simpler test to verify current behavior:

<｜DSML｜function_calls>
<｜DSML｜invoke name="python_exec">
<｜DSML｜parameter name="code" string="true">from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

# Test the boolean bug
memory = WorkingMemory(current_task="Test")
memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))

# Test with start=True (bool)
should_read, reason = memory.should_read_file("/test/file.py", True, 10)
print(f"start=True, end=10: should_read={should_read}, reason={reason}")
print(f"Expected: True with error about invalid type")
print()

# Test with start=False (bool)  
should_read2, reason2 = memory.should_read_file("/test/file.py", False, 10)
print(f"start=False, end=10: should_read={should_read2}, reason={reason2}")
print(f"Expected: True with error about invalid line number (0 is invalid)")
print()

# Test with valid integers
should_read3, reason3 = memory.should_read_file("/test/file.py", 10, 50)
print(f"start=10, end=50: should_read={should_read3}, reason={reason3}")
print(f"Expected: False (file read fully)")