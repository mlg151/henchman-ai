# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-14T15:00:00Z
## Bug Summary
The `should_read_file` method incorrectly handles the case where a file was read fully earlier but has a more recent partial read entry. It only checks the most recent entry for "full", causing unnecessary re-reads of lines that were already read in a full read.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| If a file was read fully at any point (any entry has `lines_read="full"`), any line range should be considered already read | Only checks most recent entry for "full", ignoring older full reads |
| Historical full reads should prevent re-reading of any lines in the file | Partial reads after full reads cause unnecessary re-reads of other lines |
| File reading decisions should be accurate based on complete history | Inaccurate decisions waste context window and reduce performance |

## Root Cause
The bug is in the logic of `should_read_file` method at lines 254-256:
```python
# Check if MOST RECENT entry indicates file was read fully
if matches[0].lines_read.strip().lower() == "full":
    return False, "File already read (full)"
```

The method only checks the most recent entry for "full". If a file was:
1. Read fully at time T1 (entry: "full")
2. Read partially at time T2 (entry: "10-50")
3. We want to read lines 60-100 at time T3

The method will check most recent entry ("10-50"), see it's not "full", and then check line ranges. Since `LineRange.from_str("full")` returns `None`, the full read entry won't be considered in the line range check either. Result: returns `True` (should read) even though lines 60-100 were already read in the full read.

## Fix Plan
Modify the `should_read_file` method to check ALL entries for "full", not just the most recent one. If any entry has `lines_read="full"` (case-insensitive, with whitespace), the file was fully read at some point and any line range should be considered already read.

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Modified `should_read_file` method to check ALL entries for "full" instead of just the most recent entry.
2. `tests/agents/test_working_memory.py` - Added new test `test_memory_should_read_file_full_then_partial` to verify the fix.

## Changes Made
The bug was in lines 254-256 of `working_memory.py`. Changed from:
```python
# Check if MOST RECENT entry indicates file was read fully
if matches[0].lines_read.strip().lower() == "full":
    return False, "File already read (full)"
```

To:
```python
# Check if ANY entry indicates file was read fully
# If file was read fully at any point, we know all lines
for match in matches:
    if match.lines_read.strip().lower() == "full":
        return False, "File already read (full)"
```

This ensures that if a file was read fully at any point (even if followed by partial reads), any line range will be considered already read, preventing unnecessary re-reads and improving performance.